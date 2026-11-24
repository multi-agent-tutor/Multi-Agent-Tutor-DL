# prompts/

Responsable : Ons — tâches O2, O4 (voir la répartition des tâches).

| Fichier | Agent | Sections |
|---|---|---|
| `explainer.md` | Explainer (O2, `agents/explainer.py`) | `Commun` + un niveau : `Débutant`, `Intermédiaire`, `Avancé` |
| `critic.md` | Critic (O3, `agents/critic.py`) | `Fidélité`, `QCM` |
| `quiz.md` | Quiz (A2, `agents/quiz.py`) | `QCM`, `Flashcards` |

Chaque section `## ...` est (une partie d') un prompt système ; le contenu des slides va dans
le message utilisateur. Le format de sortie est imposé par un modèle Pydantic dans l'agent
(grammaire llama.cpp), pas par le prompt.
