# T0 — Schéma d'une slide et interfaces entre modules

> Statut : **proposition v1.0**, à valider en réunion avec Ghayth, Both et Ali, puis figée.
> Après validation, toute modification passe par Ons (PR sur `develop`).

Source de vérité : `schemas/models.py` (Pydantic v2). Les fichiers `schemas/*.json`
sont des JSON Schema générés par `python -m schemas.export` ; ne pas les éditer à la main.
Exemple complet : `schemas/exemples/exemple_cours.json`.

## 1. Identifiants

| Objet | Format | Exemple |
|---|---|---|
| `course_id` | nom du fichier source sans extension, `[a-z0-9_]` | `ml_regression_lineaire_fr` |
| `slide.id` | `<course_id>__s<NNN>` (numéro sur 3 chiffres, à partir de 001) | `ml_regression_lineaire_fr__s002` |
| `chunk.id` | identique à l'id de la slide (une slide = un chunk) | |

`slide_id(course_id, numero)` construit l'identifiant ; les modèles refusent un id incohérent.

## 2. Slide

| Champ | Type | Rempli par | Description |
|---|---|---|---|
| `id` | str | H1 | `<course_id>__s<NNN>` |
| `course_id` | str | H1 | identifiant du cours |
| `numero` | int ≥ 1 | H1 | numéro de la slide / page |
| `titre` | str | H1 | vide si absent |
| `texte` | str | H1 | texte visible, ou texte OCR |
| `notes` | str | H1 | notes du présentateur (PPTX) |
| `image_rendu` | str \| null | H1 | PNG 150 dpi, relatif à `data/processed/<course_id>/` |
| `images` | list[str] | H1 | images extraites, mêmes chemins relatifs |
| `description_figures` | list[str] | H2 | descriptions VLM des schémas / graphiques |
| `formules_latex` | list[str] | H2 | formules en LaTeX, sans `$` |
| `concepts` | list[str] | H3 | concepts clés |
| `ocr` | bool | H1 | vrai si le texte vient de l'OCR |

Les champs non encore produits restent à leur valeur par défaut (`""`, `[]`), jamais absents.
Les champs inconnus sont refusés (`extra="forbid"`).

## 3. Course (`data/processed/<course_id>/course.json`)

`schema_version`, `id`, `titre`, `fichier_source`, `format` (`pdf`|`pptx`),
`langue` (`fr`|`en`|`ar`|`mixte`), `source_url`, `nombre_slides`, `resume` (H3), `slides`.
Contrôles : `nombre_slides == len(slides)`, slides numérotées 1..n sans trou, toutes du même cours.

## 4. Chunk et SearchHit (RAG)

- `Chunk` : `id`, `course_id`, `numero`, `titre`, `contenu` (= texte + notes + description_figures),
  `contexte_precedent`, `contexte_suivant` (slides N-1 / N+1), `langue`.
- `SearchHit` : `chunk` + `score` (après RRF ou reranking).

## 5. État du graphe et réponses des agents

- `TutorState` (O1) : `course_id`, `slide_courante`, `niveau` (`debutant`|`intermediaire`|`avance`),
  `langue_reponse`, `historique` (liste de `Message`), `question`,
  `intention` (`expliquer`|`question`|`quiz`|`ressources`), `reponse`, `sources`, `iterations_critic` (≤ 2),
  `score_fidelite` (0..1, Critic O3) et `corrections` (affirmations non appuyées à reprendre ; vide = acceptée).
- `Source` : `course_id`, `numero`, `extrait` — affichée « [Slide N] ».
- `AgentResponse` : `agent`, `reponse`, `sources`, `score_fidelite` (rempli par le Critic).

Les formats des quiz/flashcards (A2) et des ressources (A4) seront ajoutés par Ali, en suivant ces conventions.

## 6. Disposition des fichiers

```
data/corpus/<course_id>.<pdf|pptx>          # cours bruts (C1)
data/corpus_extra/                          # corpus complémentaire (G2)
data/processed/<course_id>/course.json      # sortie de l'ingestion (ignoré par Git)
data/processed/<course_id>/slides/sNNN.png  # rendus 150 dpi
data/processed/<course_id>/images/          # images extraites
data/cache/                                 # cache VLM / embeddings (ignoré par Git)
```

## 7. Interfaces entre modules

Signatures attendues (les modules importent les modèles depuis `schemas`).

```python
# ingestion/ — Ghayth
def parse_course(path: Path, course_id: str | None = None) -> Course: ...       # H1
def enrich_with_vlm(course: Course) -> Course: ...                               # H2 (avec cache)
def build_course_map(course: Course) -> Course: ...                              # H3 : concepts + resume
def get_prerequisites(slide_id: str) -> list[str]: ...                           # H3 : ids de slides

# rag/ — Both
def index_course(course: Course) -> int: ...                                     # B2 : nb de chunks indexés
def search(query: str, course_id: str, k: int = 5) -> list[SearchHit]: ...       # B1/B2

# agents/ — Ons, Both, Ali (nœuds LangGraph)
def explainer(state: TutorState) -> TutorState: ...                              # O2
def qa(state: TutorState) -> TutorState: ...                                     # B3
def critic(state: TutorState) -> TutorState: ...                                 # O3

# api/ — Ali
# POST /upload -> Course ; GET /course/{id} -> Course
# GET /slide/{id}/explain?niveau=... -> AgentResponse ; POST /ask -> AgentResponse
```

Flux : `fichier PDF/PPTX → parse_course → enrich_with_vlm → build_course_map → index_course → graphe (TutorState) → API`.
