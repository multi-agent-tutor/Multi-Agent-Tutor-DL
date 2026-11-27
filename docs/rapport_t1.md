# T1 — Rapport de la campagne de tests manuels

Testeur : Ghayth · Date : 2026-11-21 · Checklist : [`checklist_tests.md`](checklist_tests.md) ·
Captures : [`captures_t1/`](captures_t1/)

## Environnement

| Élément | Valeur |
|---|---|
| Commit testé | `bc1601d` (develop, après la PR #21 d'Ali) |
| OS / navigateur | Windows 11, Microsoft Edge (piloté par Playwright pour les captures) |
| API | `uvicorn api.main:app`, `API_CRITIC=off` (CPU), `API_QA=auto` |
| LLM / VLM | Qwen2.5-3B-Instruct Q4_K_M (A0) · Qwen2.5-VL-3B (H2), CPU uniquement |
| Frontend | `npm run dev` (Vite 8), `VITE_API_URL=http://localhost:8000` |

## Cours utilisés

| Cours | Comment il a été testé |
|---|---|
| `ml_regression_lineaire_fr` (cours d'exemple de l'API) | parcours complet dans l'interface |
| `dl_self_attention_ntu_en` (PPTX ingéré par H1-H3) | API (`/slide/…/explain`, `/course`, `/resources`) et interface |
| `maths_matrices_scan_uiowa_en` (PDF scanné) | import par l'interface et `POST /upload` |
| fichiers vide / corrompu / `.docx` | `POST /upload` |

L'interface ne peut afficher **que** le cours d'exemple : c'est le constat principal (bugs 1 et 2).

## Résumé

**13 bugs** : 2 bloquants, 6 majeurs, 5 mineurs. Tout ce qui ne dépend pas de l'ouverture
d'un vrai cours fonctionne : navigation, clavier, niveaux, citations cliquables, SSE, gestion des erreurs
404 / 415 / 422, arabe RTL, anglais, largeur mobile, flashcards, révision SM-2.

| # | Gravité | Titre | Module | Pour | Issue |
|---|---|---|---|---|---|
| 1 | bloquant | `POST /upload` ignore le fichier et renvoie le cours d'exemple | api | Ali | [#37](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/37) |
| 2 | bloquant | Les cours ingérés (`data/processed`) sont introuvables : `GET /course/{id}` → 404 | api | Ali | [#36](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/36) |
| 3 | majeur | L'indicateur d'attente n'est jamais visible : panneau Explication vide pendant 1 à 4 min | frontend | Ali | [#35](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/35) |
| 4 | majeur | Formules LaTeX et gras Markdown affichés bruts dans l'explication | agents / frontend | Ons, Ali | [#34](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/34) |
| 5 | majeur | Quiz toujours vide : le Critic rejette tous les QCM (rejets incohérents, LaTeX abîmé) | agents | Ons, Ali | [#33](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/33) |
| 6 | majeur | `/quiz` et `/flashcards` → 500 si une dépendance du RAG manque ; le frontend dit « API injoignable » | agents / api | Ali | [#32](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/32) |
| 7 | majeur | `GET /resources` → 404 sur les slides des cours ingérés | api | Ali | [#31](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/31) |
| 8 | majeur | Un PDF vide ou corrompu est accepté (HTTP 200) | api | Ali | [#30](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/30) |
| 9 | mineur | Citation fausse : l'explication de la slide 1 attribue à `[Slide 1]` une formule de la slide 2 | agents | Ons | [#29](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/29) |
| 10 | mineur | Le repli « Q&A non disponible » s'affiche comme une réponse sourcée `[Slide 1]` | frontend / agents | Ali, Both | [#28](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/28) |
| 11 | mineur | `GET /resources` met 17 s alors que le catalogue est local | agents | Ali | [#27](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/27) |
| 12 | mineur | Les explications sont regénérées à chaque rechargement et s'empilent dans la file du LLM | frontend | Ali | [#26](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/26) |
| 13 | mineur | Bundle JS de 529 Ko (avertissement Vite > 500 Ko) | frontend | Ali | [#25](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/25) |

## Non testé (et pourquoi)

- **Q&A réel (B3)** : modèles `bge-m3` et `bge-reranker-v2-m3` (≈ 4,6 Go) en cours de téléchargement ;
  seul le repli « Q&A non disponible » a été vérifié. À refaire dès que les modèles sont là.
- **Critic actif (`API_CRITIC=on`)** : non testé sur l'explication (3 à 5 min par réponse sur CPU) ;
  le Critic du quiz, lui, est toujours actif (bug 5).
- **TTS (A7)** : bouton « Écouter » désactivé, tâche pas encore livrée.
- **Import Anki** : export non téléchargé, faute de cartes enregistrées (quiz vide, bug 5).
- **Ingestion par l'interface** : impossible tant que le bug 1 n'est pas corrigé.

## Ce qui fonctionne

| Section | Résultat |
|---|---|
| Build | `npm run build` : TypeScript sans erreur, build Vite OK |
| Navigation | Précédente / Suivante, bornes respectées, ← / → au clavier, pastilles de slides |
| Explication | 3 niveaux réellement différents (avancé : formule complète ; débutant : analogie), structure idée clé → détail → exemple → à retenir, 40 à 105 s sur CPU |
| Explication d'un cours ingéré | `GET /slide/dl_self_attention_ntu_en__s033/explain` OK (42 s), cite `[Slide 33]` |
| Citations | 5 pastilles `[Slide N]` cliquables, navigation vers la slide |
| SSE | événements `progression`, `: ping`, réponse finale, `[DONE]` |
| Erreurs API | `.docx` → 415, slide hors limites → 404, niveau invalide → 422, question vide → 422 |
| Flashcards | 3 cartes pertinentes en 27 s, formules bien délimitées par `$…$` ; `/flashcards/due` OK |
| Langues | EN traduit ; AR : `dir="rtl"`, `lang="ar"`, mise en page inversée correcte ([capture](captures_t1/11_langue_AR.png)) |
| Mobile 375 px | aucun débordement horizontal ([capture](captures_t1/12_mobile_375.png)) |

---

## Issues GitHub

Publiées le 2026-11-27 : [#25 à #37](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues?q=is%3Aissue+%5BT1%5D). Texte ci-dessous.

### Issue 1 ([#37](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/37)) — [T1] `POST /upload` ignore le fichier et renvoie toujours le cours d'exemple

- **Gravité** : bloquant · **Étiquettes** : `bug`, `T1`, `api` · **Assigné** : Ali
- **Section** : 1. Upload et ingestion · **Cours** : `maths_matrices_scan_uiowa_en.pdf`

**Étapes**
1. Lancer l'API et le frontend.
2. « Importer un cours » → choisir `data/corpus/en/maths/maths_matrices_scan_uiowa_en.pdf`.

**Attendu** : le cours importé (8 slides, « Mathematical Methods of Physics I - Matrices ») s'affiche.
**Obtenu** : l'interface reste sur « Régression linéaire », sans message. L'API renvoie 200 avec
`"id": "ml_regression_lineaire_fr"` quel que soit le fichier.
**Capture** : [`07_apres_import_scan.png`](captures_t1/07_apres_import_scan.png)

**Cause** : `api/main.py:146-153`, le contenu est lu puis ignoré (`return _cours(_exemple.id)`).
**Piste** : écrire le fichier dans `data/corpus/_local/`, appeler `ingestion.parse_course(...)` (ou
`ingestion.ingest(...)` pour H1 → H2 → H3, ou `--texte-brut` pour aller vite), ajouter le cours à
`COURS`, puis indexer avec `rag.index`. L'ingestion est longue (VLM) : la lancer en tâche de fond.

### Issue 2 ([#36](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/36)) — [T1] Les cours ingérés sont introuvables : `GET /course/{id}` → 404

- **Gravité** : bloquant · **Étiquettes** : `bug`, `T1`, `api` · **Assigné** : Ali
- **Section** : 2. Navigation · **Cours** : `dl_self_attention_ntu_en` (présent dans `data/processed/`)

**Étapes**
1. `curl http://localhost:8000/course/dl_self_attention_ntu_en`
2. Ou, dans le navigateur : `localStorage.setItem('mat-cours','dl_self_attention_ntu_en')` puis recharger.

**Attendu** : le `Course` de `data/processed/dl_self_attention_ntu_en/course.json`.
**Obtenu** : `404 Cours inconnu`. L'interface affiche l'écran d'accueil vide « Ouvre un cours pour
commencer », sans dire que le cours est introuvable.
**Capture** : [`08_cours_ingere.png`](captures_t1/08_cours_ingere.png)

**Cause** : `_cours()` (`api/main.py:119`) ne lit que le dictionnaire `COURS` (cours d'exemple), alors
que `_slide_connue()` (`api/main.py:405`), utilisée par `/explain`, lit déjà `data/processed`. Les deux
routes ne voient pas les mêmes cours.
**Piste** : faire passer `_cours()` par le même chargement (`ingestion.charger_course(course_id)`), et
ajouter une route `GET /courses` qui liste les cours de `data/processed` pour le frontend.

### Issue 3 ([#35](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/35)) — [T1] Indicateur d'attente jamais visible : panneau Explication vide pendant 1 à 4 min

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `frontend` · **Assigné** : Ali
- **Section** : 3. Explication · **Cours** : `ml_regression_lineaire_fr`

**Étapes**
1. Ouvrir la page Cours, cliquer sur « Avancé ».
2. Observer le panneau Explication pendant la génération.

**Attendu** : « Le tuteur réfléchit… » avec le compteur de secondes et le bouton « Annuler ».
**Obtenu** : panneau vide (ni texte, ni compteur, ni bouton Annuler) pendant toute la génération
(plus de 4 min observées quand une autre génération était en file). L'étudiant croit que rien ne se passe.
**Capture** : [`05_explication_avance.png`](captures_t1/05_explication_avance.png)

**Cause** : `frontend/src/api.ts:117`, `surTexte(texte)` est appelé pour **chaque** événement SSE, y compris
`event: progression` (pas de `token` ni de `reponse`). Dès le premier événement, `Cours.tsx:302` passe en
`statut: "ecriture"` avec un texte vide, et `<Attente>` (`Cours.tsx:367`, affiché seulement en
`"attente"`) disparaît.
**Piste** : n'appeler `surTexte` que si `texte` a changé, ou rester en `"attente"` tant que le texte est vide.

### Issue 4 ([#34](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/34)) — [T1] Formules LaTeX et gras Markdown affichés bruts dans l'explication

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `agents`, `frontend` · **Assignés** : Ons (O2), Ali (A5)
- **Section** : 3. Explication · **Cours** : `ml_regression_lineaire_fr`, slide 1, niveau intermédiaire

**Attendu** : formules rendues par KaTeX, titres « Idée clé », « Exemple », « À retenir » en gras.
**Obtenu** : texte brut `J(\theta) = \frac{1}{2m} \sum_{i=1}^{m} (h_\theta(x^{(i)}) - y^{(i)})^2`, et
`**Idée clé**`, `**Exemple**`, `**À retenir**` avec les astérisques. Aucun élément `.katex` dans la page.
**Capture** : [`02_explication_intermediaire.png`](captures_t1/02_explication_intermediaire.png)

**Cause** : l'Explainer produit les formules **sans** délimiteurs `$…$` (les flashcards, elles, les
délimitent bien), et `TexteRiche` ne rend que les formules délimitées ; il ne gère pas non plus `**gras**`.
**Piste** : Ons, exiger `$…$` dans le prompt de l'Explainer (ou envelopper les formules en post-traitement) ;
Ali, rendre `**…**` dans `TexteRiche` (ou retirer les astérisques avant `structurer`).

### Issue 5 ([#33](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/33)) — [T1] Quiz toujours vide : le Critic rejette tous les QCM

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `agents` · **Assignés** : Ons (O3), Ali (A2)
- **Section** : 5. Quiz · **Cours** : `ml_regression_lineaire_fr`, slide 2

**Étapes** : `GET /quiz?course_id=ml_regression_lineaire_fr&slide=2&n=3&langue=fr`

**Attendu** : 3 QCM.
**Obtenu** : `[]` après 80 s, en-tête `X-Quiz-Message: Quiz indisponible : aucun QCM n'a passé la
vérification du Critic`. Le journal de l'API montre des rejets **incohérents** :

```
QCM écarté par le Critic (La réponse C est correcte et correspond à l'interprétation
de la fonction de coût $J(<TAB>heta)$.)
```

Le Critic dit que la réponse est correcte et écarte quand même la question. Le `\t` de `\theta` est
devenu une tabulation : le LaTeX est mal échappé dans le JSON échangé avec le Critic, ce qui fausse sans
doute son jugement (`\f` de `\frac` et `\b` de `\beta` sont touchés de la même façon).
**Capture** : [`09_quiz.png`](captures_t1/09_quiz.png)
**Piste** : vérifier l'échappement des `\` dans les QCM envoyés à `verifier_qcm`, et le critère de rejet
(rejeter seulement si le verdict est négatif).

### Issue 6 ([#32](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/32)) — [T1] `/quiz` et `/flashcards` → 500 si une dépendance du RAG manque

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `agents`, `api` · **Assigné** : Ali
- **Section** : 5. Quiz / 9. Robustesse

**Étapes** : environnement sans `qdrant_client`, puis ouvrir l'onglet Quiz.

**Attendu** : repli sur la recherche locale (comme le Q&A), quiz généré.
**Obtenu** : HTTP 500 (`ModuleNotFoundError: No module named 'qdrant_client'`). La réponse 500 n'a pas
d'en-tête CORS : le navigateur la bloque et le frontend affiche « API injoignable
(http://localhost:8000). Lance « uvicorn api.main:app --reload » » alors que l'API tourne.

**Cause** : `agents/quiz.py:148`, `importlib.import_module("rag.search")` est **hors** du `try/except`
de `recherche()` (ligne 157) : une erreur d'import d'une dépendance du RAG n'est pas rattrapée.
**Piste** : déplacer l'import dans le `try`, ou rattraper `ImportError` dans `_recherche_rag()` ; côté
frontend, distinguer « API injoignable » d'une erreur 5xx.

### Issue 7 ([#31](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/31)) — [T1] `GET /resources` → 404 sur les slides des cours ingérés

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `api` · **Assigné** : Ali
- **Étapes** : `GET /resources?slide_id=dl_self_attention_ntu_en__s013`
- **Obtenu** : `404 Cours inconnu : dl_self_attention_ntu_en`. **Cause** : même origine que l'issue 2.

### Issue 8 ([#30](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/30)) — [T1] Un PDF vide ou corrompu est accepté (HTTP 200)

- **Gravité** : majeur · **Étiquettes** : `bug`, `T1`, `api` · **Assigné** : Ali
- **Étapes** : `POST /upload` avec un `.pdf` de 0 octet, puis avec 2 Ko d'octets aléatoires nommés `.pdf`.
- **Attendu** : 400 « fichier vide ou illisible ». **Obtenu** : 200 et le cours d'exemple.
- **Piste** : avec l'issue 1, rattraper les erreurs de `parse_course` (`ValueError`, erreurs PyMuPDF) en 400.

### Issue 9 ([#29](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/29)) — [T1] Citation fausse dans l'explication de la slide 1

- **Gravité** : mineur · **Étiquettes** : `bug`, `T1`, `agents` · **Assignée** : Ons (O2)
- **Obtenu** : l'explication de la slide 1 donne la formule `J(\theta)`, qui est sur la **slide 2**, et la cite
  `[Slide 1]`. Observé avec `API_CRITIC=off` : à revérifier avec le Critic actif.
- **Capture** : [`02_explication_intermediaire.png`](captures_t1/02_explication_intermediaire.png)

### Issue 10 ([#28](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/28)) — [T1] Le repli « Q&A non disponible » s'affiche comme une réponse sourcée

- **Gravité** : mineur · **Étiquettes** : `bug`, `T1`, `frontend`, `agents` · **Assignés** : Ali, Both
- **Obtenu** : « Le Q&A n'est pas disponible : modèles RAG non installés ou cours non indexé. » avec une
  pastille `[Slide 1]`, dans une bulle normale. La source fait croire à une réponse tirée du cours.
- **Attendu** : bulle d'erreur ou de refus (pointillés), sans source.
- **Capture** : [`06_chat_qa.png`](captures_t1/06_chat_qa.png)

### Issue 11 ([#27](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/27)) — [T1] `GET /resources` met 17 s

- **Gravité** : mineur · **Étiquettes** : `T1`, `agents`, `performance` · **Assigné** : Ali
- **Obtenu** : 16,8 s pour `slide_id=ml_regression_lineaire_fr__s002`, alors que les ressources viennent du
  catalogue local `data/ressources/catalogue.json`. Probablement l'appel LLM de filtrage : à mettre en cache.

### Issue 12 ([#26](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/26)) — [T1] Explications regénérées à chaque rechargement, qui s'empilent dans la file du LLM

- **Gravité** : mineur · **Étiquettes** : `T1`, `frontend`, `performance` · **Assigné** : Ali
- **Obtenu** : le cache des explications est en mémoire (`useRef`) : chaque rechargement relance
  `/explain` (vu 3 fois pour la même slide × niveau dans le journal). `agents/llm.py` sérialise les appels
  et une génération abandonnée continue côté serveur : les attentes s'additionnent.
- **Piste** : garder le cache dans `sessionStorage`, et/ou un cache côté API (slide × niveau × langue).

### Issue 13 ([#25](https://github.com/multi-agent-tutor/Multi-Agent-Tutor-DL/issues/25)) — [T1] Bundle JS de 529 Ko

- **Gravité** : mineur · **Étiquettes** : `T1`, `frontend` · **Assigné** : Ali
- **Obtenu** : `npm run build` avertit « Some chunks are larger than 500 kB ». **Piste** : charger KaTeX et
  les pages Quiz/Flashcards avec `import()` dynamique.
