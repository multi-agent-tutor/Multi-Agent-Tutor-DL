# C1 — Corpus de test

Objectif initial : 5 à 10 cours PPTX et PDF, en français et en anglais, de 15 à 60 slides chacun
(élargi : le plus de cours possible, de sources variées),
pour tester l'ingestion (H1–H3), le RAG (B1–B2) et les agents.

- **Ons** : cours riches en schémas, diagrammes et formules (maths, ML, réseaux).
- **Both** : cours riches en texte, dont au moins un PDF scanné (test de l'OCR).

Corpus complémentaire d'autres matières : `data/corpus_extra/` (Ghofrane, G2). Ne pas reprendre ces cours ici.

## Règles pour collecter en parallèle

1. **Rangement par langue puis par domaine** : `data/corpus/<langue>/<domaine>/<fichier>`,
   avec `<langue>` = `fr` ou `en` et `<domaine>` = `maths`, `ml`, `dl`, `reseaux` (ou un domaine de Both).
   Fichiers nommés `<domaine>_<sujet>_<source>_<langue>.<pdf|pptx>` : minuscules ASCII, chiffres et `_`,
   sans accent. Le nom sans extension sert de `course_id` (voir `docs/schema.md`) et doit être unique
   dans tout le corpus. Exemple : `en/dl/dl_deep_learning_louppe1_en.pdf`.
   - `maths` : probabilités, algèbre, analyse ;
   - `ml` : apprentissage automatique classique et optimisation (régression, gradient…) ;
   - `dl` : deep learning (réseaux de neurones, CNN, transformers, LLM) ;
   - `reseaux` : réseaux informatiques.
2. **Préfixes réservés**, pour éviter les doublons :
   - Ons : `maths_`, `ml_`, `dl_`, `reseaux_` ;
   - Both : les autres matières textuelles (`histoire_`, `droit_`, `bio_`…) et `scan_` pour un PDF scanné.
3. **Un inventaire par personne** : `inventaire_ons.csv` et `inventaire_both.csv`. Chacune ne modifie que le sien.
   Ce README n'est modifié que par Ons.
4. **Taille** : pas de fichier de plus de 20 Mo dans Git. Tous les cours d'Ons sont versionnés (décision d'Ons,
   2026-11-17), y compris les supports internes d'Esprit et les cours dont la licence est inconnue ;
   la source et l'auteur de chacun sont indiqués dans l'inventaire. `data/corpus/_local/` reste ignoré par Git
   pour les fichiers qu'on ne veut pas publier.
5. Commits préfixés `[C1]`, par exemple `[C1] ajout ml_reseaux_neurones_fr`.

## Format des inventaires

Mêmes premières colonnes que `data/corpus_extra/inventaire.csv`, puis des colonnes ajoutées :

| Colonne | Valeurs |
|---|---|
| `fichier` | chemin relatif à `data/corpus/` (`<langue>/<domaine>/<fichier>`) |
| `titre` | titre du cours |
| `source` | URL d'origine |
| `format` | `PDF` ou `PPTX` |
| `langue` | `fr`, `en`, `ar` ou `mixte` |
| `nombre_slides` | calculé avec `python tools/slide_stats.py <fichier>` |
| `licence` | ex. `CC BY-NC-SA 4.0`, `inconnue` |
| `collecte_par` | `ons` ou `both` |
| `contenu` | `figures`, `formules`, `texte`, combinés par `+` |
| `scanne` | `oui` ou `non` |
| `date_collecte` | `AAAA-MM-JJ` |

## Crédits

- `en/reseaux/reseaux_introduction_kurose_en.pptx` : slides identiques à celles de J.F. Kurose et K.W. Ross,
  *Computer Networking: A Top-Down Approach*, 9e édition, chapitre 1 (V9.0).
  © 1996-2025 J.F. Kurose et K.W. Ross, tous droits réservés.
  Source : https://gaia.cs.umass.edu/kurose_ross/ppt.php — diffusées par les auteurs pour un usage libre,
  à condition de citer la source et leur copyright.
- `en/dl/dl_fondements_louppe_en.pdf` et `en/dl/dl_perceptrons_louppe_en.pdf` : slides de Gilles Louppe,
  INFO8010 Deep Learning, Université de Liège (lectures 1 et 2). Source : https://github.com/glouppe/info8010-deep-learning,
  licence BSD-3-Clause.
- `en/dl/dl_introduction_uva_en.pdf` : slides d'Efstratios Gavves, UvA Deep Learning Course, lecture 1 (2019).
  Source : https://uvadlc.github.io, licence Apache-2.0.

## Répartition du corpus (Ons + Both, 2026-11-19)

**Total : 47 cours** (38 d'Ons + 9 de Both), 32 PDF et 15 PPTX, tous versionnés dans Git.
Noyaux de test : `noyau_ons.json` (10 cours) et `noyau_both.json` (6 cours).

### Corpus d'Ons

38 cours (25 PDF, 13 PPTX), tous versionnés dans Git. 4 ont une licence explicite (voir Crédits),
6 sont des supports internes d'Esprit, les autres ont une licence inconnue (source dans l'inventaire).

| Langue | maths | ml | dl | reseaux | Total |
|---|---|---|---|---|---|
| fr | 3 | 3 | 2 | 4 | 12 |
| en | 8 | 7 | 8 | 3 | 26 |
| **Total** | 11 | 10 | 10 | 7 | **38** |

Les PPTX de NTU (Hung-yi Lee) contiennent parfois quelques mots en chinois ; ils restent classés `en`.
Détail (titre, source, licence, nombre de slides) : `inventaire_ons.csv`.

Le chapitre 4 d'Optimisation pour le ML (Esprit, recherche linéaire) a été retiré du corpus d'Ons :
il est déjà collecté par Both (`fr/ml/ml_recherche_lineaire_esprit_fr.pdf`).

### Corpus de Both

9 cours (7 PDF, 2 PPTX), riches en texte, dont **2 PDF scannés** sans couche de texte pour tester l'OCR
(`en/maths/maths_jacobien_scan_uiowa_en.pdf`, `en/maths/maths_matrices_scan_uiowa_en.pdf`).
`en/ml/ml_introduction_mit_en.pdf` a un texte illisible à l'extraction (encodage de police) : bon cas de test pour l'OCR / le VLM.

| Langue | cloud | maths | ml | reseaux | bd | Total |
|---|---|---|---|---|---|---|
| fr | 0 | 0 | 1 | 1 | 1 | 3 |
| en | 2 | 2 | 2 | 0 | 0 | 6 |
| **Total** | 2 | 2 | 3 | 1 | 1 | **9** |

Détail (titre, source, licence, nombre de slides, remarques) : `inventaire_both.csv`.
Noyau de Both (`noyau_both.json`) : 6 cours ; les 2 scans (8 pages) et `reseaux_introduction_grenoble_fr` (64 slides) restent en réserve.

## Noyau de test (C1)

Le PDF de répartition prévoit 5 à 10 cours de test. Ons a retenu un **noyau de 10 cours** (`noyau_ons.json`),
utilisé en priorité pour H1–H3, B1–B2 et pour écrire les questions de C2 :

| Cours | Langue | Domaine | Format | Slides |
|---|---|---|---|---|
| `maths_vecteurs_gaussiens_brownien_esprit_fr` | fr | maths | PDF | 23 |
| `maths_probabilites_labri_fr` | fr | maths | PDF | 35 |
| `ml_gradient_stochastique_esprit_fr` | fr | ml | PDF | 24 |
| `dl_reseaux_convolutifs_cnam_fr` | fr | dl | PDF | 39 |
| `reseaux_transport_grenoble_fr` | fr | reseaux | PDF | 25 |
| `maths_valeurs_propres_ntu_en` | en | maths | PPTX | 19 |
| `ml_regression_uppsala_en` | en | ml | PDF | 42 |
| `dl_fondements_louppe_en` | en | dl | PDF | 57 |
| `dl_self_attention_ntu_en` | en | dl | PPTX | 43 |
| `reseaux_tcp_routage_liu_en` | en | reseaux | PDF | 57 |

Les 28 autres cours d'Ons restent en **réserve** (tests de robustesse, démo, réindexation).

**Cours de plus de 60 slides** : `reseaux_introduction_kurose_en` (89), `dl_perceptrons_louppe_en` (89),
`reseaux_introduction_ntu_en` (92), `dl_introduction_uva_en` (78), `ml_introduction_ensta_fr` (75),
`dl_reseaux_neurones_larochelle_fr` (67), `reseaux_adressage_routage_evry_fr` (63), `maths_probabilites_paris1_fr` (62),
`ml_regression_ntu_en` (61). Ils sont **gardés en réserve** pour tester l'ingestion sur des cours longs,
mais n'entrent pas dans le noyau.

`tests/test_corpus.py` vérifie les inventaires (fichiers présents, `course_id` valides et uniques,
rangement `<langue>/<domaine>/`, taille ≤ 20 Mo) et le noyau (5 à 10 cours, 15 à 60 slides, FR + EN, PDF + PPTX).
