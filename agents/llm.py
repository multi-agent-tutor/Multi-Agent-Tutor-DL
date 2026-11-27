"""Moteur LLM 100 % local partagé par les agents, configuré par ``.env``.

Règle d'équipe : aucune API externe et aucun appel réseau à l'exécution. Ce module est le
seul endroit qui parle au LLM, pour qu'on puisse changer de moteur sans toucher aux agents.

Interface publique :

- ``generer_structure(system, prompt, schema, *, max_tokens)`` : réponse validée par un
  modèle Pydantic ;
- ``generer_texte(system, prompt, *, max_tokens)`` : réponse en texte libre ;
- ``est_configure()`` : un appel a-t-il une chance d'aboutir ?
- ``LLMIndisponible`` : levée en cas d'échec, à l'agent de prévoir un repli.

Variables d'environnement (voir ``.env.example`` et ``docs/llm_local.md``) :

- ``LLM_BACKEND`` : ``llamacpp`` (défaut) | ``transformers`` | ``fake`` ;
- ``LLM_MODEL_PATH`` : fichier GGUF pour ``llamacpp``
  (``models/qwen2.5-3b-instruct-q4_k_m.gguf`` par défaut, relatif à la racine du dépôt) ;
- ``LLM_N_CTX`` : taille du contexte pour ``llamacpp`` (4096 par défaut) ;
- ``LLM_N_THREADS`` : nombre de threads CPU pour ``llamacpp`` (auto par défaut) ;
- ``LLM_MODEL`` : identifiant ou dossier local pour ``transformers``
  (``Qwen/Qwen2.5-1.5B-Instruct`` par défaut, lu dans le cache local uniquement) ;
- ``LLM_TEMPERATURE`` : température d'échantillonnage (0.2 par défaut).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

# Interdire tout téléchargement depuis le Hub Hugging Face, quel que soit le backend.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RACINE = Path(__file__).resolve().parents[1]
BACKENDS = ("llamacpp", "transformers", "fake")
BACKEND_PAR_DEFAUT = "llamacpp"
MODELE_GGUF_PAR_DEFAUT = "models/qwen2.5-3b-instruct-q4_k_m.gguf"
MODELE_HF_PAR_DEFAUT = "Qwen/Qwen2.5-1.5B-Instruct"
N_CTX_PAR_DEFAUT = 4096
TEMPERATURE_PAR_DEFAUT = 0.2

# Un seul modèle en mémoire, et une seule génération à la fois (llama.cpp n'est pas thread-safe).
_verrou = threading.Lock()


class LLMIndisponible(RuntimeError):
    """Le LLM n'a pas pu répondre (modèle absent, dépendance manquante, sortie invalide…)."""


# --------------------------------------------------------------------------- configuration


def backend() -> str:
    return os.getenv("LLM_BACKEND", BACKEND_PAR_DEFAUT).strip().lower()


def chemin_modele() -> Path:
    """Chemin du fichier GGUF ; un chemin relatif part de la racine du dépôt."""
    chemin = Path(os.getenv("LLM_MODEL_PATH", MODELE_GGUF_PAR_DEFAUT).strip())
    return chemin if chemin.is_absolute() else RACINE / chemin


def modele() -> str:
    """Nom lisible du modèle utilisé par le backend courant."""
    b = backend()
    if b == "llamacpp":
        return chemin_modele().name
    if b == "transformers":
        return os.getenv("LLM_MODEL", MODELE_HF_PAR_DEFAUT).strip()
    return b


def _entier_env(nom: str, defaut: int | None) -> int | None:
    valeur = os.getenv(nom, "").strip()
    return int(valeur) if valeur else defaut


def _temperature() -> float:
    valeur = os.getenv("LLM_TEMPERATURE", "").strip()
    return float(valeur) if valeur else TEMPERATURE_PAR_DEFAUT


def _transformers_en_cache(nom: str) -> bool:
    if Path(nom).is_dir():
        return True
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(nom, "config.json"), str)


def est_configure() -> bool:
    """Indiquer si un appel a une chance d'aboutir, sans charger le modèle."""
    b = backend()
    if b == "fake":
        return True
    if b == "llamacpp":
        return importlib.util.find_spec("llama_cpp") is not None and chemin_modele().is_file()
    if b == "transformers":
        return (
            importlib.util.find_spec("transformers") is not None
            and importlib.util.find_spec("torch") is not None
            and _transformers_en_cache(modele())
        )
    return False


# --------------------------------------------------------------------------- chargement (singletons)


@lru_cache(maxsize=1)
def _charger_llamacpp(chemin: str, n_ctx: int, n_threads: int | None) -> Any:
    if not Path(chemin).is_file():
        raise LLMIndisponible(f"modèle GGUF introuvable : {chemin} (voir docs/llm_local.md)")
    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise LLMIndisponible("llama-cpp-python n'est pas installé (voir docs/llm_local.md)") from e
    log.info("chargement de %s (n_ctx=%d)", chemin, n_ctx)
    try:
        return Llama(model_path=chemin, n_ctx=n_ctx, n_threads=n_threads, verbose=False)
    except Exception as e:  # noqa: BLE001 - llama.cpp lève ValueError/RuntimeError selon les cas
        raise LLMIndisponible(f"échec du chargement de {chemin} : {e}") from e


@lru_cache(maxsize=1)
def _charger_transformers(nom: str) -> tuple[Any, Any]:
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise LLMIndisponible("transformers/torch ne sont pas installés (voir docs/llm_local.md)") from e
    log.info("chargement de %s (hors ligne)", nom)
    try:
        tokenizer = AutoTokenizer.from_pretrained(nom, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(nom, local_files_only=True, torch_dtype="auto")
    except OSError as e:
        raise LLMIndisponible(f"modèle {nom} absent du cache local : {e}") from e
    model.eval()
    return tokenizer, model


def _llama() -> Any:
    return _charger_llamacpp(
        str(chemin_modele()),
        _entier_env("LLM_N_CTX", N_CTX_PAR_DEFAUT) or N_CTX_PAR_DEFAUT,
        _entier_env("LLM_N_THREADS", None),
    )


def reinitialiser() -> None:
    """Décharger les modèles (utile pour les tests ou après un changement de ``.env``)."""
    _charger_llamacpp.cache_clear()
    _charger_transformers.cache_clear()


# --------------------------------------------------------------------------- génération brute


def _messages(system: str, prompt: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


# llama.cpp déroule ``maxLength`` / ``maxItems`` en options imbriquées : au-delà, la conversion
# du schéma en grammaire échoue (« grammar recursion depth limit exceeded (max 256) ») ou plante.
# Un ``maxLength`` > MAX_LENGTH_GRAMMAIRE est donc retiré du schéma envoyé (le ramener à 200
# coupait les phrases en plein milieu) : ``max_tokens`` borne la longueur réelle de la sortie.
# ``maxItems`` est plafonné (le Critic juge jusqu'à 8 affirmations).
MAX_LENGTH_GRAMMAIRE = 200
MAX_ITEMS_GRAMMAIRE = 10


def borner_schema(schema: Any) -> Any:
    """Copie du schéma JSON rendue convertible en grammaire par llama.cpp.

    - ``maxLength`` > ``MAX_LENGTH_GRAMMAIRE`` : supprimé ; sinon conservé tel quel ;
    - ``maxItems`` > ``MAX_ITEMS_GRAMMAIRE`` : ramené au plafond ;
    - ``minLength`` / ``minItems`` : ramenés sous le même plafond (et sous le max restant)
      pour garder un schéma cohérent et une grammaire de profondeur bornée.

    Seule la grammaire est concernée : la validation Pydantic garde les limites d'origine.
    """
    if isinstance(schema, list):
        return [borner_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    borne = {cle: borner_schema(valeur) for cle, valeur in schema.items()}
    if isinstance(borne.get("maxLength"), int) and borne["maxLength"] > MAX_LENGTH_GRAMMAIRE:
        del borne["maxLength"]
    if isinstance(borne.get("maxItems"), int) and borne["maxItems"] > MAX_ITEMS_GRAMMAIRE:
        borne["maxItems"] = MAX_ITEMS_GRAMMAIRE
    for maxi, mini, plafond in (("maxLength", "minLength", MAX_LENGTH_GRAMMAIRE),
                                ("maxItems", "minItems", MAX_ITEMS_GRAMMAIRE)):
        if isinstance(borne.get(mini), int):
            limite = borne[maxi] if isinstance(borne.get(maxi), int) else plafond
            borne[mini] = min(borne[mini], limite, plafond)
    return borne


def _brut_llamacpp(messages: list[dict[str, str]], max_tokens: int,
                   schema_json: dict[str, Any] | None) -> str:
    llama = _llama()
    options: dict[str, Any] = {"max_tokens": max_tokens, "temperature": _temperature()}
    if schema_json is not None:
        options["response_format"] = {"type": "json_object", "schema": borner_schema(schema_json)}
    try:
        with _verrou:
            reponse = llama.create_chat_completion(messages=messages, **options)
    except ValueError as e:
        if "exceed context window" in str(e):
            raise LLMIndisponible(f"prompt trop long pour LLM_N_CTX : {e}") from e
        raise LLMIndisponible(f"llama.cpp : {e}") from e
    except Exception as e:  # noqa: BLE001 - p. ex. grammaire JSON non convertible
        raise LLMIndisponible(f"llama.cpp : {e}") from e
    return reponse["choices"][0]["message"]["content"] or ""


def _brut_transformers(messages: list[dict[str, str]], max_tokens: int) -> str:
    tokenizer, model = _charger_transformers(modele())
    import torch

    texte = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    entrees = tokenizer([texte], return_tensors="pt").to(model.device)
    temperature = _temperature()
    with _verrou, torch.no_grad():
        sorties = model.generate(
            **entrees,
            max_new_tokens=max_tokens,
            do_sample=temperature > 0,
            temperature=temperature if temperature > 0 else None,
            top_p=None,
            top_k=None,
        )
    generes = sorties[0][entrees["input_ids"].shape[1]:]
    return tokenizer.decode(generes, skip_special_tokens=True)


def _brut(messages: list[dict[str, str]], max_tokens: int, schema_json: dict[str, Any] | None) -> str:
    b = backend()
    if b == "llamacpp":
        return _brut_llamacpp(messages, max_tokens, schema_json)
    if b == "transformers":
        return _brut_transformers(messages, max_tokens)
    raise LLMIndisponible(f"LLM_BACKEND inconnu : {b!r} (attendu : {', '.join(BACKENDS)})")


# --------------------------------------------------------------------------- backend fake


def _exemple(schema: dict[str, Any], defs: dict[str, Any]) -> Any:
    """Construire une valeur minimale et déterministe conforme à un schéma JSON."""
    if "$ref" in schema:
        return _exemple(defs[schema["$ref"].split("/")[-1]], defs)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    for cle in ("anyOf", "oneOf", "allOf"):
        if cle in schema:
            options = [s for s in schema[cle] if s.get("type") != "null"] or schema[cle]
            return _exemple(options[0], defs)
    type_ = schema.get("type", "string")
    if isinstance(type_, list):
        type_ = next((t for t in type_ if t != "null"), "null")
    if type_ == "object":
        proprietes = schema.get("properties", {})
        return {nom: _exemple(sous, defs) for nom, sous in proprietes.items()}
    if type_ == "array":
        return [_exemple(schema.get("items", {}), defs) for _ in range(schema.get("minItems", 0))]
    if type_ in ("integer", "number"):
        valeur = schema.get("minimum", schema.get("exclusiveMinimum", -1) + 1)
        return int(valeur) if type_ == "integer" else float(valeur)
    if type_ == "boolean":
        return False
    if type_ == "null":
        return None
    texte = "fake".ljust(schema.get("minLength", 0), "x")
    return texte[: schema["maxLength"]] if "maxLength" in schema else texte


def _fake_structure(schema: type[T]) -> T:
    impose = os.getenv("LLM_FAKE_REPONSE", "").strip()
    if impose:
        return schema.model_validate_json(impose)
    schema_json = schema.model_json_schema()
    return schema.model_validate(_exemple(schema_json, schema_json.get("$defs", {})))


def _fake_texte(system: str, prompt: str) -> str:
    impose = os.getenv("LLM_FAKE_REPONSE", "").strip()
    return impose or f"[fake] réponse à : {prompt[:80]}"


# --------------------------------------------------------------------------- interface publique


def _extraire_json(texte: str) -> str:
    """Isoler le premier objet JSON d'une réponse (le backend transformers n'est pas contraint)."""
    debut, fin = texte.find("{"), texte.rfind("}")
    return texte[debut:fin + 1] if 0 <= debut < fin else texte


def _message_correction(erreur: ValidationError) -> str:
    """Consigne de la 2e tentative ; un JSON invalide signale en pratique une sortie coupée
    par ``max_tokens`` (la grammaire garantit sinon la syntaxe) : on demande alors plus court."""
    if any(detail.get("type") == "json_invalid" for detail in erreur.errors()):
        return (
            "Ta réponse a été coupée avant la fin : le JSON est incomplet. Renvoie un JSON complet "
            "et nettement plus court (phrases plus brèves, moins de détails)."
        )
    return f"Ta réponse est invalide :\n{erreur}\nRenvoie un JSON corrigé."


def generer_texte(system: str, prompt: str, *, max_tokens: int = 1024) -> str:
    """Appeler le LLM local et renvoyer sa réponse en texte libre.

    Lève ``LLMIndisponible`` en cas d'échec : à l'agent de prévoir un repli.
    """
    if backend() == "fake":
        return _fake_texte(system, prompt)
    texte = _brut(_messages(system, prompt), max_tokens, None).strip()
    if not texte:
        raise LLMIndisponible("réponse vide")
    return texte


def generer_structure(system: str, prompt: str, schema: type[T], *, max_tokens: int = 4096) -> T:
    """Appeler le LLM local et renvoyer une réponse validée par le modèle Pydantic ``schema``.

    Avec ``llamacpp``, la sortie est contrainte par une grammaire dérivée du schéma JSON. Si la
    réponse ne passe pas la validation Pydantic, une seconde tentative est faite en renvoyant
    l'erreur au modèle. Lève ``LLMIndisponible`` en cas d'échec : à l'agent de prévoir un repli.
    """
    if backend() == "fake":
        try:
            return _fake_structure(schema)
        except ValidationError as e:
            raise LLMIndisponible(f"LLM_FAKE_REPONSE invalide pour {schema.__name__} : {e}") from e

    schema_json = schema.model_json_schema()
    consigne = (
        f"{system}\n\nRéponds uniquement par un objet JSON conforme à ce schéma, sans texte autour :\n"
        f"{json.dumps(schema_json, ensure_ascii=False)}"
    )
    messages = _messages(consigne, prompt)
    derniere_erreur: Exception | None = None
    for tentative in range(2):
        texte = _brut(messages, max_tokens, schema_json)
        try:
            return schema.model_validate_json(_extraire_json(texte))
        except ValidationError as e:
            derniere_erreur = e
            log.info("sortie invalide (tentative %d) : %s", tentative + 1, e)
            messages = [
                *messages,
                {"role": "assistant", "content": texte},
                {"role": "user", "content": _message_correction(e)},
            ]
    raise LLMIndisponible(f"sortie invalide après 2 tentatives : {derniere_erreur}")


__all__ = [
    "LLMIndisponible",
    "backend",
    "borner_schema",
    "chemin_modele",
    "est_configure",
    "generer_structure",
    "generer_texte",
    "modele",
    "reinitialiser",
]
