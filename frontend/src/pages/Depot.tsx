// Page Dépôt (maquette D2 depot.html) : glisser-déposer ou choix d'un PPTX/PDF, POST /upload avec suivi
// (envoi avec progression, traitement, erreur, annulation), puis ouverture du cours dans la page Cours.
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ErreurApi, estAnnulation } from "../api";
import { Icone } from "../components/Icones";
import { Mascotte, type EtatMascotte } from "../components/Mascotte";
import { useLangue, type CleTexte } from "../i18n";
import { lireRecents, retirerRecent, type CoursRecent } from "../recents";
import type { Course, LangueUI, Niveau } from "../types";

const TAILLE_MAX = 50 * 1024 * 1024; // maquette : 50 Mo au plus
const EXTENSIONS = ["pdf", "pptx"] as const;
const ACCEPT = ".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation";
/** Étapes de l'analyse côté API (ingestion H1, OCR, VLM H2, index RAG B1). */
const ETAPES: { cle: CleTexte; agent: string }[] = [
  { cle: "e1", agent: "Ingestion" },
  { cle: "e2", agent: "OCR" },
  { cle: "e3", agent: "VLM" },
  { cle: "e4", agent: "RAG" },
];
/** L'API ne renvoie pas d'avancement par étape : celles-ci avancent à ce rythme, la dernière attend la réponse. */
const RYTHME_ETAPES_MS = 1400;

type Etat =
  | { nom: "choix" }
  | { nom: "pret-a-envoyer" }
  | { nom: "envoi"; fraction: number }
  | { nom: "traitement"; etape: number }
  | { nom: "termine"; cours: Course };

interface Props {
  niveau: Niveau;
  surNiveau: (n: Niveau) => void;
  /** Cours reçu (ou rouvert) : l'application l'ouvre. */
  surCours: (c: Course) => void;
  surPage: (p: "cours" | "quiz") => void;
}

const LOCALES: Record<LangueUI, string> = { fr: "fr-FR", en: "en-GB", ar: "ar-TN" };

export function PageDepot({ niveau, surNiveau, surCours, surPage }: Props) {
  const { t, langue } = useLangue();
  const entree = useRef<HTMLInputElement>(null);
  const lancer = useRef<HTMLButtonElement>(null);
  const ouvrir = useRef<HTMLButtonElement>(null);
  const annulation = useRef<AbortController | null>(null);
  const minuteurMascotte = useRef(0);
  const [fichier, setFichier] = useState<File | null>(null);
  const [etat, setEtat] = useState<Etat>({ nom: "choix" });
  const [erreur, setErreur] = useState<string | null>(null);
  const [survol, setSurvol] = useState(false);
  const [langueCours, setLangueCours] = useState("auto");
  const [mascotte, setMascotte] = useState<EtatMascotte>("");
  const [recents, setRecents] = useState<CoursRecent[]>(lireRecents);
  const [ouvertureRecent, setOuvertureRecent] = useState<string | null>(null);

  const occupe = etat.nom === "envoi" || etat.nom === "traitement";
  const nombre = (n: number, chiffres = 0) => new Intl.NumberFormat(LOCALES[langue], { maximumFractionDigits: chiffres }).format(n);
  const taille = (octets: number) =>
    octets >= 1048576 ? `${nombre(octets / 1048576, 1)} ${t("mo")}` : `${nombre(Math.max(1, Math.round(octets / 1024)))} ${t("ko")}`;

  const humeur = (e: EtatMascotte, duree?: number) => {
    clearTimeout(minuteurMascotte.current);
    setMascotte(e);
    if (duree) minuteurMascotte.current = window.setTimeout(() => setMascotte(""), duree);
  };

  // Un fichier lâché à côté de la zone ne doit pas faire quitter la page au navigateur.
  useEffect(() => {
    const bloquer = (e: globalThis.DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) e.preventDefault();
    };
    addEventListener("dragover", bloquer);
    addEventListener("drop", bloquer);
    return () => {
      removeEventListener("dragover", bloquer);
      removeEventListener("drop", bloquer);
      annulation.current?.abort();
      clearTimeout(minuteurMascotte.current);
    };
  }, []);

  // Étapes de traitement : avancent seules, la dernière reste « en cours » jusqu'à la réponse de l'API.
  const enTraitement = etat.nom === "traitement";
  useEffect(() => {
    if (!enTraitement) return;
    const id = setInterval(
      () => setEtat((e) => (e.nom === "traitement" && e.etape < ETAPES.length - 1 ? { ...e, etape: e.etape + 1 } : e)),
      RYTHME_ETAPES_MS,
    );
    return () => clearInterval(id);
  }, [enTraitement]);

  useEffect(() => {
    if (etat.nom === "pret-a-envoyer") lancer.current?.focus();
    if (etat.nom === "termine") ouvrir.current?.focus();
  }, [etat.nom]);

  function choisir(f: File | undefined) {
    if (!f || occupe) return;
    const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (!(EXTENSIONS as readonly string[]).includes(ext)) {
      setErreur(t("erreur-type", { nom: f.name }));
      humeur("oups", 1600);
      return;
    }
    if (f.size > TAILLE_MAX) {
      setErreur(t("erreur-taille"));
      humeur("oups", 1600);
      return;
    }
    setErreur(null);
    setFichier(f);
    setEtat({ nom: "pret-a-envoyer" });
  }

  async function analyser() {
    if (!fichier || occupe) return;
    const ctrl = new AbortController();
    annulation.current = ctrl;
    setErreur(null);
    setEtat({ nom: "envoi", fraction: 0 });
    humeur("reflechit");
    try {
      const cours = await api.televerser(fichier, {
        langue: langueCours === "auto" ? undefined : langueCours,
        surEnvoi: (fraction) => setEtat((e) => (e.nom === "envoi" ? { nom: "envoi", fraction } : e)),
        surTraitement: () => setEtat({ nom: "traitement", etape: 0 }),
        signal: ctrl.signal,
      });
      surCours(cours);
      setRecents(lireRecents());
      setEtat({ nom: "termine", cours });
      humeur("");
    } catch (e) {
      setEtat({ nom: "pret-a-envoyer" });
      if (estAnnulation(e)) {
        setErreur(t("envoi-annule"));
        humeur("");
        return;
      }
      setErreur(t("erreur-analyse", { m: e instanceof ErreurApi ? e.message : String(e) }));
      humeur("oups", 2000);
    } finally {
      annulation.current = null;
    }
  }

  function reinitialiser() {
    setFichier(null);
    setErreur(null);
    setEtat({ nom: "choix" });
    if (entree.current) entree.current.value = "";
    requestAnimationFrame(() => entree.current?.focus());
  }

  async function rouvrir(r: CoursRecent) {
    setOuvertureRecent(r.id);
    setErreur(null);
    try {
      surCours(await api.cours(r.id));
      surPage("cours");
    } catch (e) {
      if (e instanceof ErreurApi && e.statut === 404) {
        setRecents(retirerRecent(r.id));
        setErreur(t("recent-introuvable", { titre: r.titre }));
      } else setErreur(e instanceof ErreurApi ? e.message : String(e));
    } finally {
      setOuvertureRecent(null);
    }
  }

  const glisser = (e: DragEvent, dedans: boolean) => {
    e.preventDefault();
    if (!occupe) setSurvol(dedans);
  };

  const ext = fichier?.name.split(".").pop()?.toLowerCase();
  const pourcent = etat.nom === "envoi" ? Math.round(etat.fraction * 100) : 100;
  const etapeCourante = etat.nom === "traitement" ? etat.etape : etat.nom === "termine" ? ETAPES.length : -1;

  return (
    <main className="page-depot">
      <div>
        <div className="entete-depot">
          <Mascotte etat={mascotte} />
          <div>
            <h1>{t("depot-titre")}</h1>
            <p>{t("depot-chapo")}</p>
          </div>
        </div>

        <label
          className={survol ? "zone survol" : "zone"}
          hidden={etat.nom !== "choix"}
          onDragEnter={(e) => glisser(e, true)}
          onDragOver={(e) => glisser(e, true)}
          onDragLeave={(e) => glisser(e, false)}
          onDrop={(e) => {
            glisser(e, false);
            choisir(e.dataTransfer.files[0]);
          }}
        >
          <input ref={entree} type="file" accept={ACCEPT} onChange={(e) => choisir(e.target.files?.[0])} />
          <span className="disque" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 16V4M7 9l5-5 5 5" />
              <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
            </svg>
          </span>
          <strong>{t("glisser")}</strong>
          <span>
            {t("ou")} <span className="lien-choisir">{t("choisir-fichier")}</span>
          </span>
          <small>{t("formats")}</small>
        </label>

        {erreur && (
          <p className="erreur-depot" role="alert">
            <Icone nom="alerte" />
            <span>{erreur}</span>
          </p>
        )}

        {fichier && etat.nom !== "choix" && etat.nom !== "termine" && (
          <div className="panneau fichier-choisi">
            <span className={ext === "pdf" ? "badge-type pdf" : "badge-type"}>{ext?.toUpperCase()}</span>
            <div>
              <div className="nom">{fichier.name}</div>
              <div className="meta">{taille(fichier.size)}</div>
            </div>
            {occupe ? (
              <button className="bouton discret" type="button" onClick={() => annulation.current?.abort()}>
                {t("annuler")}
              </button>
            ) : (
              <button className="bouton discret" type="button" onClick={() => entree.current?.click()}>
                {t("changer")}
              </button>
            )}
          </div>
        )}

        {etat.nom === "pret-a-envoyer" && (
          <>
            <div className="options">
              <label className="option">
                <span>{t("langue-cours")}</span>
                <select value={langueCours} onChange={(e) => setLangueCours(e.target.value)}>
                  <option value="auto">{t("auto")}</option>
                  <option value="fr" lang="fr">
                    Français
                  </option>
                  <option value="en" lang="en">
                    English
                  </option>
                  <option value="ar" lang="ar">
                    العربية
                  </option>
                </select>
              </label>
              <label className="option">
                <span>{t("niveau-expl")}</span>
                <select value={niveau} onChange={(e) => surNiveau(e.target.value as Niveau)}>
                  {(["debutant", "intermediaire", "avance"] as Niveau[]).map((n) => (
                    <option key={n} value={n}>
                      {t(n)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="actions-depot">
              <button ref={lancer} className="bouton principal" type="button" onClick={analyser}>
                <Icone nom="importer" />
                <span>{erreur ? t("reessayer") : t("lancer")}</span>
              </button>
            </div>
          </>
        )}

        {(occupe || etat.nom === "termine") && (
          <ol className="panneau etapes-analyse" aria-live="polite">
            <li className={etat.nom === "envoi" ? "en-cours" : "fait"}>
              <span className="pastille">
                <svg viewBox="0 0 16 16">
                  <path d="M3.5 8.5l3 3 6-7" />
                </svg>
              </span>
              <span>
                {t("e-envoi")}
                {etat.nom === "envoi" && (
                  <span className="progression-envoi">
                    <span
                      className="barre-envoi"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={pourcent}
                      aria-label={t("e-envoi")}
                    >
                      <i style={{ transform: `scaleX(${etat.fraction})` }} />
                    </span>
                    <b>{nombre(pourcent)} %</b>
                  </span>
                )}
              </span>
              <span className="agent">API</span>
            </li>
            {ETAPES.map(({ cle, agent }, i) => (
              <li key={cle} className={i < etapeCourante ? "fait" : i === etapeCourante ? "en-cours" : ""}>
                <span className="pastille">
                  <svg viewBox="0 0 16 16">
                    <path d="M3.5 8.5l3 3 6-7" />
                  </svg>
                </span>
                <span>{t(cle)}</span>
                <span className="agent">{agent}</span>
              </li>
            ))}
            {etat.nom === "traitement" && <li className="note-traitement">{t("traitement-note")}</li>}
          </ol>
        )}

        {etat.nom === "termine" && (
          <section className="panneau pret" aria-labelledby="pret-titre">
            <div className="titre-pret">
              <Mascotte etat="contente" />
              <div>
                <h2 id="pret-titre">{t("pret-titre", { n: etat.cours.nombre_slides })}</h2>
                <p dir="auto">
                  {etat.cours.titre} · {t("pret-detail")}
                </p>
              </div>
            </div>
            <span className="verifie">
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3.5 8.5l3 3 6-7" />
              </svg>
              <span>{t("local")}</span>
            </span>
            <div className="actions-depot">
              <button ref={ouvrir} className="bouton principal" type="button" onClick={() => surPage("cours")}>
                <Icone nom="cours" />
                <span>{t("ouvrir")}</span>
              </button>
              <button className="bouton" type="button" onClick={() => surPage("quiz")}>
                <Icone nom="quiz" />
                <span>{t("tester-tout-de-suite")}</span>
              </button>
              <button className="bouton discret" type="button" onClick={reinitialiser}>
                {t("autre")}
              </button>
            </div>
          </section>
        )}
      </div>

      <aside className="cote-depot">
        <section className="panneau">
          <h2>{t("garanties-titre")}</h2>
          <ul className="liste-garanties">
            <li>
              <Icone nom="bouclier" />
              <span>{t("g1")}</span>
            </li>
            <li>
              <Icone nom="ecran" />
              <span>{t("g2")}</span>
            </li>
            <li>
              <Icone nom="monde" />
              <span>{t("g3")}</span>
            </li>
          </ul>
        </section>
        <section className="panneau">
          <h2>{t("recents-titre")}</h2>
          {recents.length === 0 ? (
            <p className="recents-vide">{t("recents-vide")}</p>
          ) : (
            <ul className="recents">
              {recents.map((r) => (
                <li key={r.id}>
                  <button type="button" disabled={ouvertureRecent !== null || occupe} aria-busy={ouvertureRecent === r.id} onClick={() => rouvrir(r)}>
                    <span className={r.format === "pdf" ? "badge-type pdf" : "badge-type"}>{r.format.toUpperCase()}</span>
                    <span>
                      <b dir="auto">{r.titre}</b>
                      <span>
                        {t("slides-n", { n: r.nombre_slides })} · {t(`langue-${r.langue}` as CleTexte)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </main>
  );
}
