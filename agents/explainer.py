"""O2 — Agent Explainer : explique une slide au niveau de l'étudiant, avec le LLM local (A0).

1. Charge la slide demandée (``slide_courante``, ou « slide 5 » dans la question) et ses
   voisines N-1 / N+1, via ``agents.quiz.charger_cours`` (cours de l'API, ``data/processed``
   ou cours d'exemple) ;
2. ajoute les prérequis de la slide : ``get_prerequisites(slide_id)`` de H3
   (``ingestion.course_map``, Ghayth), dont les ids de slides deviennent « Slide N : titre » ;
   sans carte du cours, repli sur les concepts des deux slides précédentes ;
3. un SEUL appel ``agents.llm.generer_structure`` avec le prompt du niveau
   (``prompts/explainer.md``) et le modèle de sortie ``Explication`` :
   idée clé → explication → exemple → lien avec la slide précédente → à retenir ;
4. sans LLM (``LLMIndisponible``) : repli extractif tiré de la slide elle-même.

La réponse cite [Slide N] (et [Slide N-1] pour le lien) : le Critic (O3) s'appuie sur ces
citations et sur ``sources`` ; quand il renvoie des ``corrections``, elles sont ajoutées au
prompt pour la nouvelle version.

Branchement dans le graphe (O1) :

    from agents.graph import construire_graphe
    from agents.explainer import explainer_agent

    graphe = construire_graphe({"expliquer": explainer_agent})
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agents import llm
from agents.quiz import LANGUES_LISIBLES, charger_cours, nettoyer
from agents.resources import normaliser
from schemas import Course, Message, Slide, Source, TutorState
from schemas.models import Langue, Niveau

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
PROMPTS = RACINE / "prompts" / "explainer.md"

# Budget CPU : contexte et sortie courts.
MAX_CARACTERES_SLIDE = 1800
MAX_CARACTERES_VOISINE = 300
MAX_CARACTERES_EXTRAIT = 300
MAX_PREREQUIS = 6
TOKENS_PAR_NIVEAU: dict[Niveau, int] = {"debutant": 560, "intermediaire": 520, "avance": 520}

SECTIONS_NIVEAU: dict[Niveau, str] = {
    "debutant": "Débutant",
    "intermediaire": "Intermédiaire",
    "avance": "Avancé",
}

ChargerCours = Callable[[str], Course | None]
Prerequis = Callable[[str], list[str]]


# --------------------------------------------------------------------------- format de sortie

# Bornes de longueur : imposées par la grammaire llama.cpp (schéma JSON seulement), elles
# évitent qu'une réponse trop bavarde dépasse ``max_tokens`` et soit tronquée.
MAX_IDEE, MAX_EXPLICATION, MAX_EXEMPLE, MAX_LIEN, MAX_POINT = 220, 1100, 500, 300, 180


def _texte(max_len: int, description: str) -> Any:
    return Field(description=description, json_schema_extra={"maxLength": max_len})


class Explication(BaseModel):
    """Explication structurée d'une slide, dans l'ordre où l'étudiant la lit."""

    idee_cle: str = _texte(MAX_IDEE, "L'idée principale de la slide en une phrase")
    explication: str = _texte(MAX_EXPLICATION, "Explication adaptée au niveau de l'étudiant")
    exemple: str = _texte(MAX_EXEMPLE, "Exemple concret ou application")
    lien_precedente: str = _texte(MAX_LIEN, "Lien avec la slide précédente, vide s'il n'y en a pas")
    a_retenir: list[str] = Field(
        min_length=1,
        description="1 à 3 points à retenir",
        json_schema_extra={"maxItems": 3, "items": {"type": "string", "maxLength": MAX_POINT}},
    )


@dataclass
class ResultatExplication:
    """Explication d'une slide, ses sources et l'origine du texte (LLM ou repli)."""

    explication: Explication
    sources: list[Source]
    numero: int
    precedente: int | None = None
    via_llm: bool = True
    prerequis: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- prompts


@lru_cache(maxsize=2)
def _lire_prompts(chemin: str, _mtime: float) -> dict[str, str]:
    sections: dict[str, str] = {}
    for bloc in re.split(r"^## ", Path(chemin).read_text(encoding="utf-8"), flags=re.M)[1:]:
        titre, _, corps = bloc.partition("\n")
        sections[normaliser(titre)] = corps.strip()
    return sections


PROMPT_SECOURS = (
    "Tu es un tuteur qui explique une slide de cours. Appuie-toi uniquement sur la slide "
    "fournie, n'invente rien, adapte-toi au niveau de l'étudiant et rédige dans la langue demandée."
)


def prompt_systeme(niveau: Niveau) -> str:
    """Section ``Commun`` + section du niveau de ``prompts/explainer.md`` (secours si absentes)."""
    sections = _lire_prompts(str(PROMPTS), PROMPTS.stat().st_mtime) if PROMPTS.is_file() else {}
    commun = sections.get("commun")
    propre = sections.get(normaliser(SECTIONS_NIVEAU[niveau]))
    if not commun or not propre:
        log.warning("prompts/explainer.md incomplet pour le niveau %r, prompt de secours", niveau)
        return f"{PROMPT_SECOURS}\nNiveau de l'étudiant : {SECTIONS_NIVEAU[niveau].lower()}."
    return f"{commun}\n\n{propre}"


# --------------------------------------------------------------------------- prérequis (H3)


def prerequis_bouchon(cours: Course, numero: int) -> list[str]:
    """Repli quand la carte du cours (H3) n'existe pas : concepts des deux slides précédentes, sans doublon."""
    vus: dict[str, str] = {}
    for s in cours.slides[max(0, numero - 3): numero - 1]:
        for concept in s.concepts:
            vus.setdefault(normaliser(concept), concept.strip())
    return [c for c in vus.values() if c][:MAX_PREREQUIS]


def _prerequis_h3() -> Prerequis | None:
    """``get_prerequisites`` de H3 (``ingestion.course_map``, Ghayth) s'il est installé."""
    nom = "ingestion.course_map"
    try:
        if importlib.util.find_spec("ingestion") is None or importlib.util.find_spec(nom) is None:
            return None
        fonction = getattr(importlib.import_module(nom), "get_prerequisites", None)
    except ImportError as e:
        log.warning("module %s inutilisable : %s", nom, e)
        return None
    return fonction if callable(fonction) else None


def libelle_prerequis(cours: Course, valeur: str) -> str:
    """H3 renvoie des ids de slides (``<course_id>__s003``) : les rendre lisibles pour le LLM.

    ``<course_id>__s003`` du même cours → « Slide 3 : <titre> » ; toute autre valeur (un nom de
    notion) est gardée telle quelle.
    """
    m = re.fullmatch(rf"{re.escape(cours.id)}__s(\d+)", valeur)
    if not m:
        return valeur
    n = int(m.group(1))
    if not 1 <= n <= cours.nombre_slides:
        return ""
    titre = cours.slides[n - 1].titre.strip()
    return f"Slide {n} : {titre}" if titre else f"Slide {n}"


def prerequis(cours: Course, numero: int, source: Prerequis | None = None) -> list[str]:
    """Prérequis de la slide : ``source`` ou H3 (carte du cours), sinon le repli sur les concepts voisins.

    H3 renvoie ``[]`` quand la carte du cours n'a pas encore été calculée : on passe alors au repli.
    """
    fonction = source or _prerequis_h3()
    if fonction is not None:
        try:
            brut = [str(p).strip() for p in fonction(cours.slides[numero - 1].id) if str(p).strip()]
            libelles = [lib for lib in (libelle_prerequis(cours, p) for p in brut) if lib]
            if libelles:
                return list(dict.fromkeys(libelles))[:MAX_PREREQUIS]
        except Exception as e:  # noqa: BLE001 - un prérequis manquant ne doit pas bloquer l'explication
            log.warning("get_prerequisites a échoué, repli sur les concepts voisins : %s", e)
    return prerequis_bouchon(cours, numero)


# --------------------------------------------------------------------------- contexte de la slide


def _corps(slide: Slide, limite: int) -> str:
    morceaux = [slide.texte, slide.notes]
    morceaux += [f"Figure : {d}" for d in slide.description_figures]
    morceaux += [f"Formule : {f}" for f in slide.formules_latex]
    corps = "\n".join(m.strip() for m in morceaux if m and m.strip())
    return corps[:limite]


def _bloc_slide(etiquette: str, slide: Slide, limite: int) -> str:
    titre = slide.titre.strip() or "(sans titre)"
    corps = _corps(slide, limite) or "(slide sans texte)"
    return f"{etiquette} — [Slide {slide.numero}] {titre}\n{corps}"


def construire_prompt(cours: Course, numero: int, langue: Langue, prerequis_slide: list[str],
                      corrections: list[str] | None = None) -> str:
    """Message utilisateur : langue, slide à expliquer, voisines, prérequis et corrections du Critic."""
    slide = cours.slides[numero - 1]
    lignes = [f"Langue de la réponse : {LANGUES_LISIBLES.get(langue, langue)}.", ""]
    lignes.append(_bloc_slide("Slide à expliquer", slide, MAX_CARACTERES_SLIDE))
    if numero > 1:
        lignes += ["", _bloc_slide("Slide précédente", cours.slides[numero - 2], MAX_CARACTERES_VOISINE)]
    else:
        lignes += ["", "Slide précédente : aucune (première slide), laisse `lien_precedente` vide."]
    if numero < cours.nombre_slides:
        lignes += ["", _bloc_slide("Slide suivante", cours.slides[numero], MAX_CARACTERES_VOISINE)]
    if prerequis_slide:
        lignes += ["", "Prérequis déjà vus : " + ", ".join(prerequis_slide) + "."]
    if corrections:
        lignes += ["", "Corrections du relecteur : ta version précédente contenait ces affirmations, "
                   "que la slide n'appuie pas. Retire-les ou reformule-les d'après la slide :"]
        lignes += [f"- {c}" for c in corrections]
    return "\n".join(lignes)


_SLIDE_DEMANDEE = re.compile(r"\b(?:slide|diapo(?:sitive)?|page)\s*(?:n[°o]\s*)?(\d{1,3})\b", re.I)


def slide_demandee(question: str, defaut: int) -> int:
    """Numéro de slide cité dans la question (« explique la slide 5 »), sinon ``defaut``."""
    m = _SLIDE_DEMANDEE.search(question or "")
    return int(m.group(1)) if m else defaut


# --------------------------------------------------------------------------- génération


def explication_sans_llm(cours: Course, numero: int) -> Explication:
    """Repli extractif : la slide reformatée dans les mêmes rubriques, sans rien inventer."""
    slide = cours.slides[numero - 1]
    titre = slide.titre.strip() or f"Slide {numero}"
    corps = _corps(slide, MAX_EXPLICATION).strip()
    precedente = cours.slides[numero - 2] if numero > 1 else None
    lien = ""
    if precedente is not None and precedente.titre.strip():
        lien = f"Fait suite à « {precedente.titre.strip()} »."
    points = [c.strip() for c in slide.concepts if c.strip()][:3] or [titre]
    return Explication(
        idee_cle=titre,
        explication=corps or "Cette slide ne contient pas de texte exploitable.",
        exemple="",
        lien_precedente=lien,
        a_retenir=points,
    )


def _nettoyer_explication(brute: Explication, numero: int) -> Explication:
    points = [nettoyer(p) for p in brute.a_retenir if p and p.strip()][:3]
    return Explication(
        idee_cle=nettoyer(brute.idee_cle),
        explication=nettoyer(brute.explication),
        exemple=nettoyer(brute.exemple),
        # Pas de slide précédente : un lien serait forcément inventé.
        lien_precedente=nettoyer(brute.lien_precedente) if numero > 1 else "",
        a_retenir=points or [nettoyer(brute.idee_cle)],
    )


def _source(slide: Slide) -> Source:
    extrait = (slide.texte or slide.titre).strip()[:MAX_CARACTERES_EXTRAIT]
    return Source(course_id=slide.course_id, numero=slide.numero, extrait=extrait)


def expliquer_slide(
    course_id: str,
    numero: int,
    niveau: Niveau = "intermediaire",
    langue: Langue | None = None,
    *,
    charger: ChargerCours = charger_cours,
    source_prerequis: Prerequis | None = None,
    corrections: list[str] | None = None,
) -> ResultatExplication | None:
    """Explication de la slide ``numero`` du cours, ou ``None`` si la slide n'existe pas."""
    cours = charger(course_id)
    if cours is None or not 1 <= numero <= cours.nombre_slides:
        return None
    if langue is None or langue == "mixte":
        langue = cours.langue if cours.langue != "mixte" else "fr"
    prerequis_slide = prerequis(cours, numero, source_prerequis)
    slide = cours.slides[numero - 1]
    try:
        brute = llm.generer_structure(
            prompt_systeme(niveau),
            construire_prompt(cours, numero, langue, prerequis_slide, corrections),
            Explication,
            max_tokens=TOKENS_PAR_NIVEAU[niveau],
        )
        explication, via_llm = _nettoyer_explication(brute, numero), True
        if not explication.idee_cle or not explication.explication:
            raise llm.LLMIndisponible("explication vide")
    except llm.LLMIndisponible as e:
        log.warning("explainer : LLM local indisponible, repli extractif : %s", e)
        explication, via_llm = explication_sans_llm(cours, numero), False

    sources = [_source(slide)]
    precedente = numero - 1 if numero > 1 and explication.lien_precedente else None
    if precedente is not None:
        sources.append(_source(cours.slides[precedente - 1]))
    return ResultatExplication(explication, sources, numero, precedente, via_llm, prerequis_slide)


# --------------------------------------------------------------------------- mise en forme


RUBRIQUES: dict[str, dict[str, str]] = {
    "fr": {"idee": "Idée clé", "exemple": "Exemple", "lien": "Lien avec la slide {n}",
           "retenir": "À retenir", "repli": "(Explication tirée directement de la slide : "
           "le modèle local n'a pas pu répondre.)", "absente": "La slide {n} n'existe pas dans ce cours."},
    "en": {"idee": "Key idea", "exemple": "Example", "lien": "Link with slide {n}",
           "retenir": "Remember", "repli": "(Explanation taken directly from the slide: "
           "the local model could not answer.)", "absente": "Slide {n} does not exist in this course."},
    "ar": {"idee": "الفكرة الأساسية", "exemple": "مثال", "lien": "الصلة بالشريحة {n}",
           "retenir": "للتذكر", "repli": "(شرح مأخوذ مباشرة من الشريحة: لم يتمكن النموذج المحلي من الإجابة.)",
           "absente": "الشريحة {n} غير موجودة في هذا الدرس."},
}


def formater(resultat: ResultatExplication, langue: Langue = "fr") -> str:
    """Texte affiché dans le chat, avec les citations [Slide N] attendues par le Critic (O3)."""
    r = RUBRIQUES.get(langue, RUBRIQUES["fr"])
    e, n = resultat.explication, resultat.numero
    lignes = [f"**{r['idee']}** : {e.idee_cle} [Slide {n}]", "", f"{e.explication} [Slide {n}]"]
    if e.exemple:
        lignes += ["", f"**{r['exemple']}** : {e.exemple}"]
    if resultat.precedente is not None:
        p = resultat.precedente
        lignes += ["", f"**{r['lien'].format(n=p)}** : {e.lien_precedente} [Slide {p}]"]
    lignes += ["", f"**{r['retenir']}**"]
    lignes += [f"- {point} [Slide {n}]" for point in e.a_retenir]
    if not resultat.via_llm:
        lignes += ["", r["repli"]]
    return "\n".join(lignes)


# --------------------------------------------------------------------------- agent


def explainer_agent(state: TutorState) -> dict[str, Any]:
    """Nœud LangGraph ``explainer`` : même signature et mêmes champs que les bouchons d'O1."""
    numero = slide_demandee(state.question, state.slide_courante)
    langue: Langue = state.langue_reponse
    resultat = expliquer_slide(state.course_id, numero, state.niveau, langue,
                               corrections=state.corrections)
    if resultat is None:
        reponse = RUBRIQUES.get(langue, RUBRIQUES["fr"])["absente"].format(n=numero)
        sources = [Source(course_id=state.course_id, numero=state.slide_courante)]
    else:
        reponse = formater(resultat, langue)
        sources = resultat.sources
    historique = list(state.historique)
    if state.question:
        historique.append(Message(role="utilisateur", contenu=state.question))
    historique.append(Message(role="tuteur", contenu=reponse))
    return {"reponse": reponse, "sources": sources, "historique": historique}


__all__ = [
    "Explication",
    "ResultatExplication",
    "construire_prompt",
    "explainer_agent",
    "explication_sans_llm",
    "expliquer_slide",
    "formater",
    "prerequis",
    "prerequis_bouchon",
    "prompt_systeme",
    "slide_demandee",
]
