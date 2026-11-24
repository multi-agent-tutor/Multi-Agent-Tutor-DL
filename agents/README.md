# agents/

Responsable : Ons, Both, Ali — tâches O1-O3, B3, A2, A4, A6 (voir la répartition des tâches).

## O1 — Graphe LangGraph (`graph.py`)

```
START → router → explainer | qa | quiz | resources → END        (sans Critic)
```

- **État partagé** : `TutorState` (`schemas/models.py`, T0) : `course_id`, `slide_courante`, `niveau`,
  `langue_reponse`, `historique`, `question`, `intention`, `reponse`, `sources`, `iterations_critic`.
- **Router** : garde l'`intention` si l'API l'impose (ex. `GET /slide/{id}/explain` → `expliquer`),
  sinon la déduit de la question par mots-clés FR/EN (`classer_intention`, provisoire, remplaçable par un LLM).
  Sans question : `expliquer`.
- **Agents** : des bouchons renvoient une réponse fixe `[agent] … [Slide N]`, une source et l'historique.

### Brancher son agent (Both, Ali)

Un agent est une fonction `(TutorState) -> dict` qui renvoie les champs modifiés :

```python
from agents.graph import construire_graphe, executer
from schemas import Source, TutorState

def agent_qa(state: TutorState) -> dict:
    passages = search(state.question, state.course_id, k=5)      # rag/ (B2)
    return {"reponse": "…", "sources": [Source(course_id=state.course_id, numero=3)]}

graphe = construire_graphe({"question": agent_qa})              # les autres restent des bouchons
final = executer(TutorState(course_id="ml_x_fr", slide_courante=3, question="Pourquoi ?"), graphe)
```

| Intention | Nœud | Responsable |
|---|---|---|
| `expliquer` | `explainer` | Ons (O2) |
| `question` | `qa` | Both (B3) |
| `quiz` | `quiz` | Ali (A2) |
| `ressources` | `resources` | Ali (A4) |

Tests : `tests/test_graph.py`.

## O2 — Explainer (`explainer.py`)

Explique une slide au niveau de l'étudiant (`prompts/explainer.md` : `Commun` + `Débutant` |
`Intermédiaire` | `Avancé`), dans l'ordre idée clé → explication → exemple → lien avec la slide
précédente → à retenir, avec les citations [Slide N]. Contexte : la slide, ses voisines N-1 / N+1,
ses figures et formules, ses prérequis (`get_prerequisites` de H3, Ghayth ; repli sur les concepts voisins sans carte du cours). Sans LLM :
repli extractif tiré de la slide. Tests : `tests/test_explainer.py`.

## O3 — Critic et boucle de correction (`critic.py`)

```
START → router → explainer | qa ⇄ critic → END
               → quiz | resources → END
```

- `critic_agent` relit les slides sources et juge chaque affirmation de la réponse
  (`prompts/critic.md`, section `Fidélité` ; sans LLM, repli lexical). Il remplit
  `score_fidelite` (part des affirmations appuyées) et `corrections` (affirmations non appuyées).
- Sous le seuil (`CRITIC_SEUIL`, 0,7 par défaut), la réponse repart vers l'agent d'origine avec les
  `corrections` (2 fois au plus, `iterations_critic`) ; ensuite elle est livrée avec un avertissement.
  L'Explainer ajoute les corrections à son prompt ; l'agent Q&A peut faire de même avec `state.corrections`.
- Quiz : `verifier_qcm` contrôle une seule bonne réponse, juste, et des distracteurs faux ;
  `quiz_verifie_agent` enveloppe l'agent Quiz (A2) et écarte les QCM rejetés.

```python
from agents.critic import critic_agent, quiz_verifie_agent
from agents.explainer import explainer_agent

graphe = construire_graphe({"expliquer": explainer_agent, "quiz": quiz_verifie_agent},
                           critic=critic_agent)
```

Tests : `tests/test_critic.py`.

## B3 — Agent Q&A avec citations (`qa.py`)

```python
from agents.graph import construire_graphe
from agents.qa import AgentQA
from rag.rerank import BgeReranker, RechercheReranked
from rag.search import RechercheHybride
from rag.store import BgeM3Embedder, VectorStore

store = VectorStore(BgeM3Embedder(), chemin="qdrant_storage")       # cours indexés par python -m rag.index
agent = AgentQA(RechercheReranked(RechercheHybride(store), BgeReranker()))
graphe = construire_graphe({"question": agent})
```

- Recherche B2 (hybride top-20 → reranker top-5) dans le cours courant ; seuls les passages au score ≥ 0,01 (réglable : `QA_SEUIL` dans `.env`) sont gardés ; ce seuil écarte le hors-sujet évident, et le LLM refuse si les passages ne permettent pas de répondre.
- Aucun passage pertinent : réponse « L'information n'est pas dans le cours. » (`eval.schema.REPONSE_HORS_COURS`), sans appeler le LLM.
- Sinon, le LLM local (A0) répond à partir des seuls passages, en citant `[Slide N]` ; les citations de slides absentes des passages sont retirées ; une réponse sans citation reçoit celle du meilleur passage.
- LLM indisponible (`LLMIndisponible`) : repli extractif, le passage le plus pertinent est renvoyé avec sa citation.
- Démo : `python -m agents.qa "Qu'est-ce que la fonction de coût ?"` (cours d'exemple T0, modèles locaux). Tests : `tests/test_qa.py` (LLM fake).
