# api/

Responsable : Ali — tâches A1, A3, A7 (voir la répartition des tâches).

## A1 — API factice

Routes (données factices tirées de `schemas/exemples/exemple_cours.json`) :

| Méthode | Route | Réponse |
|---|---|---|
| POST | `/upload` (champ `fichier`, PDF/PPTX) | `Course` |
| GET | `/course/{id}` | `Course` |
| GET | `/slide/{id}/explain?niveau=debutant\|intermediaire\|avance` | `AgentResponse` |
| POST | `/ask` (body : `course_id`, `slide_courante`, `question`, `niveau`, `langue`) | `AgentResponse` avec sources `[Slide N]` |
| GET | `/quiz?course_id=&slide=` | `list[QCM]` |
| GET | `/resources?slide_id=` | `list[Ressource]` |

Les types viennent de `schemas/models.py` ; `QCM`, `Ressource` et `AskRequest`, absents du
contrat commun, sont définis dans `api/models.py`. CORS est ouvert aux origines locales du
frontend (ports 3000, 5173, 8501, 8765).

### Lancer

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Puis ouvrir http://localhost:8000/docs.

### Tester

```bash
pytest tests/test_api.py tests/test_api_graphe.py
```

## A3 — Branchement du graphe multi-agent (`api/graphe.py`)

Le graphe O1 est construit une seule fois (`api.graphe.graphe()`, au premier appel) :

```python
construire_graphe({"expliquer": explainer_agent, "quiz": quiz_verifie_agent,
                   "ressources": resources_agent, "question": <qa>}, critic=critic_agent)
```

- `question` : `AgentQA(RechercheReranked(RechercheHybride(store), BgeReranker()))` si `agents/qa.py` (B3)
  existe et `API_QA=auto` (index Qdrant : `QDRANT_PATH`, `qdrant_storage` par défaut), enveloppé dans
  `AgentQAProtege` ; sinon le bouchon d'O1 (voir `API_QA` ci-dessous).
- `GET /slide/{id}/explain?niveau=&langue=` : intention `expliquer` imposée → Explainer (O2) ⇄ Critic (O3).
- `POST /ask` (body : `course_id`, `slide_courante`, `question`, `niveau`, `langue`, `historique` optionnel,
  liste de `{"role": "utilisateur" | "tuteur", "contenu": "…"}`, 40 messages au plus, envoyée par la page Cours) :
  le router du graphe choisit l'agent ; `agent` de la réponse = nœud utilisé (`qa`, `explainer`, `quiz`, `resources`).
- `GET /quiz` : QCM de l'agent Quiz (A2) filtrés par `verifier_qcm` du Critic (O3).
- `/resources`, `/flashcards*` : inchangés.

### `API_CRITIC` (`.env`)

| Valeur | Graphe | Usage |
|---|---|---|
| `on` (défaut) | `construire_graphe(..., critic=critic_agent)` : explication et Q&A relues par le Critic (O3), corrigées 2 fois au plus | qualité, machine rapide |
| `off` | `construire_graphe(...)` sans Critic : réponse livrée sans vérification, `score_fidelite` à `null`, pas d'étape SSE `verification` | démo sur CPU lent |

Lue à la construction du graphe (premier appel) : redémarrer l'API après l'avoir changée. Le quiz reste
vérifié par `verifier_qcm` dans les deux modes.

### `API_QA` (`.env`)

| Valeur | Agent `question` | Usage |
|---|---|---|
| `auto` (défaut) | vrai Q&A (B3) si `agents/qa.py` existe, sinon bouchon d'O1 | normal |
| `bouchon` | bouchon d'O1, même si `agents/qa.py` existe | tests, démo sans modèles RAG |

En mode `auto`, le Q&A charge bge-m3, le reranker et l'index Qdrant au premier appel. Si sa construction
ou un appel échoue (`OSError` modèle non téléchargé, `ImportError`, index vide ou absent…), l'erreur est
journalisée et `/ask` répond quand même (200, `agent: "qa"`) : « Le Q&A n'est pas disponible : modèles RAG
non installés ou cours non indexé. », avec la slide courante en source. L'indisponibilité est mémorisée :
les requêtes suivantes ne retentent pas le chargement. Après avoir téléchargé les modèles ou indexé le
cours, redémarrer l'API. Lue à la construction du graphe (premier appel).

### Streaming SSE (`/slide/{id}/explain`, `/ask`)

Avec `?stream=1` ou `Accept: text/event-stream` (envoyé par le frontend), format lu par `lireReponseAgent`
(`frontend/src/api.ts`) ; sans, réponse JSON `AgentResponse` comme avant.

```
event: progression
data: {"etape": "debut", "message": "Demande reçue, préparation du contexte…"}

event: progression
data: {"etape": "generation", "message": "…", "agent": "explainer"}

event: progression
data: {"etape": "verification", "message": "Le Critic vérifie la réponse sur les slides…"}   (API_CRITIC=on)

event: progression                          (si le Critic renvoie la réponse à l'agent)
data: {"etape": "correction", "iteration": 1, "score_fidelite": 0.4, "message": "…"}

: ping                                      (toutes les 15 s pendant une longue génération)

data: {"agent": "explainer", "reponse": "…", "sources": […], "score_fidelite": 0.9}

data: [DONE]
```

Les événements `progression` n'ont ni `token` ni `reponse` : le frontend les ignore pour le texte affiché.
Les agents produisent du JSON structuré : il n'y a pas de streaming jeton par jeton.

### Erreurs

| Cas | JSON | SSE |
|---|---|---|
| cours / slide inconnu | 404 | 404 (avant l'ouverture du flux) |
| requête invalide | 422 | 422 |
| LLM au-delà de `API_TIMEOUT_LLM` (`.env`, 400 s par défaut) | 504 | `event: erreur` `{"statut": 504}` puis réponse de secours |
| `LLMIndisponible` remontée jusqu'à l'API | 200, réponse de secours (texte de la slide, cité) | `event: erreur` `{"statut": 503}` puis réponse de secours |

Une génération abandonnée par timeout se termine en arrière-plan (llama.cpp ne s'interrompt pas) ;
`agents/llm.py` sérialise les appels, la requête suivante attend donc la fin de la précédente.
Chaque requête est loguée (logger `api`) avec son temps de réponse, aussi renvoyé dans l'en-tête `X-Temps-Reponse`.
CORS : ports 3000, 5173, 8501 et 8765 (page `depot.html`).
