// Miroir TypeScript des modèles Pydantic (schemas/models.py et api/models.py).
// À garder aligné à la main : toute évolution du contrat passe par schemas/.

export type Langue = "fr" | "en" | "ar" | "mixte";
export type LangueUI = "fr" | "en" | "ar";
export type Niveau = "debutant" | "intermediaire" | "avance";
export type NiveauBloom = "memoriser" | "comprendre" | "appliquer" | "analyser";

export interface Slide {
  id: string;
  course_id: string;
  numero: number;
  titre: string;
  texte: string;
  notes: string;
  image_rendu: string | null;
  images: string[];
  description_figures: string[];
  formules_latex: string[];
  concepts: string[];
  ocr: boolean;
}

export interface Course {
  schema_version: string;
  id: string;
  titre: string;
  fichier_source: string;
  format: "pdf" | "pptx";
  langue: Langue;
  source_url: string | null;
  nombre_slides: number;
  resume: string;
  slides: Slide[];
}

export interface Source {
  course_id: string;
  numero: number;
  extrait: string;
}

/** Un tour de conversation (schemas/models.py : Message). */
export interface Message {
  role: "utilisateur" | "tuteur";
  contenu: string;
}

/** Nombre maximal de messages d'historique acceptés par POST /ask (api/models.py : MAX_HISTORIQUE). */
export const MAX_HISTORIQUE = 40;

/** Corps de POST /ask (api/models.py : AskRequest). */
export interface AskRequest {
  course_id: string;
  slide_courante: number;
  question: string;
  niveau?: Niveau;
  langue?: Langue;
  /** Tours précédents, du plus ancien au plus récent (sans la question en cours). */
  historique?: Message[];
}

export interface AgentResponse {
  agent: "explainer" | "qa" | "quiz" | "resources" | "critic";
  reponse: string;
  sources: Source[];
  score_fidelite: number | null;
}

export interface QCM {
  question: string;
  choix: [string, string, string, string];
  bonne_reponse: number;
  explication: string;
  niveau_bloom: NiveauBloom;
  source: Source;
}

export interface Flashcard {
  recto: string;
  verso: string;
  source: Source;
}

export interface EtatSM2 {
  repetitions: number;
  intervalle: number;
  facilite: number;
  prochaine_revision: string; // date ISO AAAA-MM-JJ
}

export interface CarteSRS {
  id: number;
  user: string;
  course_id: string;
  recto: string;
  verso: string;
  source: Source;
  etat: EtatSM2;
}

export interface Ressource {
  titre: string;
  url: string;
  type: "video" | "article" | "cours" | "exercice" | "documentation" | "recherche";
  langue: Langue;
  description: string;
  justification: string;
}

/** Identifiant de slide : « <course_id>__s<NNN> » (schemas.models.slide_id). */
export const slideId = (courseId: string, numero: number) =>
  `${courseId}__s${String(numero).padStart(3, "0")}`;
