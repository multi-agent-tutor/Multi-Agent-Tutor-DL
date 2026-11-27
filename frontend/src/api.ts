// Client de l'API FastAPI (api/main.py). Aucune autre origine n'est appelée.
import type {
  AgentResponse,
  AskRequest,
  CarteSRS,
  Course,
  Flashcard,
  LangueUI,
  Niveau,
  QCM,
  Ressource,
} from "./types";
import { slideId } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ErreurApi extends Error {
  constructor(
    message: string,
    readonly statut: number,
  ) {
    super(message);
  }
}

async function verifier(res: Response): Promise<Response> {
  if (res.ok) return res;
  let detail = `${res.status} ${res.statusText}`;
  try {
    const corps = await res.json();
    if (typeof corps?.detail === "string") detail = corps.detail;
    else if (Array.isArray(corps?.detail)) detail = corps.detail.map((d: { msg?: string }) => d.msg).join(" ; ");
  } catch {
    /* corps non JSON */
  }
  throw new ErreurApi(detail, res.status);
}

async function requete(chemin: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${chemin}`, init);
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ErreurApi(`API injoignable (${API_URL}). Lance « uvicorn api.main:app --reload ».`, 0);
  }
  return verifier(res);
}

async function json<T>(chemin: string, init?: RequestInit): Promise<T> {
  return (await requete(chemin, init)).json() as Promise<T>;
}

const corpsJson = (corps: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(corps),
  signal,
});

const qs = (params: Record<string, string | number | null | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  return p.toString();
};

// ---------------------------------------------------------------- réponses des agents texte

/**
 * Lire la réponse d'un agent texte (Explainer, Q&A) en l'affichant au fil de l'eau.
 *
 * - Réponse `text/event-stream` (SSE de l'API) : chaque événement `data:` est soit du
 *   JSON `{"token": "..."}` (morceau de texte), soit le JSON final `AgentResponse`
 *   (`{"reponse": ..., "sources": [...]}`), soit du texte brut ajouté tel quel. Les événements
 *   `progression` / `erreur` (ni `token` ni `reponse`) n'entrent pas dans le texte.
 * - Réponse JSON : le texte est révélé progressivement côté client.
 */
export async function lireReponseAgent(
  res: Response,
  surTexte: (textePartiel: string) => void,
  signal?: AbortSignal,
): Promise<AgentResponse> {
  const type = res.headers.get("content-type") ?? "";
  if (type.includes("text/event-stream") && res.body) return lireSSE(res.body, surTexte, signal);
  const reponse = (await res.json()) as AgentResponse;
  await reveler(reponse.reponse, surTexte, signal);
  return reponse;
}

async function lireSSE(
  corps: ReadableStream<Uint8Array>,
  surTexte: (t: string) => void,
  signal?: AbortSignal,
): Promise<AgentResponse> {
  const lecteur = corps.getReader();
  const decodeur = new TextDecoder();
  let tampon = "";
  let texte = "";
  let finale: AgentResponse | null = null;
  const traiter = (evenement: string) => {
    const donnees = evenement
      .split(/\r?\n/)
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!donnees || donnees === "[DONE]") return;
    try {
      const objet = JSON.parse(donnees);
      if (typeof objet?.token === "string") texte += objet.token;
      else if (typeof objet?.reponse === "string") {
        finale = objet as AgentResponse;
        texte = finale.reponse;
      }
    } catch {
      texte += donnees;
    }
    surTexte(texte);
  };
  for (;;) {
    if (signal?.aborted) throw new DOMException("Annulé", "AbortError");
    const { value, done } = await lecteur.read();
    if (done) break;
    tampon += decodeur.decode(value, { stream: true });
    const evenements = tampon.split(/\r?\n\r?\n/);
    tampon = evenements.pop() ?? "";
    evenements.forEach(traiter);
  }
  if (tampon.trim()) traiter(tampon);
  return finale ?? { agent: "qa", reponse: texte, sources: [], score_fidelite: null };
}

const mouvementReduit = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Révéler un texte mot à mot (au plus ~1,5 s), comme le fera le streaming SSE. */
async function reveler(texte: string, surTexte: (t: string) => void, signal?: AbortSignal) {
  const mots = texte.split(/(\s+)/);
  if (mouvementReduit() || mots.length < 4) return surTexte(texte);
  const pas = Math.max(1, Math.ceil(mots.length / 60));
  for (let i = pas; i < mots.length; i += pas) {
    if (signal?.aborted) throw new DOMException("Annulé", "AbortError");
    surTexte(mots.slice(0, i).join(""));
    await new Promise((r) => setTimeout(r, 25));
  }
  surTexte(texte);
}

// ---------------------------------------------------------------- routes

export const api = {
  cours: (courseId: string) => json<Course>(`/course/${encodeURIComponent(courseId)}`),

  /**
   * POST /upload avec suivi : `surEnvoi(fraction)` pendant l'envoi du fichier (0 à 1), puis
   * `surTraitement()` quand le fichier est reçu et que l'API l'analyse (aucune progression côté
   * serveur : la réponse arrive d'un bloc). XMLHttpRequest, car fetch ne donne pas la progression d'envoi.
   */
  televerser(
    fichier: File,
    { langue, surEnvoi, surTraitement, signal }: {
      langue?: string;
      surEnvoi?: (fraction: number) => void;
      surTraitement?: () => void;
      signal?: AbortSignal;
    } = {},
  ): Promise<Course> {
    return new Promise((resoudre, rejeter) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier);
      if (langue) donnees.append("langue", langue); // ignoré par l'API tant que l'ingestion n'est pas branchée
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_URL}/upload`);
      xhr.responseType = "text";
      xhr.upload.onprogress = (e) => e.lengthComputable && surEnvoi?.(e.loaded / e.total);
      xhr.upload.onload = () => {
        surEnvoi?.(1);
        surTraitement?.();
      };
      xhr.onload = () => {
        let corps: unknown = null;
        try {
          corps = JSON.parse(xhr.responseText);
        } catch {
          /* corps non JSON */
        }
        if (xhr.status >= 200 && xhr.status < 300 && corps) return resoudre(corps as Course);
        const detail = (corps as { detail?: unknown } | null)?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg).join(" ; ")
              : `${xhr.status} ${xhr.statusText}`;
        rejeter(new ErreurApi(message, xhr.status));
      };
      xhr.onerror = () => rejeter(new ErreurApi(`API injoignable (${API_URL}). Lance « uvicorn api.main:app --reload ».`, 0));
      xhr.onabort = () => rejeter(new DOMException("Annulé", "AbortError"));
      if (signal?.aborted) return rejeter(new DOMException("Annulé", "AbortError"));
      signal?.addEventListener("abort", () => xhr.abort(), { once: true });
      xhr.send(donnees);
    });
  },

  /** Réponse brute de /slide/{id}/explain, à passer à `lireReponseAgent`. */
  expliquer: (courseId: string, numero: number, niveau: Niveau, signal?: AbortSignal) =>
    requete(`/slide/${slideId(courseId, numero)}/explain?${qs({ niveau })}`, {
      signal,
      headers: { Accept: "text/event-stream, application/json" },
    }),

  /** Réponse brute de /ask, à passer à `lireReponseAgent`. */
  demander: (corps: AskRequest, signal?: AbortSignal) => {
    const init = corpsJson(corps, signal);
    (init.headers as Record<string, string>).Accept = "text/event-stream, application/json";
    return requete("/ask", init);
  },

  async quiz(courseId: string, slide: number | null, langue: LangueUI, n = 3, signal?: AbortSignal) {
    const res = await requete(`/quiz?${qs({ course_id: courseId, slide, n, langue })}`, { signal });
    const message = res.headers.get("X-Quiz-Message");
    return { qcm: (await res.json()) as QCM[], message: message ? decodeURIComponent(message) : null };
  },

  flashcards: (courseId: string, slide: number | null, langue: LangueUI, n = 5, signal?: AbortSignal) =>
    json<Flashcard[]>(`/flashcards?${qs({ course_id: courseId, slide, n, langue })}`, { signal }),

  sauverFlashcards: (user: string, flashcards: Flashcard[]) =>
    json<CarteSRS[]>("/flashcards/save", corpsJson({ user, flashcards })),

  cartesDues: (user: string, courseId: string) =>
    json<CarteSRS[]>(`/flashcards/due?${qs({ user, course_id: courseId })}`),

  reviser: (user: string, carteId: number, qualite: number) =>
    json<CarteSRS>(`/flashcards/${carteId}/review`, corpsJson({ user, qualite })),

  async exporterAnki(user: string, courseId: string): Promise<Blob> {
    return (await requete(`/flashcards/export?${qs({ course_id: courseId, user })}`)).blob();
  },

  ressources: (courseId: string, numero: number, niveau: Niveau, langue: LangueUI, signal?: AbortSignal) =>
    json<Ressource[]>(`/resources?${qs({ slide_id: slideId(courseId, numero), niveau, langue })}`, { signal }),
};

/**
 * URL du rendu PNG d'une slide (`Slide.image_rendu`, chemin relatif à data/processed/<course_id>/,
 * produit par l'ingestion H1). Route attendue côté API : GET /course/{course_id}/{chemin}.
 * Tant que l'API ne la sert pas, l'image échoue et la page Cours garde l'affichage texte.
 */
export function urlImageSlide(courseId: string, imageRendu: string): string {
  const chemin = imageRendu.replace(/^\/+/, "").split("/").map(encodeURIComponent).join("/");
  return `${API_URL}/course/${encodeURIComponent(courseId)}/${chemin}`;
}

/** Proposer un fichier au téléchargement (export Anki). */
export function telecharger(blob: Blob, nom: string) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nom });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Identifiant de l'étudiant pour la révision espacée (A6), gardé dans le navigateur. */
export function utilisateur(): string {
  let id = localStorage.getItem("mat-user");
  if (!id) {
    id = "etudiant";
    localStorage.setItem("mat-user", id);
  }
  return id;
}

export const estAnnulation = (e: unknown) => (e as Error)?.name === "AbortError";
