"""Modèles propres à l'API, absents de ``schemas/models.py``.

Les modèles partagés (Course, AgentResponse, Source…) restent dans ``schemas/`` ;
ce module ne définit que ce qui manque au contrat commun.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.models import COURSE_ID_PATTERN, Langue, Message, Niveau, Source


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


MAX_HISTORIQUE = 40


class AskRequest(_Base):
    """Corps de ``POST /ask``."""

    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    slide_courante: int = Field(ge=1)
    question: str = Field(min_length=1)
    niveau: Niveau = "intermediaire"
    langue: Langue = "fr"
    historique: list[Message] = Field(
        default_factory=list, max_length=MAX_HISTORIQUE,
        description="Tours précédents de la conversation (A3), du plus ancien au plus récent",
    )


NiveauBloom = Literal["memoriser", "comprendre", "appliquer", "analyser"]


class QCM(_Base):
    """Question à choix multiples renvoyée par ``GET /quiz`` (A2).

    Exactement 4 choix distincts, une seule bonne réponse (``bonne_reponse`` : index 0..3).
    """

    question: str = Field(min_length=1)
    choix: list[str] = Field(min_length=4, max_length=4)
    bonne_reponse: int = Field(ge=0, le=3, description="Index de la bonne réponse dans ``choix``")
    explication: str = ""
    niveau_bloom: NiveauBloom = "comprendre"
    source: Source


class Flashcard(_Base):
    """Carte de révision renvoyée par ``GET /flashcards`` (A2)."""

    recto: str = Field(min_length=1, description="Question ou notion")
    verso: str = Field(min_length=1, description="Réponse ou définition")
    source: Source


class Ressource(_Base):
    """Ressource externe renvoyée par ``GET /resources``."""

    titre: str
    url: str
    type: Literal["video", "article", "cours", "exercice", "documentation", "recherche"] = Field(
        description="``recherche`` : lien de recherche Wikipédia/YouTube construit localement (A4)"
    )
    langue: Langue = "fr"
    description: str = ""
    justification: str = Field(default="", description="Pourquoi la ressource est pertinente (A4)")


Utilisateur = Annotated[
    str, Field(min_length=1, max_length=100, pattern=r"^\S(?:.*\S)?$", description="Identifiant de l'utilisateur")
]


class EtatSM2(_Base):
    """État de révision espacée (SM-2) d'une carte (A6)."""

    repetitions: int = Field(ge=0, description="Révisions réussies consécutives")
    intervalle: int = Field(ge=0, description="Jours jusqu'à la prochaine révision")
    facilite: float = Field(ge=1.3, description="Facteur de facilité SM-2 (départ 2.5)")
    prochaine_revision: date


class CarteSRS(_Base):
    """Flashcard enregistrée pour un utilisateur, avec son état SM-2 (A6)."""

    id: int
    user: str
    course_id: str
    recto: str
    verso: str
    source: Source
    etat: EtatSM2


class SaveFlashcardsRequest(_Base):
    """Corps de ``POST /flashcards/save`` : flashcards de l'agent Quiz (A2) à mémoriser."""

    user: Utilisateur
    flashcards: list[Flashcard] = Field(min_length=1)


class ReviewRequest(_Base):
    """Corps de ``POST /flashcards/{id}/review`` : note SM-2 de 0 (oubli total) à 5 (parfait)."""

    user: Utilisateur
    qualite: int = Field(ge=0, le=5)


__all__ = [
    "QCM",
    "AskRequest",
    "CarteSRS",
    "EtatSM2",
    "Flashcard",
    "NiveauBloom",
    "Ressource",
    "ReviewRequest",
    "SaveFlashcardsRequest",
]
