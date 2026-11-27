# T1 — Checklist de tests manuels

Responsable : Ghayth. Phase S5, dépend de A5 (frontend). Chaque bug trouvé → une issue GitHub
(modèle en bas de page). Statut : **checklist prête, campagne à lancer quand A5 est livré.**

## Cours de test (au moins 3, formats et langues variés)

| # | Cours | Pourquoi |
|---|---|---|
| C-A | `fr/dl/dl_reseaux_convolutifs_cnam_fr.pdf` | PDF FR riche en figures |
| C-B | `en/dl/dl_self_attention_ntu_en.pptx` | PPTX EN avec notes, schémas et formules |
| C-C | `en/maths/maths_matrices_scan_uiowa_en.pdf` | PDF scanné manuscrit (OCR + VLM) |
| C-D | `en/dl/dl_fondements_louppe_en.pdf` | PDF decktape (couche texte trouée) |

Environnement à noter dans chaque issue : OS, navigateur, commit testé, `LLM_BACKEND`, `VLM_BACKEND`.

## 0. Pré-requis

- [ ] `pip install -r requirements.txt` sans erreur ; `pytest` vert
- [ ] Modèles présents dans `models/` (LLM A0, VLM H2) ; `.env` copié depuis `.env.example`
- [ ] Backend lancé (`uvicorn api.main:app`), `GET /health` OK, Swagger `/docs` accessible
- [ ] Frontend lancé, aucune erreur dans la console du navigateur

## 1. Upload et ingestion

- [ ] Upload d'un PDF → le cours apparaît, nombre de slides correct
- [ ] Upload d'un PPTX → rendus des slides affichés (pas d'image cassée)
- [ ] Upload d'un fichier non pris en charge (`.docx`, `.png`) → message d'erreur clair, pas de crash
- [ ] Upload d'un fichier vide ou corrompu → erreur claire
- [ ] Gros fichier (60 slides) → indicateur de progression, pas de timeout
- [ ] Ré-upload du même cours → pas de doublon, cache VLM réutilisé (plus rapide)
- [ ] PDF scanné (C-C) → texte OCR ou description VLM présents sur chaque slide

## 2. Navigation

- [ ] Slide suivante / précédente, première / dernière (bornes respectées)
- [ ] Saut direct à une slide (n° ou miniature)
- [ ] Le numéro affiché correspond à la slide rendue
- [ ] Rechargement de la page → on reste sur la même slide / le même cours
- [ ] Affichage correct en largeur mobile (≈ 375 px)

## 3. Explication par niveau (Explainer, O2)

- [ ] Débutant : analogies, pas de jargon non expliqué
- [ ] Intermédiaire / avancé : formules présentes et rendues par KaTeX (pas de LaTeX brut)
- [ ] Structure : idée clé → explication → exemple → lien avec la slide précédente → à retenir
- [ ] Les figures de la slide sont mentionnées (description VLM utilisée)
- [ ] Les prérequis cités viennent de slides antérieures (carte du cours H3)
- [ ] Changement de niveau → l'explication change réellement
- [ ] Slide de titre / plan → explication courte et cohérente, pas d'hallucination

## 4. Q&A avec citations (B3)

- [ ] Question factuelle → bonne réponse avec citations `[Slide N]`
- [ ] Clic sur `[Slide N]` → navigation vers la bonne slide
- [ ] Question sur une figure → réponse qui s'appuie sur la figure
- [ ] Question hors cours → refus explicite (« pas dans le cours »)
- [ ] Question en anglais sur un cours FR (et inversement) → réponse dans la langue demandée
- [ ] Historique : question de suivi (« et pourquoi ? ») comprise
- [ ] Question vide ou très longue → pas de crash

## 5. Quiz (A2)

- [ ] QCM générés pour la slide et pour le chapitre
- [ ] Une seule bonne réponse par question ; distracteurs plausibles mais faux
- [ ] Feedback immédiat + explication après chaque réponse
- [ ] Score final correct
- [ ] Niveaux de Bloom variés (mémoriser, comprendre, appliquer, analyser)

## 6. Flashcards et révision espacée (A6)

- [ ] Recto / verso, retournement de la carte
- [ ] Notation (0–5) → prochaine date de révision cohérente (SM-2)
- [ ] Cartes « à réviser » filtrées par date
- [ ] Export `.apkg` → import dans Anki sans erreur

## 7. Ressources (A4)

- [ ] 3 à 5 ressources par slide, en rapport avec les concepts
- [ ] Liens valides ; type (vidéo / article) et justification affichés

## 8. Narration TTS et multilingue (A7)

- [ ] Bouton lecture → audio de l'explication, pause / reprise
- [ ] Sélecteur FR / EN / AR → explication, Q&A et audio dans la langue choisie
- [ ] Arabe : affichage de droite à gauche correct

## 9. Robustesse et performance

- [ ] Temps de réponse noté pour l'explication et le Q&A (objectif < 30 s sur CPU)
- [ ] LLM absent ou arrêté → message d'erreur clair, pas de page blanche
- [ ] Deux onglets en parallèle → pas de mélange entre cours

## Suivi de la campagne

| Section | C-A | C-B | C-C | C-D | Issues |
|---|---|---|---|---|---|
| 1. Upload | | | | | |
| 2. Navigation | | | | | |
| 3. Explication | | | | | |
| 4. Q&A | | | | | |
| 5. Quiz | | | | | |
| 6. Flashcards | | | | | |
| 7. Ressources | | | | | |
| 8. TTS / langues | | | | | |
| 9. Robustesse | | | | | |

## Modèle d'issue GitHub

```markdown
**[T1] <titre court du bug>**

- Section de la checklist : 4. Q&A
- Cours : dl_self_attention_ntu_en (slide 12)
- Environnement : Windows 11, Chrome 131, commit abc1234, LLM_BACKEND=llamacpp

**Étapes pour reproduire**
1. ...
2. ...

**Résultat attendu** : ...
**Résultat obtenu** : ...
**Capture** : (glisser l'image ici)
**Gravité** : bloquant | majeur | mineur
```

Étiquettes : `bug`, `T1`, et le module concerné (`ingestion`, `rag`, `agents`, `api`, `frontend`).
Assigner la personne responsable du module (voir le README).
