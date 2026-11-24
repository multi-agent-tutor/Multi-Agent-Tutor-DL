---
name: Multi-Agent Tutor
description: Tuteur multi-agent pour supports de cours, dans le monde du logo et de la charte D1 (bleu roi, marine, jaune du pompon, Inter).
colors:
  bleu: "#2563EB"
  bleu-fonce: "#1D4ED8"
  bleu-clair: "#4C8AFD"
  bleu-ciel: "#EFF5FF"
  bleu-ciel-2: "#DBEAFE"
  or: "#FBBF24"
  or-doux: "#FEF3C7"
  or-texte: "#78350F"
  marine: "#0B1A45"
  marine-2: "#334155"
  gris: "#475569"
  filet: "#E2E8F0"
  filet-fort: "#CBD5E1"
  fond: "#F8FAFC"
  surface: "#FFFFFF"
  vert: "#15803D"
  vert-doux: "#DCFCE7"
  rouge: "#DC2626"
  rouge-doux: "#FEE2E2"
  marine-surface: "#182851"
  sur-marine: "#C7D2FE"
typography:
  display:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "50px"
    fontWeight: 700
    lineHeight: 1
  headline:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "27px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  lead:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1
  meta:
    fontFamily: "Inter, Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.5
  math:
    fontFamily: "STIX Two Text, Noto Sans Math, serif"
    fontSize: "23px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  pill: "999px"
  lg: "18px"
  md: "16px"
  vignette: "14px"
  sm: "12px"
  segment: "10px"
  bouton: "8px"
  citation: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.bleu}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.bouton}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.bleu-fonce}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.bleu}"
    typography: "{typography.label}"
    rounded: "{rounded.bouton}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.bleu-ciel}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.gris}"
    typography: "{typography.label}"
    rounded: "{rounded.bouton}"
    padding: "0 16px"
    height: "40px"
  source-chip:
    backgroundColor: "{colors.or}"
    textColor: "{colors.marine}"
    rounded: "{rounded.citation}"
    padding: "0 8px"
  agent-disc:
    backgroundColor: "{colors.bleu}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    size: "32px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.marine}"
    rounded: "{rounded.lg}"
    padding: "22px 24px"
  callout-retenir:
    backgroundColor: "{colors.or-doux}"
    textColor: "{colors.marine}"
    rounded: "{rounded.sm}"
    padding: "14px 16px"
  bubble-tutor:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.marine}"
    rounded: "{rounded.lg}"
    padding: "10px 14px"
  bubble-student:
    backgroundColor: "{colors.bleu-ciel-2}"
    textColor: "{colors.marine}"
    rounded: "{rounded.lg}"
    padding: "10px 14px"
  level-selector:
    backgroundColor: "{colors.bleu-ciel}"
    textColor: "{colors.marine-2}"
    rounded: "{rounded.segment}"
    padding: "4px"
  level-selector-active:
    backgroundColor: "{colors.bleu}"
    textColor: "{colors.surface}"
  choice:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.marine}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
    height: "56px"
  choice-correct:
    backgroundColor: "{colors.vert-doux}"
  choice-wrong:
    backgroundColor: "{colors.rouge-doux}"
  tabs:
    backgroundColor: "{colors.bleu-ciel}"
    textColor: "{colors.marine-2}"
    rounded: "{rounded.pill}"
    padding: "4px"
  tabs-active:
    backgroundColor: "{colors.bleu}"
    textColor: "{colors.surface}"
  input-question:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.marine}"
    rounded: "{rounded.pill}"
    padding: "5px 5px 5px 18px"
---

# Design System: Multi-Agent Tutor

> Système relevé sur les maquettes livrées (`docs/maquettes/cours.html`, `quiz.html`, `maquettes.css`, `maquettes.js`).
> **Source des valeurs de couleur, de police et de bouton : la charte graphique D1 de Both (`docs/charte.md`, branche
> `both`).** Elle est contraignante pour l'équipe : les variables `--mat-*` de `maquettes.css` en sont la copie exacte,
> et les jetons ci-dessus en dérivent. Les maquettes HTML/CSS/JS statiques sont la référence visuelle du frontend React
> (Vite, tâche A5) : les jetons de `:root` deviennent les variables CSS du thème, la mascotte SVG de `maquettes.js`
> devient un composant à états. Toute nouvelle valeur de couleur, de police ou de bouton passe par la charte.

## Overview

**Creative North Star: "Le tuteur a un visage"**

Le système sort du logo officiel (contrainte binding de PRODUCT.md) et de la charte D1 qui en fixe les valeurs : un robot
tuteur à toque de diplômé, contours bleu marine, bleu roi pour l'action, jaune du pompon pour ce qui renvoie au cours.
L'en-tête porte le logo lui-même (`docs/maquettes/img/logo-icone.png`, copie de `assets/logo-icone.png` de la charte),
sans recoloration ni ombre. La mascotte SVG redessinée reste le visage animé du tuteur : elle change d'état quand un agent
travaille ou quand l'étudiant répond (tête de panneau Explication, fil de questions, réactions du quiz) ; les disques bleu
roi deviennent les avatars des agents ; l'éclat devient le retour positif.

La densité est celle d'un outil d'étude, pas d'une page vitrine : fond gris très clair, panneaux blancs posés dessus,
boutons nets à 8px de rayon, rails et pilules pour la navigation, une seule famille (Inter) pour toute l'interface et une
vraie serif mathématique pour les formules. Le ton visuel est encourageant et clair, crédible devant un jury
d'enseignants. L'interface est trilingue (FR / EN / AR) et passe entièrement en RTL en arabe.

Rejet confirmé : le tableau de bord SaaS anonyme à cartes grises. Le monde précédemment tiré (« tableau de l'amphi »,
sombre) a été remplacé par l'épinglage du logo et ne fait pas partie du système.

Deux registres partagent ces valeurs. **L'outil** (pages Cours et Quiz, puis le frontend React) reste clair, dense et
calme : c'est la règle par défaut de tout ce document. **La vitrine** (landing `docs/maquettes/accueil/`, demandée
« créative, marketing, animée ») a le droit de parler plus fort : bandes marine, dégradé vivant, très grands titres,
mouvement d'auteur. Les exceptions de la vitrine sont listées dans « La landing (vitrine) » ; elles ne s'appliquent
jamais à l'outil.

**Key Characteristics:**
- Les valeurs de la charte D1 (Both, `docs/charte.md`) reprises telles quelles dans les variables `--mat-*`.
- Le logo officiel en en-tête ; la mascotte SVG à quatre états (sourit, réfléchit, contente, oups) comme visage du tuteur.
- Bleu roi pour l'action, les agents et le segment actif ; marine pour le texte et les contours épais ; jaune du pompon pour les citations `[Slide N]` et « à retenir ».
- Inter auto-hébergée pour toute l'interface (700 titres, 600 boutons, 400 texte) ; STIX Two Text pour les formules.
- Chaque contenu généré porte sa source `[Slide N]` sous forme de pastille jaune cliquable.
- Mouvement court et doux (ease-out), réduit mais pas supprimé sous `prefers-reduced-motion`.

## Colors

La palette de la charte D1, tirée du logo : un bleu roi franc avec son survol et un bleu clair, un marine presque noir
pour l'encre, le jaune du pompon, deux couleurs de verdict, et des neutres ardoise. Quelques teintes pâles sont dérivées
dans le build pour les grands aplats ; elles ne remplacent jamais une valeur de la charte.

### Primary
- **Bleu roi** (bleu, `--mat-primaire`) : bouton principal, liens, onglet actif, segment actif du sélecteur de niveau,
  avatars d'agent, trait tracé sous la formule clé, verso de la flashcard, score final, contour de focus clavier.
- **Bleu foncé** (bleu-fonce, `--mat-primaire-survol`) : survol du bouton principal, titre de la slide, niveau de Bloom.
- **Bleu clair** (bleu-clair, `--mat-secondaire`) : point « vue » de la bande des slides, survol des choix, des
  vignettes et des suggestions, disque de l'agent Q&A. Jamais de texte blanc dessus (contraste insuffisant, charte).
- **Bleu très clair** (bleu-ciel-2, `--mat-fond-clair`) : bulle de l'étudiant, étapes à venir du quiz, halo de focus du
  champ de question, sélection de texte.
- **Bleu ciel** (bleu-ciel, teinte dérivée de `--mat-fond-clair`) : grands aplats doux : rails des onglets et
  sélecteurs, survol des boutons secondaires, disque-lettre des choix, fond de formule sur la slide.

### Secondary
- **Jaune du pompon** (or, `--mat-accent`) : pastille de citation `[Slide N]`, bordure et disque de l'encadré « À
  retenir », étape courante du quiz, halo de repérage autour de la slide quand une source y mène. Toujours du texte
  marine dessus, jamais blanc.
- **Jaune pâle** (or-doux, dérivé) : fond de l'encadré « À retenir » et de la vignette de la slide courante.
- **Ambre encre** (or-texte, dérivé) : titre de l'encadré « À retenir » (le jaune pur n'est pas lisible en texte).

### Tertiary
- **Vert succès** (vert, `--mat-succes`) / **vert pâle** (vert-doux, dérivé) : bonne réponse, point « testée », badge
  « Vérifié par le Critic ».
- **Rouge erreur** (rouge, `--mat-erreur`) / **rouge pâle** (rouge-doux, dérivé) : mauvaise réponse uniquement.

### Neutral
- **Bleu marine** (marine, `--mat-texte`) : texte principal, contours épais, langue active, contour de la mascotte.
- **Ardoise appuyée** (marine-2, dérivé) : texte des paragraphes d'explication, libellés inactifs des rails, compteurs.
- **Ardoise** (gris, `--mat-texte-secondaire`) : métadonnées, légendes, placeholders, texte du bouton discret.
- **Gris clair** (filet, `--mat-bordure`) : séparateurs, bordures des panneaux, des choix, des vignettes, bulle du tuteur.
- **Gris appuyé** (filet-fort, dérivé) : bordure du champ de question au repos, pointillé du refus honnête, point de
  maîtrise vide, barre de défilement.
- **Marine surface** (marine-surface, dérivé de `--mat-texte`) et **bleu pâle sur marine** (sur-marine, dérivé de
  `--mat-fond-clair`) : réservés aux bandes marine de la landing (boutons de demande, texte secondaire).
- **Fond** (fond, `--mat-fond`) : fond de page. **Surface** (surface, `--mat-surface`) : panneaux, bouton secondaire,
  cadre de slide, bulle du tuteur.

### Named Rules
**The Charter Rule.** Toute couleur vient de `docs/charte.md` (variables `--mat-*`) ou en est une teinte pâle dérivée
pour un aplat. Une nouvelle teinte passe par la charte D1, pas par la maquette.

**The Pompon Rule.** Le jaune renvoie au cours : citations `[Slide N]`, ce qu'il faut retenir, l'endroit où l'on est.
Jamais un bouton d'action, jamais une décoration, jamais de texte blanc dessus.

**The Verdict Colors Rule.** Le vert et le rouge n'apparaissent qu'en réponse à un acte de l'étudiant (réponse au quiz,
vérification par le Critic), et toujours avec une icône coche ou croix : jamais la couleur seule, jamais au repos.

## Typography

**Display Font:** Inter 700 (avec Noto Sans Arabic, Segoe UI, Roboto, Arial, sans-serif)
**Body Font:** Inter 400 (même pile)
**Label/Mono Font:** STIX Two Text pour les formules (avec Noto Sans Math, serif)

**Character:** Une seule voix d'interface, Inter, imposée par la charte D1 : la hiérarchie se fait par la graisse (700
titres, 600 boutons et citations, 400 texte) et la taille, pas par un changement de famille. Les formules ont leur
propre voix, une vraie serif mathématique. Toutes les polices sont auto-hébergées (`docs/maquettes/fonts/`, aucun
service en ligne). En arabe, titres et texte basculent sur Noto Sans Arabic.

### Hierarchy
- **Display** (700, 50px, 1) : le score final du quiz, seul.
- **Headline** (700, 27px cours / 30px quiz, 1.2, -0.01em, `text-wrap: balance`) : titre de page. 22–24px sous 980px.
  La charte indique 28px ; le build arrondit à 27 et 30.
- **Title** (700, 21px tête de panneau ; 24px question de quiz à 1.35 ; 23px titre du score) : la charte indique 20px
  pour un titre de section.
- **Lead** (700, 22px, 1.35) : l'idée clé de l'explication, une phrase.
- **Body** (400, 16px, 1.5, chiffres tabulaires) : explications, bulles, choix (16.5px). Paragraphes à 68ch maximum.
- **Label** (600, 15px) : boutons et citations (0.85em). Les rails, onglets, sélecteurs, compteurs et noms d'agent sont
  en 700 (13–15px). Les titres de bloc (« En détail ») en 700 13.5px bleu.
- **Meta** (400, 13.5–14.5px, ardoise) : position dans le cours, sous-titres, légende, compteurs.
- **Math** (STIX Two Text 400, 23px formule clé ; 28px verso de flashcard ; 17–21px sur la slide).

### Named Rules
**The One Family Rule.** Toute l'interface est en Inter (charte D1) ; on hiérarchise par la graisse et la taille. La
note « police trop répandue » est acceptée parce que la charte l'impose.

**The Real Math Rule.** Une formule est toujours en STIX Two Text (KaTeX en React), jamais en police d'interface.

## Layout

- **Page Cours** : grille deux colonnes `11fr / 9fr` (environ 55 / 45), largeur max 1440px, marges et gouttière de
  28px. À gauche, la colonne de la slide est collante (`top: 92px`) : titre, slide encadrée en 16:9, navigation, bande
  des slides, légende. À droite : panneau Explication puis panneau Questions.
- **Page Quiz** : une colonne de 860px max, `34px 24px 52px` de marge, pile espacée de 20px.
- **Barre du haut** collante, blanche translucide (90 %, flou 10px), filet en bas : logo et nom, cours actuel, onglets
  Cours/Quiz poussés à droite, sélecteur FR/EN/AR.
- **Rythme** : pas de 4px ; espacements usuels 8, 12, 16, 20, 24, 28. Panneaux à 22–24px de marge interne
  (18px sur mobile), 30px pour la carte de question.
- **Sous 980px** : une colonne ; l'ordre devient titre, slide, navigation, bande, légende, explication, questions ; la
  slide perd son ratio fixe ; une barre d'actions fixe en bas (« Me tester », « Demander ») garde l'action principale
  à portée de pouce, avec `safe-area-inset-bottom`.
- **Sous 640px** : la barre du haut passe sur deux lignes (onglets en pleine largeur) et défile avec la page ;
  « Envoyer » et les flèches de navigation deviennent des boutons icône de 44px avec libellé masqué accessible.
- **RTL** : propriétés logiques partout (`inline-start`, `block-end`) ; les icônes directionnelles portent la classe
  miroir et se retournent en arabe.

## Elevation & Depth

Système hybride et léger : des panneaux blancs posés sur le fond, séparés par un filet de 1px et une ombre diffuse
teintée de bleu. La profondeur vient d'abord du contraste blanc / fond et des contours marine, ensuite des ombres. Les
éléments actifs (bouton principal, onglet courant, segment de niveau actif) portent une ombre colorée bleue.

### Shadow Vocabulary
- **Ombre de panneau** (`box-shadow: 0 1px 2px rgba(14,26,61,.05), 0 12px 32px rgba(35,80,216,.08)`) : panneaux,
  cadre de slide.
- **Ombre forte** (`box-shadow: 0 18px 44px rgba(35,80,216,.18)`) : la flashcard, seul objet qu'on manipule.
- **Lueur d'action** (`box-shadow: 0 4px 12px rgba(37,99,235,.25)`) : bouton principal ; `rgba(35,80,216,.3)` pour
  l'onglet actif, `0 2px 8px rgba(37,99,235,.3)` pour le segment de niveau actif.
- **Curseur blanc** (`box-shadow: 0 2px 8px rgba(14,26,61,.12)`) : option choisie du sélecteur de mode QCM / flashcards.

### Named Rules
**The Blue Shadow Rule.** Les ombres sont teintées de bleu, diffuses et basses. Pas d'ombre grise neutre, pas d'ombre
décalée dure, et jamais d'ombre sur le logo (charte).

## Shapes

Deux familles de formes. Les **contrôles d'action** sont nets : boutons à 8px (charte), citations à 6px, segments du
sélecteur de niveau à 7px dans un rail à 10px, contour de focus arrondi à 6px. La **navigation et les rails** gardent
la pilule (999px) : onglets, langues, sélecteur de mode, champ de question, suggestions, barres de progression. Les
avatars et pastilles sont des disques parfaits. Les conteneurs ont des coins larges : 18px pour les panneaux, la slide
encadrée et la flashcard ; 16px pour les choix de quiz, le retour et les boutons d'évaluation ; 14px pour les vignettes ;
12px pour l'encadré « À retenir ». Les bulles de dialogue ont 18px avec un coin réduit à 6px du côté de celui qui parle.
Le contour épais marine (2.5px, l'épaisseur des traits du logo) est réservé au cadre de la slide et à la flashcard ; le
champ de question porte la même épaisseur en gris appuyé ; les bordures ordinaires font 1–2px en gris clair.

## Components

### Buttons
Nets et sobres, aux valeurs de la charte D1.
- **Shape:** coins à 8px, 40px de haut minimum, 16px de marge horizontale, icône 20px et libellé Inter 600 15px.
- **Primary:** bleu roi, texte blanc, sans bordure, lueur d'action bleue. Un seul par zone.
- **Secondary:** surface blanche, bordure 1px bleu roi, texte bleu roi.
- **Ghost (discret):** transparent, sans bordure, texte ardoise.
- **Hover / Focus:** survol (seulement sur pointeur fin) vers bleu foncé pour le principal, bleu ciel pour le secondaire
  et le discret ; appui en `scale(.97)` sur 160ms ease-out ; focus clavier en contour 2px bleu roi décalé de 2px.
  Désactivé : opacité 50 %, curseur `not-allowed`.
- **Évaluation des flashcards:** boutons à 16px de rayon, 60px de haut, libellé et délai sur deux lignes.

### Chips
- **Citation `[Slide N]`:** pastille jaune du pompon, texte marine Inter 600 à 0.85em, coins 6px, dans le fil du texte ;
  un clic amène la slide et la fait clignoter d'un halo jaune (900ms) ; appui en `scale(.95)`.
- **Suggestions de questions:** pilules blanches à bordure gris clair 2px, texte ardoise appuyée ; survol bleu clair.

### Cards / Containers
- **Corner Style:** 18px.
- **Background:** surface blanche sur fond gris très clair.
- **Shadow Strategy:** ombre de panneau (voir Elevation & Depth).
- **Border:** gris clair 1px.
- **Internal Padding:** 22–24px ; 18px sous 980px.
- **Cadre de slide:** contour marine épais 2.5px, 10px de marge, slide intérieure à 10px de rayon.
- **Encadré « À retenir »:** jaune pâle, bordure jaune 2px, disque jaune à pictogramme marine, titre en ambre encre.

### Inputs / Fields
- **Style:** champ de question en pilule, contour gris appuyé 2.5px, bouton « Envoyer » principal logé dedans.
- **Focus:** le contour passe au bleu roi avec un halo bleu très clair de 4px (`:focus-within`).

### Navigation
- **Logo:** `img/logo-icone.png` à 44px dans la marque, suivi du nom Inter 700 18px (« Tutor » en bleu roi).
- **Onglets Cours / Quiz:** rail bleu ciel en pilule, 4px de marge ; onglet actif plein bleu roi, texte blanc, lueur
  bleue ; inactifs ardoise appuyée, survol blanc et bleu.
- **Langues:** groupe de pilules à bordure gris clair 1px ; langue active pleine marine, texte blanc.
- **Sélecteur de niveau (charte):** segmenté, rail bleu ciel à 10px de rayon et bordure gris clair ; le segment actif
  bleu roi (7px de rayon, texte blanc) glisse en 220ms ease-out d'un niveau à l'autre. Le sens s'inverse en RTL.
- **Sélecteur de mode (QCM / flashcards):** rail bleu ciel en pilule, option choisie en pilule blanche, texte bleu roi.
- **Bande des slides:** vignettes de 50×56px, bordure gris clair 2px, numéro et point de maîtrise dont la **taille et la
  couleur disent l'état** (5px gris, 7px bleu clair « vue », 9px bleu « comprise », 11px vert « testée ») ; slide
  courante en bordure marine sur jaune pâle ; fondu aux deux bords.

### Mascotte (composant signature)
Le visage animé du tuteur, redessiné du logo en SVG 100×100 (tête blanche à contour marine 3px, visière marine, yeux en
arc bleu clair, toque bleu roi, gland jaune). 46–58px en tête de panneau, dans le fil et dans le retour de quiz ; 76px
en tête de quiz ; 110px sur le score. Le logo image tient l'en-tête ; la mascotte ne le remplace pas là. Quatre états
via `data-etat` :
- **sourit** (repos) : yeux en arc.
- **réfléchit** (un agent génère) : les yeux deviennent trois points qui pulsent (900ms, décalés de 150ms) ; le
  contenu en cours de génération passe à 25 % d'opacité avec un flou de 2px.
- **contente** (bonne réponse) : la tête se redresse (`translateY(-2px) rotate(-4deg)`) et les trois traits d'éclat
  apparaissent en 360ms, échelonnés.
- **oups** (erreur, refus) : yeux en traits, tête penchée de 5°, retour au repos après 1.6s.

### Avatars d'agent
Disque de 32px plein (bleu roi par défaut ; bleu clair, marine ou vert selon l'agent) portant un pictogramme blanc de
17px, suivi du nom de l'agent en Inter 700 14px. Chaque agent garde sa couleur.

### Fil de questions
Bulle étudiant bleu très clair, texte marine, alignée à droite ; bulle tuteur blanche à bordure gris clair, à gauche,
précédée de la mascotte (charte : bulle tuteur blanche bordée, bulle utilisateur `#DBEAFE` à droite). Le refus honnête
(« ce n'est pas dans le cours ») est une bulle blanche à bordure pointillée gris appuyé 2px. Les tours entrent en 260ms
(fondu et 8px de montée) ; la réponse s'écrit avec un curseur bleu qui pulse, puis ses citations jaunes s'ajoutent.

### Quiz et flashcards
- **Choix:** ligne de 56px min, rayon 16px, bordure gris clair 2px, lettre dans un disque bleu ciel ; après réponse, la
  bonne passe en vert pâle (bordure verte, disque vert portant une **coche**), la mauvaise choisie en rouge pâle (disque
  rouge portant une **croix**) ; les autres options passent à 50 %. Le récapitulatif du score reprend les mêmes disques
  coche / croix.
- **Progression:** barres de 8px en pilule, étape courante jaune, juste vert, fausse rouge.
- **Flashcard:** 300px de haut, contour marine épais, ombre forte ; retournement 3D de 420ms ease-in-out vers un
  verso bleu roi plein dont la réponse est en STIX Two Text 28px. Sous mouvement réduit, le retournement devient un
  simple échange de faces.

### Motion
Courbes : `cubic-bezier(.23,1,.32,1)` pour les entrées et retours d'état, `cubic-bezier(.77,0,.175,1)` pour les
transformations symétriques (flashcard, pulsations). Durées de 160ms (états de contrôle) à 450ms (trait tracé sous la
formule clé). Sous `prefers-reduced-motion`, les transformations et entrées disparaissent mais les fondus de couleur
et d'opacité restent.

### La landing (vitrine)
Fichiers : `docs/maquettes/accueil/index.html`, `accueil.css`, `accueil.js`, `gradient.js`. Mêmes variables `--mat-*`,
même Inter, mêmes boutons 8px et mêmes pastilles `[Slide N]` que l'outil ; ce qui change :
- **Bandes marine.** Le hero, la section des agents et la fin de page sont sur `--mat-texte` (#0B1A45), texte blanc
  `--mat-surface`, texte secondaire en bleu pâle dérivé (#C7D2FE). Ce sont des bandes, pas un thème sombre : le reste
  de la page est sur `--mat-fond` et l'outil n'a pas de mode sombre.
- **Dégradé vivant.** Un seul shader WebGL (`gradient.js`) mêle marine, bleu roi, bleu clair, bleu très clair et une
  petite lueur jaune du pompon, sous les bandes marine uniquement. Il est rendu à résolution réduite, se met en pause
  hors écran et onglet caché, reste figé sous mouvement réduit, et a un repli CSS en dégradés radiaux. Aucune autre
  surface ne reçoit de dégradé décoratif (le fondu bleu ciel de la section Preuves est un aplat dérivé, pas un effet).
- **Titres d'affiche.** Inter 800, de 40 à 86px dans le hero et jusqu'à 100px en fin de page, interlettrage -0.045em ;
  la seconde moitié des titres de section passe en bleu roi (bleu clair sur marine).
- **Surligneur.** Un trait jaune tracé sous le dernier mot du hero et de la fin de page : c'est le geste « à retenir »
  de la Pompon Rule, pas une décoration libre. Un seul par bande, jamais sur un bouton.
- **Le logo sur marine.** Il n'est jamais posé directement sur le fond foncé : barre de navigation blanche flottante et
  médaillon blanc rond autour de la mascotte du hero. L'ombre est portée par le médaillon, jamais par le logo.
- **Mouvement d'auteur.** Entrée du hero une fois (lignes du titre qui montent, 900ms ease-out, décalage 90ms ; trait
  du surligneur 700ms), apparition des titres au défilement (une fois, depuis 24px), compteurs (1,4s ease-out quartique),
  tuteur qui se redresse au défilement (`animation-timeline: view()`, sans repli JS), bandeau des matières en boucle
  linéaire de 38s qui s'arrête au survol, parallaxe légère des bulles du hero et bouton aimanté au pointeur fin, tache
  de lumière qui suit le curseur dans les cartes (transform sur un enfant). Rien d'autre ne tourne en boucle. Seuls
  `transform` et `opacity` sont animés ; sous `prefers-reduced-motion`, tout reste à sa place finale et le bandeau
  devient défilable à la main.

## Do's and Don'ts

### Do:
- **Do** prendre toute valeur de couleur, de police et de bouton dans `docs/charte.md` (D1, Both) ; reprendre ses variables `--mat-*` telles quelles.
- **Do** mettre la mascotte en état « réfléchit » pendant chaque génération d'agent (SSE de l'Explainer et du Q&A) et la ramener au repos à la fin.
- **Do** rendre chaque `[Slide N]` comme une pastille jaune cliquable (texte marine, coins 6px) qui mène à la slide.
- **Do** accompagner chaque verdict de quiz d'une icône coche ou croix en plus du vert ou du rouge.
- **Do** garder le focus clavier visible : contour 2px bleu roi décalé de 2px sur tout élément interactif.
- **Do** utiliser des propriétés logiques (`inline-start`, `block-end`) et retourner les icônes directionnelles pour que l'arabe passe en RTL sans CSS supplémentaire.
- **Do** garder l'action principale dans la barre fixe du bas sous 980px et les boutons icône à 44px sur téléphone.
- **Do** composer les formules en STIX Two Text (KaTeX dans le frontend React) et auto-héberger toutes les polices.

### Don't:
- **Don't** sortir de la palette de la charte : pas de nouvelle teinte, pas de thème sombre, pas de dégradé décoratif dans l'outil (la landing a ses exceptions, voir « La landing (vitrine) »).
- **Don't** reprendre dans l'outil les effets de la vitrine (dégradé vivant, bandes marine, bandeau défilant, parallaxe) : l'outil est consulté des dizaines de fois par séance.
- **Don't** utiliser le jaune pour un bouton d'action ou une décoration, ni mettre du texte blanc sur le jaune ou le bleu clair.
- **Don't** déformer, recolorer ou ombrer le logo, ni le poser sur un fond foncé.
- **Don't** construire des écrans en tableau de bord SaaS à cartes grises anonymes ; le tuteur a la mascotte pour visage.
- **Don't** mettre de vert ou de rouge sur l'interface au repos, ni un verdict sans son icône.
- **Don't** charger une police depuis un service en ligne (Google Fonts ou autre).
