"""O3 — Agent Critic : vérifie qu'une réponse est appuyée par le cours, avec le LLM local (A0).

1. Reçoit la réponse et ses sources ; relit le texte complet des slides citées
   (``agents.quiz.charger_cours``), à défaut l'extrait de chaque ``Source`` ;
2. contrôle les citations : un [Slide N] qui ne figure pas dans les sources est signalé ;
3. un appel ``agents.llm.generer_structure`` (``prompts/critic.md``, section « Fidélité »)
   découpe la réponse en affirmations et juge chacune ; sans LLM, repli lexical : une phrase
   est appuyée si la moitié au moins de ses mots pleins figurent dans les slides ;
4. sortie : ``score_fidelite`` (part des affirmations appuyées) + ``corrections``
   (affirmations non appuyées). Sous le seuil (``CRITIC_SEUIL``, 0,7 par défaut), la réponse
   repart vers l'agent d'origine avec les corrections, 2 fois au plus ; ensuite elle est
   livrée avec un avertissement.

Pour les quiz : ``verifier_qcm`` contrôle qu'il n'y a qu'une seule bonne réponse, juste, et
que les distracteurs sont faux ; ``quiz_verifie_agent`` enveloppe l'agent Quiz (A2) et
écarte les QCM rejetés.

Branchement dans le graphe (O1) :

    from agents.critic import critic_agent
    graphe = construire_graphe({...}, critic=critic_agent)
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agents import llm
from agents import quiz as qz
from agents.resources import mots_cles, normaliser
from api.models import QCM
from schemas import Course, Message, Source, TutorState

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
PROMPTS = RACINE / "prompts" / "critic.md"

SEUIL_FIDELITE = float(os.getenv("CRITIC_SEUIL", "0.7"))
MAX_ITERATIONS = 2  # borne de ``TutorState.iterations_critic``
SEUIL_LEXICAL = 0.5
MIN_MOTS_AFFIRMATION = 3
MAX_AFFIRMATIONS = 8
MAX_CARACTERES_SOURCES = 2400
MAX_CARACTERES_REPONSE = 1800
TOKENS_FIDELITE = 60 + 70 * MAX_AFFIRMATIONS
TOKENS_QCM = 120

REPONSE_HORS_COURS = "L'information n'est pas dans le cours."

ChargerCours = Callable[[str], Course | None]


# --------------------------------------------------------------------------- schémas LLM


def _texte(max_len: int, description: str) -> Any:
    return Field(description=description, json_schema_extra={"maxLength": max_len})


class AffirmationJugee(BaseModel):
    affirmation: str = _texte(240, "Affirmation factuelle tirée de la réponse")
    appuyee: bool = Field(description="Vrai si les slides fournies l'appuient")


class Jugement(BaseModel):
    affirmations: list[AffirmationJugee] = Field(
        default_factory=list, json_schema_extra={"maxItems": MAX_AFFIRMATIONS}
    )


class VerdictQCM(BaseModel):
    bonne_reponse_juste: bool
    distracteurs_faux: bool
    motif: str = _texte(200, "Problème en une phrase, vide si tout est correct")


@dataclass
class Evaluation:
    """Résultat du Critic sur une réponse texte."""

    score: float
    non_appuyees: list[str] = field(default_factory=list)
    nombre_affirmations: int = 0
    via_llm: bool = True

    def acceptee(self, seuil: float = SEUIL_FIDELITE) -> bool:
        return self.score >= seuil


# --------------------------------------------------------------------------- prompts


@lru_cache(maxsize=2)
def _lire_prompts(chemin: str, _mtime: float) -> dict[str, str]:
    sections: dict[str, str] = {}
    for bloc in re.split(r"^## ", Path(chemin).read_text(encoding="utf-8"), flags=re.M)[1:]:
        titre, _, corps = bloc.partition("\n")
        sections[normaliser(titre)] = corps.strip()
    return sections


PROMPT_SECOURS = (
    "Tu es un relecteur qui vérifie une réponse de tuteur. Juge uniquement par rapport aux "
    "slides fournies, jamais par tes propres connaissances."
)


def prompt_systeme(section: str) -> str:
    """Section ``## <section>`` de ``prompts/critic.md`` (prompt de secours si absente)."""
    if PROMPTS.is_file():
        texte = _lire_prompts(str(PROMPTS), PROMPTS.stat().st_mtime).get(normaliser(section))
        if texte:
            return texte
    log.warning("section %r absente de %s, prompt de secours", section, PROMPTS)
    return PROMPT_SECOURS


# --------------------------------------------------------------------------- texte des sources


def texte_sources(sources: list[Source], charger: ChargerCours = qz.charger_cours) -> dict[int, str]:
    """Texte complet de chaque slide source (titre, texte, notes, figures, formules)."""
    textes: dict[int, str] = {}
    cours_vus: dict[str, Course | None] = {}
    for s in sources:
        if s.course_id not in cours_vus:
            cours_vus[s.course_id] = charger(s.course_id)
        cours = cours_vus[s.course_id]
        if cours is not None and 1 <= s.numero <= cours.nombre_slides:
            sl = cours.slides[s.numero - 1]
            morceaux = [sl.titre, sl.texte, sl.notes, *sl.description_figures, *sl.formules_latex]
            texte = "\n".join(m.strip() for m in morceaux if m and m.strip())
        else:
            texte = ""
        textes[s.numero] = "\n".join(t for t in (textes.get(s.numero, ""), texte or s.extrait) if t)
    return textes


_CITATION = re.compile(r"\[Slide (\d+)\]")
_RUBRIQUE = re.compile(r"\*\*[^*]{1,60}\*\*\s*:?")


def citations(reponse: str) -> set[int]:
    return {int(n) for n in _CITATION.findall(reponse)}


def citations_orphelines(reponse: str, sources: list[Source]) -> list[int]:
    """Numéros cités dans la réponse qui ne figurent pas dans les sources."""
    connus = {s.numero for s in sources}
    return sorted(citations(reponse) - connus)


def affirmations(reponse: str) -> list[str]:
    """Phrases factuelles de la réponse, sans rubriques ni citations (pour le repli lexical)."""
    texte = _CITATION.sub(" ", _RUBRIQUE.sub(" ", reponse))
    morceaux = re.split(r"(?<=[.!?;])\s+|\n+", texte)
    phrases = [m.strip(" -•\t").strip() for m in morceaux]
    return [p for p in phrases if len(mots_cles(p)) >= MIN_MOTS_AFFIRMATION]


def _prefixes(mots: set[str]) -> set[str]:
    return {m[:5] for m in mots}


def appuyee_lexicalement(phrase: str, prefixes_sources: set[str]) -> bool:
    mots = mots_cles(phrase)
    if not mots:
        return True
    communs = sum(1 for m in mots if m[:5] in prefixes_sources)
    return communs / len(mots) >= SEUIL_LEXICAL


# --------------------------------------------------------------------------- évaluation


def _est_refus(reponse: str) -> bool:
    return normaliser(REPONSE_HORS_COURS) in normaliser(reponse)


def _bloc_sources(textes: dict[int, str]) -> str:
    lignes, reste = [], MAX_CARACTERES_SOURCES
    for numero in sorted(textes):
        corps = textes[numero][: max(reste, 0)]
        reste -= len(corps)
        lignes.append(f"[Slide {numero}]\n{corps}")
        if reste <= 0:
            break
    return "\n\n".join(lignes)


def juger_sans_llm(reponse: str, textes: dict[int, str]) -> Evaluation:
    """Repli lexical : part des phrases dont la moitié des mots pleins sont dans les slides."""
    prefixes = _prefixes(mots_cles("\n".join(textes.values())))
    phrases = affirmations(reponse)
    if not phrases:
        return Evaluation(1.0, [], 0, via_llm=False)
    rejetees = [p for p in phrases if not appuyee_lexicalement(p, prefixes)]
    return Evaluation(1 - len(rejetees) / len(phrases), rejetees, len(phrases), via_llm=False)


def juger(reponse: str, textes: dict[int, str]) -> Evaluation:
    """Jugement du LLM local ; repli lexical s'il est indisponible."""
    prompt = (
        f"Réponse à vérifier :\n{reponse[:MAX_CARACTERES_REPONSE]}\n\n"
        f"Slides sources :\n{_bloc_sources(textes)}"
    )
    try:
        jugement = llm.generer_structure(prompt_systeme("Fidélité"), prompt, Jugement,
                                         max_tokens=TOKENS_FIDELITE)
    except llm.LLMIndisponible as e:
        log.warning("critic : LLM local indisponible, repli lexical : %s", e)
        return juger_sans_llm(reponse, textes)
    jugees = [a for a in jugement.affirmations if a.affirmation.strip()][:MAX_AFFIRMATIONS]
    if not jugees:
        return Evaluation(1.0, [], 0)
    rejetees = [qz.nettoyer(a.affirmation) for a in jugees if not a.appuyee]
    return Evaluation(1 - len(rejetees) / len(jugees), rejetees, len(jugees))


def evaluer(
    reponse: str,
    sources: list[Source],
    *,
    charger: ChargerCours = qz.charger_cours,
) -> Evaluation | None:
    """Score de fidélité de ``reponse`` à ses ``sources`` ; ``None`` si rien n'est vérifiable."""
    if not reponse.strip() or not sources:
        return None
    if _est_refus(reponse):
        return Evaluation(1.0, [], 0, via_llm=False)
    textes = texte_sources(sources, charger)
    if not any(textes.values()):
        return None
    evaluation = juger(reponse, textes)
    orphelines = citations_orphelines(reponse, sources)
    if orphelines:
        # Chaque citation orpheline compte comme une affirmation non appuyée de plus.
        total = evaluation.nombre_affirmations + len(orphelines)
        appuyees = evaluation.score * evaluation.nombre_affirmations
        evaluation = Evaluation(
            appuyees / total,
            evaluation.non_appuyees
            + [f"La citation [Slide {n}] ne correspond à aucune source fournie." for n in orphelines],
            total,
            evaluation.via_llm,
        )
    return evaluation


# --------------------------------------------------------------------------- nœud du graphe


AVERTISSEMENTS: dict[str, str] = {
    "fr": "⚠ Vérification : {n} affirmation(s) de cette réponse ne sont pas clairement appuyées "
          "par le cours. Vérifie-les sur les slides citées.",
    "en": "⚠ Check: {n} statement(s) in this answer are not clearly supported by the course. "
          "Check them against the cited slides.",
    "ar": "⚠ تحقق: {n} من العبارات في هذه الإجابة غير مدعومة بوضوح في الدرس. راجعها في الشرائح المذكورة.",
}

CORRECTION_GENERIQUE = "Appuie chaque affirmation sur les slides citées et retire ce qu'elles ne disent pas."


def _sans_dernier_tour(state: TutorState) -> list[Message]:
    """Historique sans le dernier échange : l'agent le rejouera avec sa réponse corrigée."""
    historique = list(state.historique)
    if historique and historique[-1].role == "tuteur":
        historique.pop()
        if historique and historique[-1].role == "utilisateur" and historique[-1].contenu == state.question:
            historique.pop()
    return historique


def _avec_avertissement(state: TutorState, n: int) -> dict[str, Any]:
    note = AVERTISSEMENTS.get(state.langue_reponse, AVERTISSEMENTS["fr"]).format(n=n)
    reponse = f"{state.reponse}\n\n{note}"
    historique = list(state.historique)
    if historique and historique[-1].role == "tuteur":
        historique[-1] = Message(role="tuteur", contenu=reponse)
    return {"reponse": reponse, "historique": historique}


def critiquer(state: TutorState, *, charger: ChargerCours = qz.charger_cours,
              seuil: float = SEUIL_FIDELITE) -> dict[str, Any]:
    """Évaluer la réponse de l'état ; renvoyer les champs mis à jour (voir ``critic_agent``)."""
    evaluation = evaluer(state.reponse, state.sources, charger=charger)
    if evaluation is None:
        return {"score_fidelite": None, "corrections": []}
    sortie: dict[str, Any] = {"score_fidelite": round(evaluation.score, 3), "corrections": []}
    if evaluation.acceptee(seuil):
        return sortie
    if state.iterations_critic < MAX_ITERATIONS:
        log.info("critic : score %.2f < %.2f, renvoi à l'agent (itération %d)",
                 evaluation.score, seuil, state.iterations_critic + 1)
        return {
            **sortie,
            "corrections": evaluation.non_appuyees or [CORRECTION_GENERIQUE],
            "iterations_critic": state.iterations_critic + 1,
            "historique": _sans_dernier_tour(state),
        }
    return {**sortie, **_avec_avertissement(state, max(1, len(evaluation.non_appuyees)))}


def critic_agent(state: TutorState) -> dict[str, Any]:
    """Nœud LangGraph ``critic`` : ``corrections`` non vide = renvoyer à l'agent d'origine."""
    return critiquer(state)


# --------------------------------------------------------------------------- quiz


def problemes_structure(qcm: QCM) -> list[str]:
    """Contrôles sans LLM : 4 choix distincts et non vides, une seule bonne réponse."""
    choix = [normaliser(c) or c.strip().lower() for c in qcm.choix]
    problemes: list[str] = []
    if any(not c for c in choix):
        problemes.append("choix vide")
    if choix.count(choix[qcm.bonne_reponse]) > 1:
        problemes.append("la bonne réponse apparaît plusieurs fois")
    elif len(set(choix)) != len(choix):
        problemes.append("choix en double")
    if normaliser(qcm.question) in choix:
        problemes.append("la question est recopiée dans un choix")
    return problemes


def verifier_qcm(qcm: QCM, texte_slide: str = "") -> list[str]:
    """Problèmes du QCM (liste vide = valide) : structure, puis jugement du LLM sur la slide."""
    problemes = problemes_structure(qcm)
    if problemes or not texte_slide.strip():
        return problemes
    lettres = "ABCD"
    prompt = "\n".join([
        f"Slide :\n{texte_slide[:MAX_CARACTERES_SOURCES]}",
        "",
        f"Question : {qcm.question}",
        *[f"{lettres[i]}. {c}" for i, c in enumerate(qcm.choix)],
        f"Réponse indiquée comme bonne : {lettres[qcm.bonne_reponse]}",
    ])
    try:
        verdict = llm.generer_structure(prompt_systeme("QCM"), prompt, VerdictQCM, max_tokens=TOKENS_QCM)
    except llm.LLMIndisponible as e:
        log.info("critic quiz : LLM indisponible, contrôle de structure seulement : %s", e)
        return []
    if not verdict.bonne_reponse_juste:
        problemes.append(verdict.motif.strip() or "la bonne réponse n'est pas appuyée par la slide")
    if not verdict.distracteurs_faux:
        problemes.append(verdict.motif.strip() or "un distracteur est aussi une bonne réponse")
    return list(dict.fromkeys(problemes))


def quiz_verifie_agent(state: TutorState, *, charger: ChargerCours = qz.charger_cours) -> dict[str, Any]:
    """Agent Quiz (A2) suivi du Critic : seuls les QCM vérifiés sont proposés."""
    if qz.veut_flashcards(state.question):
        return qz.quiz_agent(state)
    resultat = qz.generer_quiz_detaille(state.course_id, state.slide_courante, langue=state.langue_reponse)
    textes = texte_sources([q.source for q in resultat.qcm], charger)
    retenus = []
    for q in resultat.qcm:
        problemes = verifier_qcm(q, textes.get(q.source.numero, ""))
        if problemes:
            log.info("QCM écarté par le Critic (%s) : %s", "; ".join(problemes), q.question[:80])
        else:
            retenus.append(q)
    score = len(retenus) / len(resultat.qcm) if resultat.qcm else None
    message = resultat.message or "Quiz indisponible : aucun QCM n'a passé la vérification du Critic."
    verifie = qz.ResultatQuiz(retenus, "" if retenus else message)
    reponse = qz.formater_quiz(verifie)
    sources = list({q.source.numero: q.source for q in retenus}.values()) or [
        Source(course_id=state.course_id, numero=state.slide_courante)
    ]
    historique = list(state.historique)
    if state.question:
        historique.append(Message(role="utilisateur", contenu=state.question))
    historique.append(Message(role="tuteur", contenu=reponse))
    return {"reponse": reponse, "sources": sources, "historique": historique, "score_fidelite": score}


__all__ = [
    "Evaluation",
    "MAX_ITERATIONS",
    "SEUIL_FIDELITE",
    "affirmations",
    "citations_orphelines",
    "critic_agent",
    "critiquer",
    "evaluer",
    "juger",
    "juger_sans_llm",
    "problemes_structure",
    "quiz_verifie_agent",
    "texte_sources",
    "verifier_qcm",
]
