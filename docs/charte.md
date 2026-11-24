# Charte graphique — Multi-Agent Tutor (D1)

Responsable : Both. Destinataire principal : Ali (frontend, A5).

## Logo

| Fichier | Taille | Usage |
|---|---|---|
| `assets/logo.png` | 999 × 819 | Logo complet (robot + « Multi-Agent Tutor ») : page d'accueil, README, slides de soutenance. |
| `assets/logo-icone.png` | 512 × 512 | Robot seul avec les deux bulles et le livre : en-tête de l'application, écran de chargement. |
| `assets/logo-tete.png` | 256 × 256 | Tête du robot : avatar du tuteur dans le chat. |
| `assets/favicon.png` | 64 × 64 | Icône de l'onglet du navigateur. |

Le logo montre un **robot tuteur** coiffé d'une toque de diplômé, assis derrière un **livre ouvert** (le cours). Il tient deux bulles : **l'équipe d'agents** et **le cours**.

Règles :
- garder une marge blanche autour du logo, au moins égale à la largeur d'une bulle ;
- ne pas déformer, recolorer ni ajouter d'ombre ;
- le logo est prévu pour un fond blanc ou très clair.

## Couleurs

Les couleurs sont reprises du logo.

| Rôle | Nom | Hex | Usage |
|---|---|---|---|
| Primaire | Bleu roi | `#2563EB` | Boutons principaux, liens, slide active. Texte blanc dessus : contraste 5,2:1 ✅ |
| Primaire (survol) | Bleu foncé | `#1D4ED8` | Survol et état « appuyé » des boutons primaires (6,7:1 ✅) |
| Secondaire | Bleu clair | `#4C8AFD` | Accents, badges, progression, icônes. **Pas de texte blanc dessus** (3,3:1 ❌) |
| Accent | Jaune (pompon) | `#FBBF24` | Citations [Slide N], surlignage, flashcards. **Texte marine dessus** (10:1 ✅), jamais blanc |
| Texte | Bleu marine | `#0B1A45` | Texte principal et contours (16:1 sur le fond ✅) |
| Texte secondaire | Ardoise | `#475569` | Légendes, métadonnées (7,6:1 sur blanc ✅) |
| Fond | Gris très clair | `#F8FAFC` | Fond de page ; cartes et panneaux en blanc `#FFFFFF` |
| Fond clair | Bleu très clair | `#DBEAFE` | Bulles de l'utilisateur, zones mises en avant (texte marine dessus, 13,8:1 ✅) |
| Bordures | Gris clair | `#E2E8F0` | Séparateurs, contours des cartes et des champs |

États (quiz, messages) : succès `#15803D` (5,0:1 ✅), erreur `#DC2626` (4,8:1 ✅).

```css
:root {
  --mat-primaire: #2563EB;
  --mat-primaire-survol: #1D4ED8;
  --mat-secondaire: #4C8AFD;
  --mat-accent: #FBBF24;
  --mat-texte: #0B1A45;
  --mat-texte-secondaire: #475569;
  --mat-fond: #F8FAFC;
  --mat-surface: #FFFFFF;
  --mat-fond-clair: #DBEAFE;
  --mat-bordure: #E2E8F0;
  --mat-succes: #15803D;
  --mat-erreur: #DC2626;
}
```

## Police

- **Inter** (open source, licence SIL OFL) pour toute l'interface : titres en 700, texte en 400, boutons en 600.
- **Contrainte v2 (aucun service en ligne)** : ne pas charger la police depuis Google Fonts. Placer les fichiers `.woff2` d'Inter dans `frontend/` et les déclarer avec `@font-face`, ou se contenter de la pile système.
- Pile de secours : `Inter, "Segoe UI", Roboto, Arial, sans-serif`.
- Formules (LaTeX) : rendu par KaTeX ou MathJax installé en local, police par défaut de la bibliothèque.

| Élément | Taille | Graisse |
|---|---|---|
| Titre de page | 28 px | 700 |
| Titre de section | 20 px | 700 |
| Texte courant, chat | 16 px | 400, interligne 1,5 |
| Légendes, citations | 14 px | 400 |

## Boutons

| Type | Fond | Texte | Bordure | Usage |
|---|---|---|---|---|
| Primaire | `#2563EB` (survol `#1D4ED8`) | blanc | aucune | Action principale : « Poser la question », « Démarrer le quiz » |
| Secondaire | blanc | `#2563EB` | 1 px `#2563EB` | Actions secondaires : « Slide suivante », « Exporter » |
| Discret | transparent | `#475569` | aucune | Actions mineures : « Annuler », icônes |
| Danger | `#DC2626` | blanc | aucune | Suppression uniquement |

Forme commune : coins arrondis 8 px, hauteur 40 px, marge interne 0 × 16 px, police 15 px en 600.
Désactivé : opacité 50 %, curseur `not-allowed`. Focus clavier : contour 2 px `#2563EB` décalé de 2 px (accessibilité).

```css
.mat-btn { height: 40px; padding: 0 16px; border-radius: 8px; font: 600 15px Inter, "Segoe UI", Roboto, Arial, sans-serif; cursor: pointer; }
.mat-btn:focus-visible { outline: 2px solid var(--mat-primaire); outline-offset: 2px; }
.mat-btn:disabled { opacity: .5; cursor: not-allowed; }
.mat-btn--primaire { background: var(--mat-primaire); color: #fff; border: none; }
.mat-btn--primaire:hover { background: var(--mat-primaire-survol); }
.mat-btn--secondaire { background: var(--mat-surface); color: var(--mat-primaire); border: 1px solid var(--mat-primaire); }
.mat-btn--discret { background: transparent; color: var(--mat-texte-secondaire); border: none; }
.mat-btn--danger { background: var(--mat-erreur); color: #fff; border: none; }
```

## Éléments propres au tuteur

- **Citation** `[Slide N]` : pastille jaune `#FBBF24`, texte `#0B1A45`, coins 6 px, cliquable (ouvre la slide).
- **Bulle du tuteur** : fond blanc, bordure `#E2E8F0`, avatar = `assets/logo-tete.png`. **Bulle de l'utilisateur** : fond `#DBEAFE` (bleu très clair), alignée à droite.
- **Niveau d'explication** (débutant / intermédiaire / avancé) : sélecteur segmenté, segment actif en bleu roi.
- **Quiz** : bonne réponse en `#15803D`, mauvaise en `#DC2626`, toujours accompagnées d'une icône ✓ / ✗ (ne pas reposer sur la couleur seule).
