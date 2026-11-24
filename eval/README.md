# eval/

Responsable : Ons + Both — tâches C2, B4 (voir la répartition des tâches).

## C2 — Jeu d'évaluation (`dataset.json`)

Format défini dans `schema.py` (`QuestionEval`, `JeuEvaluation`), vérifié par `tests/test_eval_dataset.py`.

| Champ | Description |
|---|---|
| `id` | `<course_id>__qNN` |
| `course_id` | cours du corpus (présent dans `data/corpus/inventaire_*.csv`) |
| `auteur` | `ons` ou `both` |
| `type` | `factuelle`, `comprehension`, `figure`, `hors_cours` |
| `langue` | `fr` ou `en` (langue du cours) |
| `question`, `reponse_reference` | question et réponse attendue, tirée du cours |
| `slides` | numéros des slides sources ; vide pour `hors_cours` |
| `relu_par` | relecture croisée : l'autre membre (`ons` ↔ `both`) |

Règles :
- ~10 questions par cours du noyau (`data/corpus/noyau_ons.json`, noyau de Both à venir) ;
- les 4 types dans chaque cours ;
- `hors_cours` : réponse de référence = « L'information n'est pas dans le cours. » (refus attendu, B3) ;
- les slides citées doivent exister dans le cours.

Avancement :
- **Ons : 100 questions** sur les 10 cours du noyau (`noyau_ons.json`), 50 FR / 50 EN :
  46 factuelles, 34 de compréhension, 10 sur une figure, 10 hors cours. À relire par Both (`relu_par`).
- Les questions « figure » s'appuient sur le texte des slides : à vérifier sur les images lors de la relecture.
- Pour les cours EN, la réponse attendue hors cours reste la phrase de refus commune (en français).
- **Both** : ~60 questions sur son noyau, à venir.

## B4 — Benchmark avant / après (`run_eval.py`, `metriques.py`)

Compare deux versions de l'agent Q&R sur le jeu C2 :

- **avant** : recherche dense seule (bge-m3), sans reranker, sans Critic ;
- **après** : hybride (bge-m3 + BM25, RRF) + reranker bge-reranker-v2-m3 + agent Q&R (B3) + Critic (O3).

Métriques (définitions RAGAS, calculées en local car la bibliothèque RAGAS appelle une API par défaut, règle v2) :
context precision (slides de référence de C2, sans LLM), faithfulness (juge = LLM local, procédure du Critic),
answer relevancy (questions générées depuis la réponse + cosinus bge-m3), refus correct / faux refus, latence.

```bash
python -m eval.run_eval --factice --limite 8   # test de bout en bout sans modèle
python -m eval.run_eval --limite 24            # échantillon : 6 questions par type, 16 cours
python -m eval.run_eval                        # les 160 questions (plusieurs heures sur CPU)
python -m eval.run_eval --juge lexical --sans-questions-generees   # plus rapide, sans juge LLM
```

Prérequis : cours ingérés par H1 dans `data/processed/<course_id>/course.json`.
Sorties : `eval/results.md` (tableaux), `eval/results.svg` (graphique), `eval/results_details.jsonl` (détail par question).
