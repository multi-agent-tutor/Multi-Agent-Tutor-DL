# ingestion/

Responsable : Ghayth — tâches H1 → H2 → H3 (voir `docs/Repartition_Taches_Multi_Agent_Tutor_v2.pdf`).
Contrat de sortie : schéma T0 (`docs/schema.md`, `schemas/models.py`). 100 % local, aucune API externe.

```
PDF / PPTX ──H1 parse.py──▶ course.json (texte, notes, tableaux, images, rendus PNG, OCR)
           ──H2 vlm.py────▶ + description_figures, formules_latex   (Qwen2.5-VL local, cache)
           ──H3 course_map.py▶ + concepts, resume, course_map.json  (LLM local A0, graphe de prérequis)
```

## Utilisation rapide

```powershell
# Tout le pipeline sur un cours (ou un dossier)
.venv\Scripts\python -m ingestion data/corpus/en/dl/dl_self_attention_ntu_en.pptx

# Étape par étape
.venv\Scripts\python -m ingestion.parse data/corpus            # H1 sur tout le corpus
.venv\Scripts\python -m ingestion.parse cours.pdf --texte-brut # H1 rapide : texte seul
.venv\Scripts\python -m ingestion.vlm dl_self_attention_ntu_en # H2 (cours déjà ingéré)
.venv\Scripts\python -m ingestion.course_map dl_self_attention_ntu_en --mermaid  # H3
```

```python
from ingestion import parse_course, enrich_with_vlm, build_course_map, get_prerequisites, ingest

course = ingest("data/corpus/fr/dl/dl_reseaux_convolutifs_cnam_fr.pdf")  # H1 + H2 + H3
get_prerequisites("dl_reseaux_convolutifs_cnam_fr__s012")  # -> ["..._s003", "..._s007"]
```

Sorties dans `data/processed/<course_id>/` (ignoré par Git) :

| Fichier | Contenu |
|---|---|
| `course.json` | `Course` T0 complet |
| `slides/sNNN.png` | rendu 150 dpi de chaque slide |
| `images/` | images extraites (logos répétés et icônes exclus, dédupliquées) |
| `course_map.json` | graphe des concepts (voir H3) |
| `course_map.mmd` | graphe des prérequis en Mermaid (option `--mermaid`) |

## H1 — `parse.py`

- **PDF** (PyMuPDF) : texte par page, titre = ligne de plus grande police dans le tiers haut,
  images extraites, rendu PNG 150 dpi.
- **PPTX** (python-pptx) : texte des formes (groupes compris, ordre de lecture), **tableaux**
  (`cellule | cellule`), titres de graphiques, **notes du présentateur**, images.
  Rendu : conversion en PDF par **LibreOffice** (`soffice`) si installé, sinon **PowerPoint**
  (Windows, COM), avec cache dans `data/cache/pptx_pdf/`. Les slides masquées sont gérées.
- **OCR** si la slide n'a pas de texte **ou** si sa couche texte est trouée (puces vides : texte
  dessiné en vectoriel, cas des PDF decktape). Backend `OCR_BACKEND` : `auto` (Tesseract s'il est
  installé, sinon **RapidOCR** : pip seul, sans logiciel système), `tesseract`, `rapidocr`, `aucun`.
  L'OCR n'est retenu que s'il apporte nettement plus de mots que la couche texte.
- Nettoyage : en-têtes/pieds de page répétés sur ≥ 50 % des slides retirés, numéros de page et
  puces isolées supprimés.
- Métadonnées : titre, langue et `source_url` lus dans les inventaires C1/G2 s'ils existent,
  sinon suffixe `_fr`/`_en` du nom de fichier, sinon détection automatique.

Limites connues : l'OCR ne lit pas l'écriture manuscrite (scans `maths_*_scan_uiowa_en`) ;
c'est le VLM (H2) qui les décrit. Sans LibreOffice ni PowerPoint, un PPTX n'a pas de rendu PNG
(texte, notes et images restent extraits).

## H2 — `vlm.py`

Modèle local : **Qwen2.5-VL-3B-Instruct** (GGUF Q4_K_M + projecteur mmproj Q8_0) via llama.cpp.

```powershell
.venv\Scripts\pip install huggingface_hub
.venv\Scripts\hf download ggml-org/Qwen2.5-VL-3B-Instruct-GGUF Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf --local-dir models
```

- Sortie JSON contrainte par grammaire : `{"figures": [...], "formules": [...]}`, validée par
  Pydantic, puis nettoyée (délimiteurs `$` retirés, doublons et « aucune figure » supprimés).
- Seules les slides **visuelles** sont envoyées (images, ≥ 12 tracés vectoriels, formules, scans) ;
  `--toutes` force l'analyse de toutes les slides.
- **Cache** `data/cache/vlm/` : clé = SHA-256(image + modèle + version du prompt + langue).
- Un échec du VLM ne bloque jamais l'ingestion : les champs restent vides. Si le JSON est
  invalide (boucle du modèle), une seconde tentative est faite à température plus élevée.
- Filtres : descriptions quasi dupliquées, « formules » décrites comme des figures et phrases
  renvoyées comme formules sont écartées.

Mesures (CPU, Qwen2.5-VL-3B Q4_K_M, image 896 px) :

| Cas | Temps / slide | Qualité |
|---|---|---|
| Slide de schéma (`dl_self_attention_ntu_en`) | ≈ 60–70 s | descriptions justes et pédagogiques ; formules parfois omises |
| Notes manuscrites scannées (`maths_matrices_scan_uiowa_en`) | ≈ 130 s | 8/8 slides, 60 formules ; matrices et vecteurs bien lus, quelques formules bruitées |

Le cache rend tout second passage instantané. Pour aller plus vite : `VLM_MAX_COTE=768`, ou un
GPU avec une roue llama-cpp CUDA et `VLM_N_GPU_LAYERS=-1`.

| Variable | Défaut | Rôle |
|---|---|---|
| `VLM_BACKEND` | `llamacpp` | `llamacpp`, `transformers`, `fake` (tests) ou `aucun` |
| `VLM_MODEL_PATH` | `models/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | modèle |
| `VLM_MMPROJ_PATH` | `models/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf` | projecteur d'images |
| `VLM_N_CTX` / `VLM_N_THREADS` / `VLM_N_GPU_LAYERS` | 4096 / auto / 0 | llama.cpp |
| `VLM_MAX_COTE` | `896` | plus grand côté de l'image envoyée (px) |
| `OCR_BACKEND` | `auto` | voir H1 |

## H3 — `course_map.py`

1. **Concepts** de chaque slide extraits par le LLM local (`agents/llm.py`, A0), sortie validée,
   cache `data/cache/concepts/`. Repli heuristique (n-grammes TF-IDF) si le LLM est absent.
2. **Graphe** : concept → slides où il apparaît (extrait ou cité), concept → slide d'introduction,
   concept → prérequis (concepts introduits **avant** et présents là où il est introduit).
   Le graphe est acyclique par construction.
3. **Résumé global** du cours par le LLM (repli : résumé extractif) → `course.resume`.
4. **`get_prerequisites(slide_id)`** → ids des slides antérieures qui introduisent les concepts
   nécessaires, triés dans l'ordre du cours (5 au plus). `[]` si la carte n'existe pas.

Validé avec Qwen2.5-3B (A0) : `dl_self_attention_ntu_en` → 120 concepts, résumé fidèle ;
p. ex. « Self-attention for Image » (s33) → prérequis s1 (self-attention) et s3 (vector set).
Environ 10 s par slide sur CPU, puis instantané grâce au cache.

`course_map.json` :

```json
{
  "version": "h3-v1", "course_id": "...", "methode": "llm:qwen2.5-3b-instruct-q4_k_m.gguf",
  "resume": "...",
  "concepts": {"matrice": {"nom": "matrice", "introduit_slide": 2, "slides": [2, 3, 4], "prerequis": ["vecteur"]}},
  "slides": {"<course_id>__s004": {"numero": 4, "concepts": ["valeur propre"], "prerequis": ["<course_id>__s002"]}}
}
```

## Tests

```powershell
.venv\Scripts\python -m pytest tests/test_ingestion_parse.py tests/test_ingestion_vlm.py tests/test_ingestion_course_map.py
```

Ils créent des PDF/PPTX synthétiques et simulent le VLM/LLM : ni modèle, ni LibreOffice requis.
