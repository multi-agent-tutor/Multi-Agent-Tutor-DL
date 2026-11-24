# docs/maquettes/

Responsable : Ons — tâche D2 (voir la répartition des tâches). À livrer à Ali avant A5 (frontend).

Maquettes HTML/CSS cliquables, à ouvrir dans un navigateur (double-clic sur le fichier) :

| Fichier | Page |
|---|---|
| `accueil/index.html` | Landing (vitrine) : présentation animée, tuteur jouable, boutons « Déposer mon cours » |
| `depot.html` | Page Dépôt : glisser-déposer PPTX/PDF, analyse en 4 étapes ; appelle `POST /upload` (A1) si l'API tourne sur `localhost:8000`, sinon mode démo |
| `cours.html` | Page Cours |
| `quiz.html` | Page Quiz (QCM + flashcards) |
| `maquettes.css` | Styles communs |

Direction visuelle « bibliothèque calme » : fond papier chaud, encre bleu nuit (`#1c2541`), accent ambre (`#d99a2b`),
titres en serif **Fraunces**, texte en **Inter** (Google Fonts), cartes arrondies, icônes au trait.
Toutes les couleurs sont des variables CSS en tête de `maquettes.css` : à aligner sur la charte de Both (D1, `docs/charte.md`).
Les contenus sont des exemples tirés du cours `ml_gradient_stochastique_esprit_fr`.

## Page Cours

| Zone | Contenu | Données (T0) / API (A1) | Tâche |
|---|---|---|---|
| Barre du haut | titre du cours, onglets Cours / Quiz | `Course.titre` — `GET /course/{id}` | A5 |
| Gauche | slide courante (PNG), navigation précédente / suivante, miniatures | `Slide.image_rendu`, `Slide.numero` | H1, A5 |
| Droite | explication en 3 niveaux (Débutant / Intermédiaire / Avancé) : idée clé, explication, exemple, lien avec la slide précédente, à retenir | `GET /slide/{id}/explain?niveau=…` → `AgentResponse` | O2 |
| Droite (outils) | 🔊 Écouter, Quiz sur cette slide, Ressources | TTS, `GET /quiz`, `GET /resources` | A7, A2, A4 |
| Bas | chat Q&A, réponses avec liens cliquables `[Slide N]`, suggestions de questions | `POST /ask` → `AgentResponse.sources` | B3, A3 |

Comportements :
- changer de slide met à jour `TutorState.slide_courante` et recharge l'explication ;
- changer de niveau met à jour `TutorState.niveau` ;
- un clic sur `[Slide N]` affiche la slide N à gauche ;
- formules rendues avec KaTeX (A5).

## Page Quiz

| Zone | Contenu | Données / API | Tâche |
|---|---|---|---|
| En-tête | n° de question, niveau de Bloom, bascule QCM / Flashcards, barre de progression | `GET /quiz` | A2, A5 |
| QCM | une question à la fois, 4 choix ; feedback immédiat (bonne réponse en vert, erreur en rouge, explication, slide source) | sortie JSON de l'agent Quiz | A2 |
| Score final | score, questions à revoir avec leur slide, recommencer, export Anki | — | A6 |
| Flashcards | recto / verso au clic, auto-évaluation (À revoir / Difficile / Bien / Facile) | SM-2 | A6 |

Le Critic (O3) vérifie en amont qu'une question n'a qu'une seule bonne réponse.
