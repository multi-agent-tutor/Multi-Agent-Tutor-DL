# rag/

Responsable : Both — tâches B1-B2 (voir la répartition des tâches).

## B1 — Qdrant + embeddings + recherche hybride

| Fichier | Rôle |
|---|---|
| `store.py` | `VectorStore` : collection Qdrant de `Chunk` (schéma T0), recherche dense filtrable par `course_id`. Embedders : `BgeM3Embedder` (bge-m3, 1024 dim., multilingue) et `HashEmbedder` (factice, pour les tests). |
| `search.py` | `BM25` (lexical, insensible aux accents), `fusion_rrf` (Reciprocal Rank Fusion, k = 60) et `RechercheHybride` (dense + BM25 → RRF → `list[SearchHit]`). |

### Utilisation

```python
from rag.store import VectorStore, BgeM3Embedder
from rag.search import RechercheHybride

store = VectorStore(BgeM3Embedder(), chemin="qdrant_storage")  # ou url="http://localhost:6333"
store.ajouter(chunks)                      # list[schemas.models.Chunk]
recherche = RechercheHybride(store)
hits = recherche.rechercher("Qu'est-ce qu'une clé primaire ?", k=5, course_id="bd_introduction_cotedazur_fr")
```

- **Qdrant sans Docker** : `chemin="qdrant_storage"` (dossier local, ignoré par Git). Avec Docker : `docker run -p 6333:6333 qdrant/qdrant` puis `url="http://localhost:6333"`.
- **bge-m3** est téléchargé au premier encodage (~2,3 Go, mis en cache par Hugging Face).
- Après un ajout ou une suppression de chunks, appeler `recherche.rafraichir()` pour reconstruire l'index BM25.
- B2 : demander `k=20` à `rechercher`, puis reranker et garder les 5 premiers. B4 : `recherche.dense(...)` sert de version « avant ».

### Vérifier

```bash
python -m pytest tests/test_rag_b1.py -q              # sans modèle (HashEmbedder, Qdrant en mémoire)
python -m rag.search "Qu'est-ce qu'une clé primaire ?" --hash   # démo sans modèle
python -m rag.search "how to move a VM without downtime"         # démo avec bge-m3
```

## B2 — Indexation des slides + reranker

| Fichier | Rôle |
|---|---|
| `index.py` | `chunks_du_cours` : une slide = un chunk (texte + notes + descriptions des figures), avec le titre des slides N-1 et N+1 en contexte. `indexer_cours` / `indexer_dossier` : (ré)indexent les `course.json` de H1 dans Qdrant. |
| `rerank.py` | `BgeReranker` (bge-reranker-v2-m3, multilingue, local, scores entre 0 et 1), `reranker(...)` et `RechercheReranked` : hybride top-20 → reranker → top-5. `MotsCommunsReranker` remplace le modèle dans les tests. |

### Utilisation

```bash
python -m rag.index                                    # indexe data/processed/*/course.json (bge-m3)
python -m rag.index data/processed/<id>/course.json    # un seul cours
python -m rag.rerank "how to move a VM without downtime"   # démo hybride + reranker
```

```python
from rag.rerank import BgeReranker, RechercheReranked
pipeline = RechercheReranked(RechercheHybride(store), BgeReranker())
hits = pipeline.rechercher("Qu'est-ce qu'une clé primaire ?", course_id="...")  # top-5, score 0..1
```

- Réindexer après H2 (VLM) : relancer `python -m rag.index`, chaque cours est remplacé.
- B3 : le score du reranker (0..1) sert de seuil pour répondre « l'information n'est pas dans le cours ».
- `--hash` utilise une collection séparée (`slides_hash`), pour ne pas mélanger avec les vecteurs bge-m3.
