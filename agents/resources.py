"""A4 — Agent Resources : ressources externes pour la slide courante, sans aucun appel réseau.

1. Lit la slide courante (titre + concepts) dans ``data/processed/<course_id>/course.json`` ;
2. cherche dans le catalogue local ``data/ressources/catalogue.json`` les ressources dont les
   concepts recoupent ceux de la slide (mots-clés normalisés, sans accents) et en garde 3 à 5 ;
3. demande au LLM local (``agents/llm.py``) une justification courte pour chacune, en UN seul
   appel ; sans LLM, justification par modèle de phrase (« Couvre : … ») ;
4. si rien ne correspond, renvoie des liens de recherche Wikipédia / YouTube construits
   localement (l'étudiant clique, l'application n'appelle rien).

Branchement dans le graphe (O1) :

    from agents.graph import construire_graphe
    from agents.resources import resources_agent

    graphe = construire_graphe({"ressources": resources_agent})
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, ConfigDict, Field

from agents import llm
from api.models import Ressource
from schemas import Course, Message, Slide, Source, TutorState
from schemas.models import Langue

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PROCESSED = RACINE / "data" / "processed"
CATALOGUE = RACINE / "data" / "ressources" / "catalogue.json"

MIN_RESSOURCES = 3
MAX_RESSOURCES = 5
# Le LLM tourne sur CPU : réponse courte, budget serré.
MAX_TOKENS_PAR_RESSOURCE = 48
MAX_CARACTERES_JUSTIFICATION = 160

BONUS_PHRASE = 2.0  # un concept du catalogue retrouvé tel quel dans la slide
BONUS_COURS = 1.0  # ressource prévue pour ce cours
BONUS_LANGUE = 0.5  # ressource dans la langue de réponse

ChargerSlide = Callable[[str, int], Slide | None]

MOTS_VIDES = frozenset(
    """
    a au aux avec ce ces d dans de des du en et l la le les leur un une ou par pour sur se sa son
    qu que qui est sont plus moins entre sans
    an and are as at be but by for from how in is it of on or the to what with why
    """.split()
)


class EntreeCatalogue(BaseModel):
    """Une ligne de ``data/ressources/catalogue.json``."""

    model_config = ConfigDict(extra="forbid")

    titre: str
    url: str
    type: Literal["video", "article"]
    langue: Langue = "fr"
    concepts: list[str] = Field(default_factory=list)
    course_id: str = ""


# --------------------------------------------------------------------------- slide courante


def charger_slide(course_id: str, numero: int, dossier: Path = DOSSIER_PROCESSED) -> Slide | None:
    """Lire la slide ``numero`` du cours ingéré, ou ``None`` si le cours est absent."""
    chemin = dossier / course_id / "course.json"
    if not chemin.is_file():
        return None
    cours = Course.model_validate(json.loads(chemin.read_text(encoding="utf-8")))
    if not 1 <= numero <= cours.nombre_slides:
        return None
    return cours.slides[numero - 1]


def construire_requete(slide: Slide | None, question: str = "") -> str:
    """Texte de recherche : titre + 3 premiers concepts, sinon la question."""
    if slide is not None:
        morceaux: list[str] = []
        for m in [slide.titre, *slide.concepts[:3]]:  # sans doublon (titre = 1er concept…)
            if m.strip() and normaliser(m) not in {normaliser(x) for x in morceaux}:
                morceaux.append(m.strip())
        requete = " ".join(morceaux)
        if requete:
            return requete
    return question.strip()


# --------------------------------------------------------------------------- normalisation


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte.lower()) if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents).split())


def _racine(mot: str) -> str:
    """Raciniser grossièrement : pluriels FR/EN (réseaux → reseau, layers → layer)."""
    if len(mot) > 4 and mot[-1] in "sx":
        return mot[:-1]
    return mot


def mots_cles(texte: str) -> set[str]:
    return {_racine(m) for m in normaliser(texte).split() if m not in MOTS_VIDES and len(m) > 1}


def _contient(texte_norm: str, phrase_norm: str) -> bool:
    return bool(phrase_norm) and f" {phrase_norm} " in f" {texte_norm} "


# --------------------------------------------------------------------------- catalogue


@lru_cache(maxsize=4)
def _lire_catalogue(chemin: str, _mtime: float) -> tuple[EntreeCatalogue, ...]:
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return tuple(EntreeCatalogue.model_validate(e) for e in donnees)


def charger_catalogue(chemin: Path = CATALOGUE) -> list[EntreeCatalogue]:
    """Lire le catalogue local (relu automatiquement s'il est modifié) ; absent → liste vide."""
    if not chemin.is_file():
        log.warning("catalogue de ressources introuvable : %s", chemin)
        return []
    return list(_lire_catalogue(str(chemin), chemin.stat().st_mtime))


def _sujet(slide: Slide | None, question: str) -> tuple[str, set[str]]:
    """Texte normalisé et mots-clés de la slide (titre + concepts), sinon de la question."""
    morceaux = [slide.titre, *slide.concepts] if slide is not None else []
    if not any(morceaux):
        morceaux = [question]
    texte = " ".join(m for m in morceaux if m)
    return normaliser(texte), mots_cles(texte)


def concepts_communs(entree: EntreeCatalogue, texte_norm: str, cles: set[str]) -> list[str]:
    """Concepts de l'entrée retrouvés dans la slide (en entier ou par un mot-clé)."""
    return [
        c for c in entree.concepts
        if _contient(texte_norm, normaliser(c)) or mots_cles(c) & cles
    ]


def score(entree: EntreeCatalogue, texte_norm: str, cles: set[str], course_id: str = "",
          langue: Langue = "fr") -> float:
    """Score de correspondance ; 0 si aucun mot-clé de la slide n'apparaît dans l'entrée."""
    cles_entree = mots_cles(" ".join([entree.titre, *entree.concepts]))
    base = len(cles & cles_entree)
    base += BONUS_PHRASE * sum(_contient(texte_norm, normaliser(c)) for c in entree.concepts)
    if base == 0:
        return 0.0
    if course_id and entree.course_id == course_id:
        base += BONUS_COURS
    if entree.langue == langue:
        base += BONUS_LANGUE
    return float(base)


def selectionner(
    slide: Slide | None,
    question: str = "",
    course_id: str = "",
    langue: Langue = "fr",
    catalogue: Iterable[EntreeCatalogue] | None = None,
) -> list[tuple[EntreeCatalogue, list[str]]]:
    """Les ``MAX_RESSOURCES`` meilleures entrées, avec leurs concepts communs."""
    texte_norm, cles = _sujet(slide, question)
    if not cles:
        return []
    entrees = charger_catalogue() if catalogue is None else list(catalogue)
    notees = [(score(e, texte_norm, cles, course_id, langue), i, e) for i, e in enumerate(entrees)]
    notees = [n for n in notees if n[0] > 0]
    notees.sort(key=lambda n: (-n[0], n[1]))  # stable : ordre du catalogue à score égal
    return [(e, concepts_communs(e, texte_norm, cles)) for _, _, e in notees[:MAX_RESSOURCES]]


# --------------------------------------------------------------------------- liens de recherche


JUSTIFICATION_RECHERCHE = "Lien de recherche à ouvrir pour trouver d'autres ressources sur ce sujet."


def liens_recherche(requete: str, langue: Langue = "fr") -> list[Ressource]:
    """Liens de recherche Wikipédia et YouTube, construits sans appel réseau."""
    code = "fr" if langue == "mixte" else langue
    q = quote_plus(requete)
    return [
        Ressource(
            titre=f"Rechercher « {requete} » sur Wikipédia",
            url=f"https://{code}.wikipedia.org/w/index.php?search={q}",
            type="recherche",
            langue=langue,
            justification=JUSTIFICATION_RECHERCHE,
        ),
        Ressource(
            titre=f"Rechercher « {requete} » sur YouTube",
            url=f"https://www.youtube.com/results?search_query={q}",
            type="recherche",
            langue=langue,
            justification=JUSTIFICATION_RECHERCHE,
        ),
    ]


# --------------------------------------------------------------------------- justifications


class _Justifications(BaseModel):
    justifications: list[str] = Field(description="Une phrase par ressource, dans l'ordre donné")


SYSTEME_JUSTIFICATION = (
    "Tu aides un étudiant qui révise une slide de cours. Pour chaque ressource numérotée, "
    "écris UNE phrase courte (moins de 25 mots) expliquant pourquoi elle aide à comprendre "
    "cette slide. Garde l'ordre des ressources."
)


def justification_modele(communs: list[str]) -> str:
    return f"Couvre : {', '.join(communs)}." if communs else "Ressource liée au sujet de la slide."


def _prompt_justification(slide: Slide | None, requete: str, niveau: str, langue: str,
                          choix: list[tuple[EntreeCatalogue, list[str]]]) -> str:
    lignes = [
        f"Slide : {slide.titre if slide else requete}",
        f"Concepts : {', '.join(slide.concepts) if slide and slide.concepts else requete}",
        f"Niveau : {niveau}. Langue des phrases : {langue}.",
        "Ressources :",
    ]
    for i, (e, communs) in enumerate(choix, 1):
        lignes.append(f"{i}. [{e.type}] {e.titre} — concepts : {', '.join(communs or e.concepts[:3])}")
    return "\n".join(lignes)


def justifier(choix: list[tuple[EntreeCatalogue, list[str]]], slide: Slide | None, requete: str,
              niveau: str = "intermediaire", langue: Langue = "fr") -> list[str]:
    """Une justification par ressource : un seul appel LLM, repli par modèle de phrase."""
    modeles = [justification_modele(communs) for _, communs in choix]
    if not choix:
        return []
    try:
        reponse = llm.generer_structure(
            SYSTEME_JUSTIFICATION,
            _prompt_justification(slide, requete, niveau, langue, choix),
            _Justifications,
            max_tokens=32 + MAX_TOKENS_PAR_RESSOURCE * len(choix),
        )
    except llm.LLMIndisponible as e:
        log.info("justifications LLM indisponibles, repli par modèle : %s", e)
        return modeles
    proposees = [j.strip()[:MAX_CARACTERES_JUSTIFICATION] for j in reponse.justifications]
    return [
        proposees[i] if i < len(proposees) and proposees[i] else modeles[i]
        for i in range(len(choix))
    ]


# --------------------------------------------------------------------------- agent


def chercher_ressources(
    state: TutorState,
    *,
    charger: ChargerSlide | None = None,
    catalogue: Iterable[EntreeCatalogue] | None = None,
) -> list[Ressource]:
    """Pipeline complet, réutilisable par l'API (``GET /resources``)."""
    slide = (charger or charger_slide)(state.course_id, state.slide_courante)
    requete = construire_requete(slide, state.question)
    if not requete:
        return []
    choix = selectionner(slide, state.question, state.course_id, state.langue_reponse, catalogue)
    if not choix:
        return liens_recherche(requete, state.langue_reponse)
    justifications = justifier(choix, slide, requete, state.niveau, state.langue_reponse)
    ressources = [
        Ressource(
            titre=e.titre,
            url=e.url,
            type=e.type,
            langue=e.langue,
            description=", ".join(e.concepts),
            justification=j,
        )
        for (e, _), j in zip(choix, justifications, strict=True)
    ]
    if len(ressources) < MIN_RESSOURCES:  # compléter avec des liens de recherche
        ressources += liens_recherche(requete, state.langue_reponse)[: MIN_RESSOURCES - len(ressources)]
    return ressources


ETIQUETTES = {"video": "Vidéo", "recherche": "Recherche"}


def formater(ressources: list[Ressource], numero: int) -> str:
    """Réponse texte affichée par le tuteur, citant la slide."""
    if not ressources:
        return f"Je n'ai pas trouvé de ressource externe pour la slide {numero} [Slide {numero}]."
    lignes = [f"Pour aller plus loin sur la slide {numero} [Slide {numero}] :"]
    for r in ressources:
        etiquette = ETIQUETTES.get(r.type, "Article")
        lignes.append(f"- {etiquette} — [{r.titre}]({r.url}) : {r.justification}")
    return "\n".join(lignes)


def resources_agent(state: TutorState) -> dict[str, Any]:
    """Nœud LangGraph ``resources`` : même signature et mêmes champs que les bouchons d'O1."""
    ressources = chercher_ressources(state)
    reponse = formater(ressources, state.slide_courante)
    historique = list(state.historique)
    if state.question:
        historique.append(Message(role="utilisateur", contenu=state.question))
    historique.append(Message(role="tuteur", contenu=reponse))
    return {
        "reponse": reponse,
        "sources": [Source(course_id=state.course_id, numero=state.slide_courante)],
        "historique": historique,
    }


__all__ = [
    "EntreeCatalogue",
    "charger_catalogue",
    "chercher_ressources",
    "formater",
    "justifier",
    "liens_recherche",
    "normaliser",
    "resources_agent",
    "selectionner",
]
