# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Frontend en **React (Vite)** (tâche A5, Ali), branché sur une API **FastAPI** (A1/A3) et un graphe d'agents **LangGraph** (O1).
Les maquettes de `docs/maquettes/` sont en HTML/CSS/JS statique et servent de référence visuelle pour les composants React.

## Users

- **Utilisateur principal : l'étudiant** qui dépose les slides d'un cours (PPTX ou PDF) et veut le comprendre seul,
  slide par slide : explication adaptée à son niveau, questions avec réponses sourcées, quiz et flashcards pour réviser.
- **Public d'évaluation : le jury d'enseignants** de la soutenance. L'interface doit être convaincante lors de la démo
  (démo de bout en bout sur 2 cours, tâche O5) : sérieuse, claire, crédible pour des enseignants.

## Product Purpose

Tuteur multi-agent « à la NotebookLM » pour supports de cours : à partir d'un PPTX ou d'un PDF, il produit pour chaque slide
une explication pédagogique (3 niveaux), répond aux questions en citant les slides `[Slide N]`, génère quiz et flashcards,
et propose des ressources complémentaires. Réussite : l'étudiant comprend et retient le cours ; les réponses sont fidèles au cours.

## Positioning

Le tuteur reste **ancré dans le cours de l'étudiant** : chaque réponse cite ses slides sources, un agent Critic vérifie
la fidélité au cours, et le Q&A refuse de répondre quand l'information n'est pas dans le cours.
L'explication suit la slide courante, ses voisines et ses prérequis (carte du cours), à trois niveaux.

## Operating Context

- Parcours : déposer un cours → naviguer slide par slide avec l'explication → poser des questions → se tester (quiz, flashcards) → réviser (SM-2, export Anki).
- Contenus : slides avec schémas, formules (rendues en LaTeX/KaTeX), figures décrites par un VLM, slides scannées (OCR).
- Corpus de test réel : 47 cours (`data/corpus/`), noyaux `noyau_ons.json` et `noyau_both.json` ; 160 questions d'évaluation (`eval/dataset.json`).

## Capabilities and Constraints

- Agents : Router, Explainer (3 niveaux : débutant, intermédiaire, avancé), Q&A avec citations, Quiz/Flashcards (niveaux de Bloom), Resources, Critic.
- API prévue : `POST /upload`, `GET /course/{id}`, `GET /slide/{id}/explain`, `POST /ask`, `GET /quiz`, `GET /resources` ; streaming SSE pour l'Explainer et le Q&A.
- Narration audio (TTS) et sélecteur de langue.
- Schéma de données commun : `docs/schema.md` (T0).
- Charte graphique (logo, couleurs, police, boutons) : tâche D1 de Both, **pas encore livrée** (`docs/charte.md`).

## Brand Commitments

- Nom : **Multi-Agent Tutor** (« Multi-Agent » en bleu marine, « Tutor » en bleu roi encadré de deux traits).
- **Logo officiel, contrainte binding** (Ons, 2026-11-19 : « le logo de l'app est celui-là, tu ne dois pas sortir de ce thème ») :
  mascotte robot souriante, contour bleu marine épais, visière sombre aux yeux en arc bleu, toque de diplômé bleue avec gland or,
  deux disques bleu roi qui tiennent des pictogrammes blancs (groupe, livre), traits d'« éclat » autour, livre ouvert bleu,
  fond blanc, lettrage sans-serif arrondi et gras. Palette du logo : bleu roi, bleu clair, bleu marine, or (accent unique), blanc.
  Fichier : `docs/maquettes/img/logo.jpg` (copie de travail ; l'original relève de D1, Both).
- Toute interface reste dans ce thème : fond clair, couleurs du logo, mascotte comme visage du tuteur.
- Ton : pédagogique, encourageant, précis ; jamais d'affirmation non appuyée par le cours.

## Evidence on Hand

- Corpus de cours réels et inventaires : `data/corpus/`.
- Jeu d'évaluation : `eval/dataset.json` (160 questions relues).
- Benchmark RAGAS avant/après : à venir (B4) ; aucun chiffre de performance ne doit être affiché avant.
- Pas de témoignages ni d'utilisateurs réels : ne pas en inventer.

## Product Principles

1. **Ancré dans le cours** : chaque contenu généré renvoie à ses slides sources.
2. **Le niveau de l'étudiant d'abord** : la même slide s'explique du débutant à l'avancé.
3. **Comprendre puis vérifier** : chaque explication mène naturellement à une question ou un quiz.
4. **Honnête** : dire « ce n'est pas dans le cours » plutôt qu'inventer.

## Accessibility & Inclusion

- Interface en **français, anglais et arabe** : l'arabe impose une mise en page **de droite à gauche (RTL)** dès les maquettes.
- Formules lisibles (LaTeX/KaTeX), narration audio disponible pour l'explication.
