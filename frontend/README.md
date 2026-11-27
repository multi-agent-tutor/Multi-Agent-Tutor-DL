# frontend/

Responsable : Ali — tâche A5 (voir la répartition des tâches).

Interface React + Vite + TypeScript du tuteur, d'après les maquettes D2 d'Ons (`docs/maquettes/`, branche `ons`,
et `DESIGN.md`) et la charte D1 de Both (`docs/charte.md`, branche `both`).

**Tout est servi en local** : aucune API externe, aucun CDN, aucune Google Fonts. Les polices (Inter, Noto Sans
Arabic, STIX Two Text, Noto Sans Math) sont dans `public/fonts/`, le logo et le favicon dans `public/img/`, et KaTeX
(formules LaTeX) est installé par npm avec ses polices. Le seul serveur appelé est l'API du projet (`VITE_API_URL`).
Les liens des ressources (Wikipédia, YouTube…) ne s'ouvrent que si l'étudiant clique dessus.

## Lancer

Il faut Node.js 20 ou plus récent, et l'API lancée à côté.

```bash
# 1. L'API, depuis la racine du dépôt (port 8000)
.venv\Scripts\activate          # Windows ; source .venv/bin/activate sous Linux/macOS
uvicorn api.main:app --reload

# 2. Le frontend, dans un second terminal (port 5173)
cd frontend
cp .env.example .env            # puis ajuster VITE_API_URL si l'API n'est pas sur localhost:8000
npm install
npm run dev                     # http://localhost:5173
```

Autres commandes : `npm run build` (vérification TypeScript + build dans `dist/`), `npm run preview` (sert `dist/`
sur le port 5173), `npm run typecheck`.

Le port 5173 est fixé (`strictPort`) car c'est l'origine autorisée par CORS dans `api/main.py`. Si une autre
application l'occupe déjà, Vite s'arrête au lieu de prendre un autre port : libère le port ou ajoute l'origine dans
`ORIGINES_FRONTEND`.

## Configuration (`frontend/.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL de l'API FastAPI |
| `VITE_COURS_PAR_DEFAUT` | `ml_regression_lineaire_fr` | Cours ouvert au premier lancement (le cours d'exemple de l'API) |

`.env` est ignoré par Git (règle racine) : `.env.example` est le modèle versionné.

## Pages et navigation

Navigation par le hash de l'URL (le bouton Précédent du navigateur fonctionne) :
**Accueil** `#accueil` (ou vide) → **Dépôt** `#depot` → **Cours** `#cours` → **Quiz** `#quiz` / `#flashcards`.

- **Accueil** (landing, maquette `docs/maquettes/accueil/`, registre « vitrine » de `DESIGN.md`) : sa propre barre
  flottante, dégradé WebGL vivant (`src/pages/accueil/degrade.ts`, port de `gradient.js`, sans bibliothèque), démos
  jouables figées (tuteur, routeur d'agents, parcours, QCM), aucun appel à l'API sauf « Essayer la démo » qui ouvre
  le cours `VITE_COURS_PAR_DEFAUT`. Sous `prefers-reduced-motion`, tout reste à sa place finale et le dégradé devient
  une image fixe. Les ancres de section (`#essai`, `#agents`…) restent sur l'accueil.
- **Dépôt** (maquette `depot.html`) : glisser-déposer ou bouton, contrôle PPTX/PDF et 50 Mo, `POST /upload` en
  XMLHttpRequest pour suivre l'envoi (pourcentage), puis traitement (étapes Ingestion / OCR / VLM / RAG
  *indicatives* : l'API ne renvoie pas d'avancement), erreur avec « Réessayer », annulation, panneau « cours prêt »
  qui ouvre la page Cours ou Quiz. « Cours déjà déposés » : les derniers cours ouverts (`localStorage`,
  `mat-cours-recents`), rouverts par `GET /course/{id}`.
- **Cours** et **Quiz** : barre de l'outil avec onglets Déposer / Cours / Quiz, logo vers l'accueil.

### Landing : styles

`src/styles/accueil.css` est la copie de `docs/maquettes/accueil/accueil.css` dont toutes les classes portent le
préfixe `v-` (la maquette réutilise `.bouton`, `.choix`, `.niveaux`, `.flashcard`… avec un autre sens que
`maquettes.css`). Après une nouvelle maquette : `python frontend/scripts/scoper_accueil.py
docs/maquettes/accueil/accueil.css <fichier>` puis remplacer le début de `accueil.css` en gardant le bloc final
« ajouts A5 » (langue, RTL). Les textes FR / EN / AR de la landing sont dans `src/pages/accueil/textes.ts`.

## Routes de l'API utilisées

| Page | Zone | Route |
|---|---|---|
| Dépôt | envoi d'un support PDF/PPTX (champ `fichier`, et `langue` si choisie) | `POST /upload` |
| Cours | slide à gauche (titre, texte, formules KaTeX, figures), navigation, bande de maîtrise | `GET /course/{id}` |
| Cours | explication à 3 niveaux (débutant / intermédiaire / avancé) | `GET /slide/{id}/explain?niveau=` |
| Cours | ressources de la slide (titre, type, justification, lien) | `GET /resources?slide_id=&niveau=&langue=` |
| Cours | chat Q&A avec citations `[Slide N]` | `POST /ask` |
| Quiz | QCM une question à la fois, retour immédiat, score | `GET /quiz?course_id=&slide=&n=&langue=` |
| Quiz | flashcards : cartes dues, sinon génération puis enregistrement | `GET /flashcards/due`, `GET /flashcards`, `POST /flashcards/save` |
| Quiz | notation SM-2 de 0 à 5 | `POST /flashcards/{id}/review` |
| Quiz | export Anki (.apkg) | `GET /flashcards/export` |

- **Langue** : FR / EN / AR dans la barre du haut (et dans la barre de la landing) ; en arabe, la page passe en RTL (`dir="rtl"`). La langue est
  envoyée à `/ask`, `/quiz`, `/flashcards` et `/resources`.
- **Citations** : `[Slide N]`, `[Slides 3, 5]` et `[Slide 3-5]` deviennent des pastilles jaunes cliquables qui
  amènent à la slide (depuis le quiz aussi). Les sources renvoyées mais non citées dans le texte sont ajoutées en fin
  de réponse. Une réponse du Q&A sans aucune source est affichée comme un refus honnête (bulle en pointillés).
- **Formules** : `$…$`, `$$…$$`, `\(…\)`, `\[…\]` dans les réponses, et `Slide.formules_latex` sur la slide ;
  toujours rendues par KaTeX (installé par npm), y compris dans les démos de la landing.
- **Image de slide** : si `Slide.image_rendu` est renseigné, la page Cours charge
  `GET {VITE_API_URL}/course/{course_id}/{image_rendu}` (`urlImageSlide`, `src/api.ts`) ; si l'image échoue, la slide
  revient à l'affichage texte (et on ne réessaie plus pour ce cours pendant la session).
- **Utilisateur SRS** : identifiant gardé dans `localStorage` (`mat-user`, `etudiant` par défaut).
- **Maîtrise** (bande des slides) : *vue* = slide affichée, *comprise* = explication reçue, *testée* = question de
  quiz répondue. Gardée dans `localStorage`, par cours.
- **Clavier** : ← / → changent de slide ; 1–4 ou A–D répondent au QCM ; Espace retourne la flashcard, 0–5 la note.

## LLM local lent et streaming (A3)

`/slide/{id}/explain` et `/ask` ne sont plus factices : ils passent par le graphe LangGraph de l'API (Explainer O2,
Q&A, Critic O3) et le LLM local. Sur CPU, une explication prend environ 2 min sans Critic et 3 à 5 min avec
(mesuré sur la slide `ml_regression_lineaire_fr__s002`, niveau débutant, Qwen2.5-3B Q4). Pendant la génération,
la mascotte « réfléchit », un compteur affiche le temps écoulé (avec un avertissement après 15 s) et un bouton
permet d'annuler. Les explications déjà reçues sont gardées en cache (slide × niveau) et un délai de 300 ms évite
de lancer une génération à chaque slide quand on navigue vite.

Le frontend envoie `Accept: text/event-stream, application/json` : l'API répond alors en **SSE** (format détaillé
dans [`api/README.md`](../api/README.md#streaming-sse-slideidexplain-ask)). `lireReponseAgent` (`src/api.ts`) lit :

- **SSE** (`text/event-stream`) : les événements `progression` (`debut`, `generation`, `verification`,
  `correction`), `erreur` (`{statut, detail}`) et les `: ping` toutes les 15 s n'ont ni `token` ni `reponse` et
  n'entrent pas dans le texte ; le dernier `data:` est l'`AgentResponse` final
  (`{"agent": …, "reponse": …, "sources": […], "score_fidelite": …}`), puis `data: [DONE]`. Les agents
  produisent du JSON structuré : la réponse arrive d'un bloc, pas jeton par jeton (`{"token": "…"}` reste
  accepté) ;
- **JSON** (`application/json`, si l'API ne streame pas) : `AgentResponse`, dont le texte est révélé mot à mot.

**`API_CRITIC`** (`.env` de l'API, à redémarrer après changement) :

- `on` (défaut) : la réponse est relue par le Critic (étape SSE `verification`, `score_fidelite` renseigné, jusqu'à
  2 corrections). `API_TIMEOUT_LLM` vaut 400 s par défaut (Explainer + Critic : ~290 s sur CPU) : au-delà,
  l'API envoie `event: erreur` (504) puis l'explication non vérifiée, suivie d'un avertissement ;
- `off` : réponse livrée sans vérification, `score_fidelite` à `null` (démo sur CPU lent).

## Arborescence

```
frontend/
├── public/fonts/        polices woff2 (copiées de docs/maquettes/fonts/, branche ons)
├── public/img/          logo, logo-icone, logo-tete, favicon (copiés de assets/, branche both)
└── src/
    ├── api.ts           client de l'API, lecture JSON/SSE, export Anki
    ├── types.ts         miroir TypeScript de schemas/models.py et api/models.py
    ├── i18n.tsx         libellés FR / EN / AR, bascule RTL
    ├── maitrise.ts      état vue / comprise / testée des slides
    ├── recents.ts       cours déjà déposés (page Dépôt)
    ├── components/      barre du haut, mascotte, icônes, texte riche (KaTeX + citations), attente
    ├── pages/           Dépôt, Cours, Quiz, Flashcards ; accueil/ (landing, dégradé WebGL, démos, textes)
    └── styles/          maquettes.css (copie de la maquette D2), app.css (états réels de l'API),
                         depot.css (maquette depot.html), accueil.css (landing, classes v-*)
scripts/scoper_accueil.py  régénère accueil.css depuis la maquette
```

`types.ts` est maintenu à la main : toute évolution de `schemas/models.py` ou `api/models.py` doit y être reportée.

## Limites connues

- Le rendu PNG des slides (`Slide.image_rendu`) n'est pas encore servi par l'API (aucune route ni fichiers statiques
  dans `api/main.py`) : la slide est affichée à partir de son texte, de ses formules et de la description de ses
  figures. Il suffira d'ajouter côté API `GET /course/{course_id}/{chemin}` servant `data/processed/<course_id>/`.
- `POST /upload` renvoie encore le cours d'exemple (ingestion non branchée) et ignore le champ `langue`.
- « Écouter » (lecture audio, A7) est affiché mais désactivé.
