---
version: 1
slug: "docs-maquettes-cours-html"
primary_target: "docs/maquettes/cours.html"
related_targets: ["docs/maquettes/quiz.html","docs/maquettes/maquettes.css"]
---

# Surface brief — maquettes Cours et Quiz (D2)

Scope: `docs/maquettes/cours.html`, `docs/maquettes/quiz.html`, `docs/maquettes/maquettes.css` (référence visuelle pour le frontend React d'Ali, A5).
Mode: operate.
Audience et tâche : l'étudiant qui travaille un cours slide par slide (explication à 3 niveaux, Q&A sourcé), puis se teste (QCM, flashcards) ; le jury d'enseignants voit la démo.
Contraintes : FR/EN/AR avec mise en page RTL ; formules lisibles ; citations `[Slide N]` partout ; aucun chiffre de performance inventé ; thème du logo obligatoire.

## Direction contract

THESIS: Le tuteur a un visage : la mascotte robot du logo accompagne l'étudiant, réfléchit quand l'agent génère, se réjouit d'une bonne réponse. Refuse le tableau de bord SaaS anonyme à cartes grises.

OWN-WORLD: Le monde du logo : fond blanc légèrement bleuté, bleu roi pour l'action et les agents, bleu clair pour les zones douces, bleu marine pour le texte et les contours épais arrondis, or réservé à l'unique accent (état actif, « à retenir »). Disques bleu roi qui portent un pictogramme blanc = avatars des agents. Traits d'éclat du logo = retour positif. Titres en sans-serif arrondi gras (Nunito), lecture en Atkinson Hyperlegible.

STORY: L'étudiant voit la slide et son explication côte à côte, change de niveau (la mascotte réfléchit puis répond), clique une source [Slide N] qui l'amène à la slide, pose une question et reçoit une réponse sourcée ou un refus honnête, puis se teste ; la mascotte réagit à chaque réponse.

FIRST VIEWPORT: Barre du haut (logo mascotte + nom, cours, onglets Cours/Quiz, FR/EN/AR). Gauche ~55 % : slide encadrée, navigation, bande des slides avec points de maîtrise. Droite ~45 % : panneau Explication avec la mascotte, sélecteur de niveau, idée clé, formule soulignée, encadré or « à retenir », action principale « Me tester ».

FORM: seed:a2b555d41f45f0d0 — monde remplacé par l'épinglage du logo par l'utilisatrice : « le logo de l'app est celui-là, tu ne dois pas sortir de ce thème de logo » ; « je veux un travail créatif interactif ». Le tirage précédent (seed:a2b555d41f45f0d0, tableau de l'amphi) est remplacé ; restent de lui la topologie, les rôles de couleur fixes par agent, les sources cerclées, les métadonnées tabulaires et le mouvement réduit respecté. Signature : la mascotte à états (réfléchit / contente / oups) et les traits d'éclat du logo quand l'étudiant réussit.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Open decisions
- Logo définitif et charte (D1, Both) : les tokens de `maquettes.css` s'aligneront sur `docs/charte.md`.
