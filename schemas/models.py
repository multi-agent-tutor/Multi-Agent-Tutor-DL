"""T0 — Modèles Pydantic partagés par tous les modules.

Ces modèles forment le contrat entre l'ingestion (Ghayth), le RAG (Both),
les agents (Ons, Both, Ali) et l'API (Ali). Toute modification passe par Ons
et doit être reportée dans ``docs/schema.md`` puis dans les JSON Schema
(``python -m schemas.export``).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"

# Identifiant de cours : minuscules ASCII, chiffres et « _ » (nom du fichier sans extension).
COURSE_ID_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
# Identifiant de slide : « <course_id>__s<numéro sur 3 chiffres> ».
SLIDE_ID_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*__s\d{3,}$"

Langue = Literal["fr", "en", "ar", "mixte"]
FormatSource = Literal["pdf", "pptx"]
Niveau = Literal["debutant", "intermediaire", "avance"]
Intention = Literal["expliquer", "question", "quiz", "ressources"]


def slide_id(course_id: str, numero: int) -> str:
    """Construire l'identifiant d'une slide à partir du cours et du numéro."""
    return f"{course_id}__s{numero:03d}"


def est_course_id_valide(valeur: str) -> bool:
    """Indiquer si une chaîne est un identifiant de cours valide (utile pour C1)."""
    return re.fullmatch(COURSE_ID_PATTERN, valeur) is not None


class _Base(BaseModel):
    """Base commune : champs inconnus refusés pour détecter les écarts au schéma."""

    model_config = ConfigDict(extra="forbid")


class Slide(_Base):
    """Une slide (ou une page PDF) après ingestion.

    H1 remplit le texte, les notes et les images ; H2 ajoute
    ``description_figures`` et ``formules_latex`` ; H3 ajoute ``concepts``.
    """

    id: str = Field(pattern=SLIDE_ID_PATTERN, description="<course_id>__s<NNN>")
    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    numero: int = Field(ge=1, description="Numéro de la slide, à partir de 1")
    titre: str = Field(default="", description="Titre de la slide, vide si absent")
    texte: str = Field(default="", description="Texte visible (ou texte OCR)")
    notes: str = Field(default="", description="Notes du présentateur (PPTX)")
    image_rendu: str | None = Field(
        default=None,
        description="Rendu PNG 150 dpi de la slide, chemin relatif à data/processed/<course_id>/",
    )
    images: list[str] = Field(
        default_factory=list,
        description="Images extraites de la slide, chemins relatifs à data/processed/<course_id>/",
    )
    description_figures: list[str] = Field(
        default_factory=list, description="Descriptions des figures produites par le VLM (H2)"
    )
    formules_latex: list[str] = Field(
        default_factory=list, description="Formules retranscrites en LaTeX, sans délimiteurs $ (H2)"
    )
    concepts: list[str] = Field(
        default_factory=list, description="Concepts clés de la slide (H3)"
    )
    ocr: bool = Field(default=False, description="Vrai si le texte vient de l'OCR")

    @model_validator(mode="after")
    def _verifier_id(self) -> Slide:
        """Vérifier que l'identifiant correspond au cours et au numéro."""
        attendu = slide_id(self.course_id, self.numero)
        if self.id != attendu:
            raise ValueError(f"id de slide incohérent : {self.id!r}, attendu {attendu!r}")
        return self


class Course(_Base):
    """Un cours complet, tel que produit par l'ingestion (``course.json``)."""

    schema_version: str = SCHEMA_VERSION
    id: str = Field(pattern=COURSE_ID_PATTERN, description="Nom du fichier source sans extension")
    titre: str
    fichier_source: str = Field(description="Chemin relatif à la racine du dépôt")
    format: FormatSource
    langue: Langue
    source_url: str | None = None
    nombre_slides: int = Field(ge=1)
    resume: str = Field(default="", description="Résumé global du cours (H3)")
    slides: list[Slide]

    @model_validator(mode="after")
    def _verifier_slides(self) -> Course:
        """Vérifier que les slides appartiennent au cours et sont numérotées 1..n."""
        if len(self.slides) != self.nombre_slides:
            raise ValueError(
                f"nombre_slides={self.nombre_slides} mais {len(self.slides)} slides présentes"
            )
        for attendu, slide in enumerate(self.slides, start=1):
            if slide.course_id != self.id:
                raise ValueError(f"slide {slide.id} n'appartient pas au cours {self.id}")
            if slide.numero != attendu:
                raise ValueError(f"numérotation discontinue : {slide.numero} au lieu de {attendu}")
        return self


class Chunk(_Base):
    """Unité indexée par le RAG (B2) : une slide = un chunk."""

    id: str = Field(pattern=SLIDE_ID_PATTERN, description="Égal à l'id de la slide")
    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    numero: int = Field(ge=1)
    titre: str = ""
    contenu: str = Field(description="texte + notes + description_figures, concaténés")
    contexte_precedent: str = Field(default="", description="Titre/résumé de la slide N-1")
    contexte_suivant: str = Field(default="", description="Titre/résumé de la slide N+1")
    langue: Langue


class SearchHit(_Base):
    """Résultat d'une recherche RAG (B1/B2)."""

    chunk: Chunk
    score: float = Field(description="Score après fusion (RRF) ou reranking")


class Source(_Base):
    """Source citée dans une réponse, affichée sous la forme [Slide N]."""

    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    numero: int = Field(ge=1)
    extrait: str = Field(default="", description="Passage qui appuie la réponse")


class Message(_Base):
    """Un tour de conversation dans l'historique."""

    role: Literal["utilisateur", "tuteur"]
    contenu: str


class TutorState(_Base):
    """État partagé du graphe LangGraph (O1)."""

    course_id: str = Field(pattern=COURSE_ID_PATTERN)
    slide_courante: int = Field(ge=1)
    niveau: Niveau = "intermediaire"
    langue_reponse: Langue = "fr"
    historique: list[Message] = Field(default_factory=list)
    question: str = ""
    intention: Intention | None = None
    reponse: str = ""
    sources: list[Source] = Field(default_factory=list)
    iterations_critic: int = Field(default=0, ge=0, le=2)
    score_fidelite: float | None = Field(
        default=None, ge=0, le=1, description="Part des affirmations appuyées par le cours (Critic, O3)"
    )
    corrections: list[str] = Field(
        default_factory=list,
        description="Affirmations non appuyées renvoyées à l'agent par le Critic (O3) ; vide = réponse acceptée",
    )


class AgentResponse(_Base):
    """Sortie commune des agents texte (Explainer, Q&A), renvoyée par l'API."""

    agent: Literal["explainer", "qa", "quiz", "resources", "critic"]
    reponse: str
    sources: list[Source] = Field(default_factory=list)
    score_fidelite: float | None = Field(default=None, ge=0, le=1, description="Rempli par le Critic (O3)")


__all__ = [
    "COURSE_ID_PATTERN",
    "SCHEMA_VERSION",
    "SLIDE_ID_PATTERN",
    "AgentResponse",
    "Chunk",
    "Course",
    "FormatSource",
    "Intention",
    "Langue",
    "Message",
    "Niveau",
    "SearchHit",
    "Slide",
    "Source",
    "TutorState",
    "est_course_id_valide",
    "slide_id",
]
