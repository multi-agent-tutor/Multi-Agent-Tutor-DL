"""B4 — Métriques du benchmark, calculées en local (règle v2 : aucune API).

Les trois métriques reprennent les définitions de RAGAS ; seuls le juge et les
embeddings changent : le LLM local de l'équipe (A0) et bge-m3 au lieu d'une API.

- **context precision** (RAGAS, variante « avec référence ») : les slides de référence
  de C2 sont-elles en tête des passages retrouvés ? Moyenne des précisions@k aux rangs
  où un passage pertinent apparaît. Sans LLM : calcul exact et reproductible.
- **faithfulness** : part des affirmations de la réponse appuyées par les passages
  retrouvés. Juge = LLM local, qui découpe la réponse en affirmations et juge chacune
  (même procédure que le Critic O3) ; repli lexical sans LLM.
- **answer relevancy** : le LLM génère 3 questions à partir de la réponse ; score =
  similarité cosinus moyenne (bge-m3) avec la question posée. Une réponse vague ou hors
  sujet produit des questions éloignées. Repli sans LLM : cosinus question/réponse.

S'ajoutent deux mesures propres au tuteur : le **refus correct** (questions hors cours)
et le **faux refus** (refus sur une question dont la réponse est dans le cours).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence

from pydantic import BaseModel, Field

from agents import llm
from agents.qa import est_refus

log = logging.getLogger(__name__)

NB_QUESTIONS_GENEREES = 3

Juge = Callable[[str, dict[int, str]], float | None]
Encodeur = Callable[[Sequence[str]], list[list[float]]]


def precision_contexte(recuperes: Sequence[int], reference: set[int]) -> float | None:
    """Context precision (avec référence) : moyenne des précisions@k aux rangs pertinents.

    ``recuperes`` = numéros des slides retrouvées, dans l'ordre ; ``reference`` = slides
    qui justifient la réponse (C2). ``None`` si la question n'a pas de référence (hors cours).
    Exemple : recuperes = [4, 2, 9], reference = {2} → précision@2 = 1/2 → 0,5.
    """
    if not reference:
        return None
    pertinents, somme = 0, 0.0
    for k, numero in enumerate(recuperes, start=1):
        if numero in reference:
            pertinents += 1
            somme += pertinents / k
    return somme / pertinents if pertinents else 0.0


def cosinus(a: Sequence[float], b: Sequence[float]) -> float:
    """Similarité cosinus de deux vecteurs (0 si l'un est nul)."""
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def juge_critic(reponse: str, textes: dict[int, str]) -> float | None:
    """Faithfulness jugée par le LLM local, avec la procédure du Critic (O3).

    Le Critic découpe la réponse en affirmations et juge chacune contre les slides ;
    sans LLM, il se replie sur un jugement lexical.
    """
    from agents.critic import juger  # O3 (Ons) : import tardif, module optionnel

    if not any(textes.values()):
        return None
    return juger(reponse, textes).score


def juge_lexical(reponse: str, textes: dict[int, str]) -> float | None:
    """Faithfulness sans LLM (rapide, approximative) : repli lexical du Critic."""
    from agents.critic import juger_sans_llm

    if not any(textes.values()):
        return None
    return juger_sans_llm(reponse, textes).score


def fidelite(reponse: str, textes: dict[int, str], juge: Juge) -> float | None:
    """Faithfulness d'une réponse ; ``None`` pour un refus (rien à vérifier)."""
    if not reponse.strip() or est_refus(reponse):
        return None
    return juge(reponse, textes)


class QuestionsGenerees(BaseModel):
    questions: list[str] = Field(
        description="Questions auxquelles la réponse répond",
        json_schema_extra={"minItems": 1, "maxItems": NB_QUESTIONS_GENEREES},
    )


SYSTEME_QUESTIONS = (
    "On te donne la réponse d'un tuteur. Écris {n} questions courtes, dans la langue de la réponse, "
    "auxquelles cette réponse répond directement. N'ajoute rien qui ne soit pas dans la réponse."
)


def questions_depuis_reponse(reponse: str) -> list[str]:
    """Questions générées par le LLM local à partir d'une réponse (RAGAS answer relevancy)."""
    resultat = llm.generer_structure(
        SYSTEME_QUESTIONS.format(n=NB_QUESTIONS_GENEREES),
        f"Réponse :\n{reponse[:1500]}",
        QuestionsGenerees,
        max_tokens=200,
    )
    return [q for q in resultat.questions if q.strip()][:NB_QUESTIONS_GENEREES]


def pertinence(
    question: str,
    reponse: str,
    encoder: Encodeur,
    generer: Callable[[str], list[str]] | None = questions_depuis_reponse,
) -> float | None:
    """Answer relevancy ; ``None`` pour un refus.

    Avec ``generer`` : cosinus moyen entre la question et les questions générées depuis la
    réponse (RAGAS). Sans, ou si le LLM est indisponible : cosinus question / réponse.
    """
    if not reponse.strip() or est_refus(reponse):
        return None
    generees: list[str] = []
    if generer is not None:
        try:
            generees = generer(reponse)
        except llm.LLMIndisponible as e:
            log.warning("answer relevancy : LLM indisponible, repli cosinus question/réponse : %s", e)
    cibles = generees or [reponse]
    vecteurs = encoder([question, *cibles])
    return sum(cosinus(vecteurs[0], v) for v in vecteurs[1:]) / len(cibles)


def moyenne(valeurs: Sequence[float | None]) -> float | None:
    """Moyenne en ignorant les ``None`` (métrique non applicable)."""
    presentes = [v for v in valeurs if v is not None]
    return sum(presentes) / len(presentes) if presentes else None


def centile(valeurs: Sequence[float], q: float) -> float | None:
    """Centile ``q`` (0..1) par interpolation linéaire."""
    if not valeurs:
        return None
    tri = sorted(valeurs)
    position = (len(tri) - 1) * q
    bas, haut = math.floor(position), math.ceil(position)
    return tri[bas] + (tri[haut] - tri[bas]) * (position - bas)


__all__ = [
    "centile",
    "cosinus",
    "fidelite",
    "juge_critic",
    "juge_lexical",
    "moyenne",
    "pertinence",
    "precision_contexte",
    "questions_depuis_reponse",
]
