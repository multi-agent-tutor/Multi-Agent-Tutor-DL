# LLM 100 % local (A0)

Règle d'équipe : **aucune API externe**, ni payante ni gratuite, et **aucun appel réseau à
l'exécution**. Tous les agents passent par [`agents/llm.py`](../agents/llm.py), qui fait tourner
un modèle sur la machine (CPU). Le réseau ne sert qu'une fois, à l'installation.

## 1. Installation

Depuis la racine du dépôt, dans le `.venv` :

```powershell
# Roue CPU précompilée de llama-cpp-python (évite de compiler du C++ sous Windows)
.venv\Scripts\pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
.venv\Scripts\pip install -r requirements.txt

# Modèle GGUF (~2 Go), une seule fois ; models/ est ignoré par Git
.venv\Scripts\hf download Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf --local-dir models
```

Vérifier :

```powershell
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python -c "from agents import llm; print(llm.est_configure(), llm.modele()); print(llm.generer_texte('Tu es concis.', 'Dis bonjour.', max_tokens=20))"
```

### Backend optionnel `transformers`

Plus lourd (torch), à n'utiliser que si llama.cpp pose problème :

```powershell
.venv\Scripts\pip install transformers torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\hf download Qwen/Qwen2.5-1.5B-Instruct   # remplit le cache local, une seule fois
```

Ensuite le modèle est lu **hors ligne** : `agents/llm.py` force `HF_HUB_OFFLINE=1`.

## 2. Variables `.env`

Copier `.env.example` en `.env`. Toutes ont une valeur par défaut, le fichier est facultatif.

| Variable | Défaut | Rôle |
|---|---|---|
| `LLM_BACKEND` | `llamacpp` | `llamacpp`, `transformers` ou `fake` (réponses déterministes, pour les tests) |
| `LLM_MODEL_PATH` | `models/qwen2.5-3b-instruct-q4_k_m.gguf` | fichier GGUF (relatif à la racine du dépôt) |
| `LLM_N_CTX` | `4096` | taille du contexte (prompt + réponse) en tokens |
| `LLM_N_THREADS` | auto | threads CPU pour llama.cpp |
| `LLM_MODEL` | `Qwen/Qwen2.5-1.5B-Instruct` | modèle du backend `transformers` (id du cache ou dossier) |
| `LLM_TEMPERATURE` | `0.2` | température d'échantillonnage |
| `LLM_FAKE_REPONSE` | — | backend `fake` : JSON (ou texte) renvoyé tel quel |

## 3. Interface

```python
from agents import llm

llm.est_configure()                                     # bool, sans charger le modèle
llm.generer_structure(system, prompt, Schema, max_tokens=4096)  # -> instance Pydantic
llm.generer_texte(system, prompt, max_tokens=1024)              # -> str
llm.LLMIndisponible                                     # levée en cas d'échec
```

- Le modèle est chargé **une seule fois** (au premier appel) puis réutilisé ; les appels
  sont sérialisés (un seul à la fois).
- `generer_structure` force une sortie JSON conforme au schéma (grammaire llama.cpp), la
  valide avec Pydantic et fait **une nouvelle tentative** si elle est invalide.
- `LLMIndisponible` si le fichier modèle est absent, la dépendance manquante, le prompt trop
  long pour `LLM_N_CTX`, ou la sortie toujours invalide. **Chaque agent doit prévoir un repli.**
- Ordre de grandeur sur CPU : 5 à 15 s de chargement, puis quelques secondes à ~45 s par
  réponse selon `max_tokens`. Garder des schémas simples et des `max_tokens` serrés.

## 4. Exemples par membre

Schémas à garder **petits et plats** : un modèle 3B suit mieux un schéma court.

### Ons — génération de QCM

```python
from agents import llm
from api.models import QCM

try:
    qcm = llm.generer_structure(
        "Tu es un tuteur. Tu crées un QCM en français à partir d'un extrait de cours.",
        f"Extrait (cours {course_id}, slide {numero}) :\n{texte_slide}\n\nCrée un QCM.",
        QCM,
        max_tokens=500,
    )
except llm.LLMIndisponible:
    qcm = None  # repli : QCM du jeu de données, ou message d'erreur côté API
```

### Both — réponse libre à une question d'étudiant

```python
from agents import llm

try:
    reponse = llm.generer_texte(
        "Tu es un tuteur patient. Réponds en français, en t'appuyant uniquement sur le contexte.",
        f"Contexte :\n{passages}\n\nQuestion : {question}",
        max_tokens=400,
    )
except llm.LLMIndisponible:
    reponse = "Le tuteur n'est pas disponible pour le moment."
```

### Ghayth — analyse structurée d'une slide

```python
from pydantic import BaseModel, Field
from agents import llm

class Analyse(BaseModel):
    notions: list[str] = Field(max_length=5)
    difficulte: int = Field(ge=1, le=3)

try:
    analyse = llm.generer_structure(
        "Tu extrais les notions clés d'une slide de cours.",
        texte_slide,
        Analyse,
        max_tokens=200,
    )
except llm.LLMIndisponible:
    analyse = Analyse(notions=[], difficulte=2)
```

## 5. Tests

```powershell
.venv\Scripts\python -m pytest
```

Les tests n'ont pas besoin du modèle : `tests/test_llm.py` utilise `LLM_BACKEND=fake` et un
faux `Llama`. Dans vos propres tests, choisir l'une des deux options :

```python
monkeypatch.setenv("LLM_BACKEND", "fake")                        # réponse minimale valide
monkeypatch.setenv("LLM_FAKE_REPONSE", '{"question": "…", ...}')  # réponse imposée
# ou, pour tester le repli :
monkeypatch.setenv("LLM_MODEL_PATH", "models/absent.gguf")        # -> LLMIndisponible
```
