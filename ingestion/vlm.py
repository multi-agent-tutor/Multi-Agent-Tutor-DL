"""H2 — VLM local pour décrire les figures et retranscrire les formules en LaTeX.

Point d'entrée : ``enrich_with_vlm(course) -> Course`` (contrat T0, voir ``docs/schema.md``).
Remplit ``description_figures`` et ``formules_latex`` de chaque slide à partir de son rendu PNG (H1).

Règle d'équipe (v2) : 100 % local, aucune API externe. Le modèle par défaut est
Qwen2.5-VL-3B-Instruct en GGUF, exécuté par llama.cpp (voir ``ingestion/README.md``).

- Seules les slides au contenu visuel (images, schémas vectoriels, formules, scans) sont envoyées
  au VLM, sauf avec ``toutes=True`` : un appel coûte de l'ordre d'une minute sur CPU.
- Chaque résultat est mis en cache dans ``data/cache/vlm/`` (clé : empreinte de l'image, modèle,
  version du prompt et langue) : le VLM n'est jamais rappelé pour une slide déjà analysée.

Variables d'environnement (toutes facultatives) :

- ``VLM_BACKEND`` : ``llamacpp`` (défaut) | ``transformers`` | ``fake`` | ``aucun`` ;
- ``VLM_MODEL_PATH`` / ``VLM_MMPROJ_PATH`` : GGUF du modèle et du projecteur d'images ;
- ``VLM_N_CTX`` (4096), ``VLM_N_THREADS`` (auto), ``VLM_N_GPU_LAYERS`` (0) ;
- ``VLM_MAX_COTE`` : plus grand côté de l'image envoyée, en px (896) ;
- ``VLM_MODEL`` : modèle du backend ``transformers`` (``Qwen/Qwen2.5-VL-3B-Instruct``, cache local) ;
- ``VLM_FAKE_REPONSE`` : backend ``fake``, JSON renvoyé tel quel.

Usage : ``python -m ingestion.vlm <course_id> [...] [--toutes] [--force]``.
"""

from __future__ import annotations

import argparse
import atexit
import base64
import hashlib
import importlib.util
import io
import json
import logging
import os
import re
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from schemas import Course, Slide

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_CACHE = RACINE / "data" / "cache" / "vlm"

VERSION_PROMPT = "h2-v2"
MODELE_GGUF = "models/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
MMPROJ_GGUF = "models/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf"
MODELE_HF = "Qwen/Qwen2.5-VL-3B-Instruct"
MAX_TOKENS = 768

_verrou = threading.Lock()

_INDICES_MATHS = re.compile(r"[=∑∫√≤≥≈∂∇∈∀∃→⇒±×÷∞αβγδεθλμσφψωΣΠΔΩ]|\^|_\{|\\[a-z]+")


class VLMIndisponible(RuntimeError):
    """Le VLM n'a pas pu répondre (modèle absent, dépendance manquante, sortie invalide…)."""


class AnalyseVisuelle(BaseModel):
    """Sortie attendue du VLM pour une slide."""

    figures: list[str] = Field(default_factory=list, max_length=8)
    formules: list[str] = Field(default_factory=list, max_length=16)


# --------------------------------------------------------------------------- configuration


def backend() -> str:
    return os.getenv("VLM_BACKEND", "llamacpp").strip().lower()


def _chemin(variable: str, defaut: str) -> Path:
    chemin = Path(os.getenv(variable, defaut).strip())
    return chemin if chemin.is_absolute() else RACINE / chemin


def _entier(variable: str, defaut: int | None) -> int | None:
    valeur = os.getenv(variable, "").strip()
    return int(valeur) if valeur else defaut


def modele() -> str:
    b = backend()
    if b == "llamacpp":
        return _chemin("VLM_MODEL_PATH", MODELE_GGUF).name
    if b == "transformers":
        return os.getenv("VLM_MODEL", MODELE_HF).strip()
    return b


def est_configure() -> bool:
    """Indiquer si un appel a une chance d'aboutir, sans charger le modèle."""
    b = backend()
    if b == "fake":
        return True
    if b == "llamacpp":
        return (importlib.util.find_spec("llama_cpp") is not None
                and _chemin("VLM_MODEL_PATH", MODELE_GGUF).is_file()
                and _chemin("VLM_MMPROJ_PATH", MMPROJ_GGUF).is_file())
    if b == "transformers":
        return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None
    return False


# --------------------------------------------------------------------------- prompt


def _consignes(langue: str) -> tuple[str, str]:
    if langue == "en":
        system = ("You analyse one slide of a university course for a tutoring system. "
                  "You answer only with JSON.")
        consigne = (
            "Look at the slide image and return a JSON object with two lists:\n"
            '- "figures": exactly one entry per distinct diagram, chart, plot, table drawn as an image, '
            "schematic or meaningful photo (never two entries for the same figure). In 1 to 3 sentences, "
            "explain what it shows (components, arrows, axes, trends, relationships) so that a student "
            "who cannot see it understands it. Formulas, logos, decorative pictures and plain text are "
            "not figures. Empty list if there is no figure.\n"
            '- "formules": every distinct mathematical formula or equation visible on the slide, in '
            "LaTeX without $ delimiters (use commands such as \\sum, \\frac, \\alpha, _ and ^), each "
            "formula written once. Empty list if there is none.\n"
            "Do not invent anything that is not visible.")
        contexte = "Text already extracted from the slide (do not copy it into the figures):"
    else:
        system = ("Tu analyses une slide de cours universitaire pour un tuteur pédagogique. "
                  "Tu réponds uniquement en JSON.")
        consigne = (
            "Observe l'image de la slide et renvoie un objet JSON avec deux listes :\n"
            '- "figures" : exactement une entrée par schéma, graphique, courbe, tableau dessiné en image, '
            "diagramme ou photo utile (jamais deux entrées pour la même figure). En 1 à 3 phrases en "
            "français, explique ce qu'il montre (éléments, flèches, axes, tendances, relations) pour "
            "qu'un étudiant qui ne le voit pas le comprenne. Les formules, logos, images décoratives et "
            "le texte simple ne sont pas des figures. Liste vide s'il n'y a pas de figure.\n"
            '- "formules" : chaque formule ou équation mathématique distincte visible, en vrai LaTeX sans '
            "délimiteurs $ (avec des commandes comme \\sum, \\frac, \\alpha, _ et ^), chacune écrite une "
            "seule fois. Liste vide s'il n'y en a pas.\n"
            "N'invente rien qui ne soit pas visible.")
        contexte = "Texte déjà extrait de la slide (ne pas le recopier dans les figures) :"
    return system, f"{consigne}\n\n{contexte}\n{{texte}}"


def _prompt(slide: Slide, langue: str) -> tuple[str, str]:
    system, modele_prompt = _consignes(langue)
    texte = "\n".join(x for x in (slide.titre, slide.texte) if x)[:800] or "(aucun)"
    return system, modele_prompt.replace("{texte}", texte)


# --------------------------------------------------------------------------- image


def _image_data_uri(chemin: Path) -> tuple[str, bytes]:
    """Image réduite (plus grand côté ``VLM_MAX_COTE``) en data URI PNG, et ses octets."""
    from PIL import Image

    max_cote = _entier("VLM_MAX_COTE", 896) or 896
    with Image.open(chemin) as img:
        img = img.convert("RGB")
        img.thumbnail((max_cote, max_cote))
        tampon = io.BytesIO()
        img.save(tampon, "PNG")
    octets = tampon.getvalue()
    return "data:image/png;base64," + base64.b64encode(octets).decode(), octets


# --------------------------------------------------------------------------- backends


@lru_cache(maxsize=1)
def _charger_llamacpp(modele_path: str, mmproj_path: str, n_ctx: int, n_threads: int | None,
                      n_gpu_layers: int) -> Any:
    for chemin in (modele_path, mmproj_path):
        if not Path(chemin).is_file():
            raise VLMIndisponible(f"fichier GGUF introuvable : {chemin} (voir ingestion/README.md)")
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Qwen25VLChatHandler
    except ImportError as e:
        raise VLMIndisponible("llama-cpp-python (avec Qwen25VLChatHandler) n'est pas installé") from e
    log.info("chargement du VLM %s", Path(modele_path).name)
    try:
        handler = Qwen25VLChatHandler(clip_model_path=mmproj_path, verbose=False)
        llm = Llama(model_path=modele_path, chat_handler=handler, n_ctx=n_ctx, n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers, verbose=False)
    except Exception as e:  # noqa: BLE001
        raise VLMIndisponible(f"échec du chargement du VLM : {e}") from e
    # Fermer avant l'arrêt de l'interpréteur (sinon llama-cpp lève une erreur dans __del__).
    atexit.register(_fermer, llm)
    return llm


def _fermer(llm: Any) -> None:
    try:
        llm.close()
    except Exception:  # noqa: BLE001
        pass


def _appel_llamacpp(system: str, prompt: str, data_uri: str, temperature: float = 0.1) -> str:
    llm = _charger_llamacpp(
        str(_chemin("VLM_MODEL_PATH", MODELE_GGUF)), str(_chemin("VLM_MMPROJ_PATH", MMPROJ_GGUF)),
        _entier("VLM_N_CTX", 4096) or 4096, _entier("VLM_N_THREADS", None), _entier("VLM_N_GPU_LAYERS", 0) or 0,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": prompt},
        ]},
    ]
    try:
        with _verrou:
            reponse = llm.create_chat_completion(
                messages=messages, max_tokens=MAX_TOKENS, temperature=temperature, repeat_penalty=1.15,
                response_format={"type": "json_object", "schema": AnalyseVisuelle.model_json_schema()},
            )
    except Exception as e:  # noqa: BLE001
        raise VLMIndisponible(f"llama.cpp : {e}") from e
    return reponse["choices"][0]["message"]["content"] or ""


@lru_cache(maxsize=1)
def _charger_transformers(nom: str) -> tuple[Any, Any]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    except ImportError as e:
        raise VLMIndisponible("transformers/torch ne sont pas installés") from e
    try:
        processor = AutoProcessor.from_pretrained(nom, local_files_only=True)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(nom, local_files_only=True,
                                                                   torch_dtype="auto", device_map="auto")
    except OSError as e:
        raise VLMIndisponible(f"modèle {nom} absent du cache local : {e}") from e
    return processor, model


def _appel_transformers(system: str, prompt: str, octets: bytes) -> str:
    from PIL import Image

    processor, model = _charger_transformers(modele())
    import torch

    messages = [{"role": "system", "content": system},
                {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    texte = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    entrees = processor(text=[texte], images=[Image.open(io.BytesIO(octets))], return_tensors="pt").to(model.device)
    with _verrou, torch.no_grad():
        sorties = model.generate(**entrees, max_new_tokens=MAX_TOKENS, do_sample=False)
    return processor.batch_decode(sorties[:, entrees["input_ids"].shape[1]:], skip_special_tokens=True)[0]


def analyser_image(chemin_image: Path, slide: Slide, langue: str) -> AnalyseVisuelle:
    """Appeler le VLM sur une image de slide (sans cache). Lève ``VLMIndisponible``."""
    system, prompt = _prompt(slide, langue)
    b = backend()
    if b not in ("fake", "llamacpp", "transformers"):
        raise VLMIndisponible(f"VLM_BACKEND inconnu ou désactivé : {b!r}")
    data_uri, octets = ("", b"") if b == "fake" else _image_data_uri(chemin_image)
    erreur: Exception | None = None
    # Deux tentatives : un petit modèle peut boucler et tronquer le JSON ; on relance plus « chaud ».
    for temperature in (0.1, 0.5):
        if b == "fake":
            brut = os.getenv("VLM_FAKE_REPONSE", "").strip() or json.dumps(
                {"figures": [f"[fake] figure de la slide {slide.numero}"], "formules": ["E = mc^2"]})
        elif b == "llamacpp":
            brut = _appel_llamacpp(system, prompt, data_uri, temperature)
        else:
            brut = _appel_transformers(system, prompt, octets)
        debut, fin = brut.find("{"), brut.rfind("}")
        try:
            return AnalyseVisuelle.model_validate_json(brut[debut:fin + 1] if 0 <= debut < fin else brut)
        except ValidationError as e:
            erreur = e
            log.info("sortie VLM invalide sur %s (T=%.1f), nouvelle tentative", slide.id, temperature)
            if b != "llamacpp":
                break
    raise VLMIndisponible(f"sortie VLM invalide : {erreur}") from erreur


# --------------------------------------------------------------------------- nettoyage


def nettoyer_latex(formule: str) -> str:
    """Retirer les délimiteurs ($, $$, \\( \\), \\[ \\], equation) et les espaces superflus."""
    f = formule.strip()
    f = re.sub(r"^\\begin\{(equation|align|displaymath)\*?\}(.*)\\end\{\1\*?\}$", r"\2", f, flags=re.S)
    for ouvrant, fermant in (("$$", "$$"), ("$", "$"), ("\\[", "\\]"), ("\\(", "\\)")):
        if f.startswith(ouvrant) and f.endswith(fermant) and len(f) > len(ouvrant) + len(fermant):
            f = f[len(ouvrant):-len(fermant)]
    return re.sub(r"\s+", " ", f.strip().strip("$")).strip()


_RIEN = re.compile(r"^(aucun|aucune|none|no|n/?a|pas de|there is no|il n'y a)\b", re.I)
# « A formula for … », « La formule … » : une formule décrite comme une figure.
_FORMULE_DECRITE = re.compile(
    r"^(an?|the|une?|la|le)\s+(mathematical\s+|mathématique\s+)?(formula|equation|formule|équation)\b", re.I)


def _est_de_la_prose(formule: str) -> bool:
    """Vrai si la « formule » contient plus de deux vrais mots (hors commandes LaTeX) : une phrase."""
    sans_commandes = re.sub(r"\\[a-zA-Z]+", " ", formule)
    return len(re.findall(r"[A-Za-zÀ-ÿ]{4,}", sans_commandes)) > 2


def _mots_cles(texte: str) -> set[str]:
    return set(re.findall(r"\w{3,}", texte.lower()))


def _quasi_doublon(texte: str, gardees: list[str]) -> bool:
    """Vrai si ``texte`` partage ≥ 60 % de ses mots avec une description déjà gardée."""
    mots = _mots_cles(texte)
    for autre in gardees:
        autres = _mots_cles(autre)
        if mots and autres and len(mots & autres) / min(len(mots), len(autres)) >= 0.6:
            return True
    return False


def _nettoyer(analyse: AnalyseVisuelle) -> tuple[list[str], list[str]]:
    figures: list[str] = []
    for f in analyse.figures:
        f = re.sub(r"\s+", " ", f).strip()
        if (len(f) >= 15 and not _RIEN.match(f) and not _FORMULE_DECRITE.match(f)
                and not _quasi_doublon(f, figures)):
            figures.append(f)
    formules: list[str] = []
    for f in analyse.formules:
        f = nettoyer_latex(f)
        if f and len(f) <= 200 and re.search(r"[=<>\\^_+\-*/≤≥∑∫]", f) and not _est_de_la_prose(f) \
                and f not in formules:
            formules.append(f)
    return figures, formules


# --------------------------------------------------------------------------- sélection des slides


def _dessins_source(course: Course) -> dict[int, int]:
    """Nombre d'éléments vectoriels (schémas) par slide, lu dans le fichier source."""
    source = Path(course.fichier_source)
    source = source if source.is_absolute() else RACINE / source
    if not source.is_file():
        return {}
    compte: dict[int, int] = {}
    try:
        if course.format == "pdf":
            import pymupdf

            with pymupdf.open(source) as doc:
                for i, page in enumerate(doc, start=1):
                    compte[i] = len(page.get_drawings())
        else:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            vectoriels = {MSO_SHAPE_TYPE.AUTO_SHAPE, MSO_SHAPE_TYPE.FREEFORM, MSO_SHAPE_TYPE.LINE,
                          MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.GROUP, MSO_SHAPE_TYPE.DIAGRAM}
            def _type(forme: Any) -> Any:
                try:
                    return forme.shape_type
                except (NotImplementedError, AttributeError):
                    return None

            # Une forme PPTX (flèche, bloc, graphique) pèse autant que ~5 tracés PDF.
            for i, s in enumerate(Presentation(str(source)).slides, start=1):
                compte[i] = 5 * sum(1 for f in s.shapes if _type(f) in vectoriels)
    except Exception as e:  # noqa: BLE001 - la sélection reste possible sans cette information
        log.debug("lecture des dessins de %s impossible : %s", source, e)
    return compte


def slide_visuelle(slide: Slide, nb_dessins: int = 0) -> bool:
    """Indiquer si la slide mérite un appel au VLM (figure, schéma, formule ou scan)."""
    return bool(
        slide.images
        or slide.ocr
        or nb_dessins >= 12
        or len(_INDICES_MATHS.findall(slide.texte)) >= 2
    )


# --------------------------------------------------------------------------- cache


def _cle_cache(octets_image: bytes, langue: str) -> str:
    h = hashlib.sha256(octets_image)
    h.update(f"|{modele()}|{VERSION_PROMPT}|{langue}".encode())
    return h.hexdigest()


def _lire_cache(cle: str, dossier: Path) -> AnalyseVisuelle | None:
    fichier = dossier / f"{cle[:2]}" / f"{cle}.json"
    if not fichier.is_file():
        return None
    try:
        return AnalyseVisuelle.model_validate_json(fichier.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return None


def _ecrire_cache(cle: str, analyse: AnalyseVisuelle, dossier: Path) -> None:
    fichier = dossier / f"{cle[:2]}" / f"{cle}.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(analyse.model_dump_json(indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- point d'entrée


def enrich_with_vlm(course: Course, *, dossier: Path | None = None, toutes: bool = False,
                    force: bool = False, cache: Path | None = None,
                    sauvegarder: bool = True) -> Course:
    """Renvoyer une copie du cours avec ``description_figures`` et ``formules_latex`` remplis.

    - ``dossier`` : dossier des rendus (défaut ``data/processed/<course_id>/``) ;
    - ``toutes`` : analyser toutes les slides, pas seulement les slides visuelles ;
    - ``force`` : ignorer le cache (le résultat est quand même réécrit dedans) ;
    - ``sauvegarder`` : réécrire ``course.json`` dans ``dossier``.

    Une slide en échec garde ses champs vides : l'ingestion n'est jamais bloquée par le VLM.
    """
    dossier = Path(dossier) if dossier else DOSSIER_PROCESSED / course.id
    cache = Path(cache) if cache else DOSSIER_CACHE
    langue = "en" if course.langue == "en" else "fr"
    utiliser_cache = backend() != "fake"
    if backend() == "aucun":
        log.warning("VLM_BACKEND=aucun : H2 ignoré pour %s", course.id)
        return course
    dessins = {} if toutes else _dessins_source(course)

    nouvelles: list[Slide] = []
    stats = {"analysees": 0, "cache": 0, "ignorees": 0, "echecs": 0}
    indisponible: str | None = None
    for slide in course.slides:
        chemin = dossier / slide.image_rendu if slide.image_rendu else None
        if chemin is None or not chemin.is_file() or not (toutes or slide_visuelle(slide, dessins.get(slide.numero, 0))):
            stats["ignorees"] += 1
            nouvelles.append(slide)
            continue
        cle = _cle_cache(chemin.read_bytes(), langue)
        analyse = None if (force or not utiliser_cache) else _lire_cache(cle, cache)
        if analyse is not None:
            stats["cache"] += 1
        elif indisponible is None:
            debut = time.perf_counter()
            try:
                analyse = analyser_image(chemin, slide, langue)
                stats["analysees"] += 1
                if utiliser_cache:
                    _ecrire_cache(cle, analyse, cache)
                log.info("%s : %.1fs", slide.id, time.perf_counter() - debut)
            except VLMIndisponible as e:
                stats["echecs"] += 1
                log.warning("VLM en échec sur %s : %s", slide.id, e)
                if "introuvable" in str(e) or "installé" in str(e) or "chargement" in str(e):
                    indisponible = str(e)  # inutile de réessayer sur les slides suivantes
        if analyse is None:
            nouvelles.append(slide)
            continue
        figures, formules = _nettoyer(analyse)
        nouvelles.append(slide.model_copy(update={"description_figures": figures, "formules_latex": formules}))

    if indisponible:
        log.warning("VLM indisponible (%s) : description_figures/formules_latex laissés vides", indisponible)
    log.info("H2 %s : %s", course.id, stats)
    resultat = Course.model_validate(course.model_copy(update={"slides": nouvelles}).model_dump())
    if sauvegarder:
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "course.json").write_text(resultat.model_dump_json(indent=2), encoding="utf-8")
    return resultat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H2 — VLM local : figures et formules")
    parser.add_argument("course_ids", nargs="+", help="cours déjà ingérés (data/processed/<id>/course.json)")
    parser.add_argument("--toutes", action="store_true", help="analyser toutes les slides")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not est_configure():
        print(f"VLM non configuré (backend {backend()!r}) : voir ingestion/README.md")
        return 1
    for cid in args.course_ids:
        chemin = DOSSIER_PROCESSED / cid / "course.json"
        course = Course.model_validate_json(chemin.read_text(encoding="utf-8"))
        debut = time.perf_counter()
        course = enrich_with_vlm(course, toutes=args.toutes, force=args.force)
        n_fig = sum(len(s.description_figures) for s in course.slides)
        n_form = sum(len(s.formules_latex) for s in course.slides)
        print(f"{cid}: {n_fig} figures, {n_form} formules, {time.perf_counter() - debut:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
