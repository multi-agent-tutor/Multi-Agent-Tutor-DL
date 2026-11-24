"""B3 — Agent Q&A : répond à une question uniquement à partir des slides, avec citations.

Étapes :
1. Recherche des passages via B2 (hybride + reranker) dans le cours courant.
2. Si aucun passage n'atteint le seuil (minimal) du reranker : refus
   (« L'information n'est pas dans le cours. »), sans appeler le LLM.
3. Sinon, le LLM local (A0, ``agents/llm.py``) rédige la réponse à partir des seuls
   passages, en citant [Slide N] après chaque affirmation.
4. Les citations sont vérifiées : un numéro de slide qui n'était pas dans les passages
   est retiré ; une réponse sans citation reçoit celle du meilleur passage.
5. Si le LLM est indisponible : repli extractif (le passage le plus pertinent, cité).

Brancher l'agent dans le graphe d'Ons (O1) :

    from agents.graph import construire_graphe
    from agents.qa import AgentQA
    agent = AgentQA(recherche)            # recherche = rag.rerank.RechercheReranked(...)
    graphe = construire_graphe({"question": agent})
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from agents import llm
from eval.schema import REPONSE_HORS_COURS
from schemas.models import AgentResponse, Message, SearchHit, Source, TutorState

log = logging.getLogger(__name__)

# Score minimal du reranker (0..1) pour qu'un passage soit envoyé au LLM. bge-reranker note
# surtout « ce passage répond-il à la question ? » : une slide du bon sujet mais sans définition
# peut avoir un score bas (0,03), alors qu'une question hors sujet est à 0,000. Le seuil ne sert
# donc qu'à écarter le hors-sujet évident ; le LLM refuse ensuite si les passages ne suffisent pas.
# Réglable par .env (QA_SEUIL) ; B4 l'ajustera sur le jeu d'évaluation.
SEUIL_PERTINENCE = float(os.getenv("QA_SEUIL", "0.01"))
K_PASSAGES = 5
LONGUEUR_PASSAGE = 1200  # caractères gardés par passage dans le prompt (contexte du LLM limité)
LONGUEUR_EXTRAIT = 200  # caractères gardés dans Source.extrait
MAX_TOKENS = 512

CITATION = re.compile(r"\[\s*Slides?\s*(\d+(?:\s*[,;]\s*\d+)*)\s*\]", re.IGNORECASE)

LANGUES = {"fr": "français", "en": "anglais", "ar": "arabe", "mixte": "la langue de la question"}

SYSTEME = """Tu es le tuteur d'un cours. Tu réponds à la question de l'étudiant UNIQUEMENT à partir des passages du cours fournis.
Règles :
- N'utilise aucune connaissance extérieure aux passages.
- Après chaque phrase ou affirmation, cite la slide d'où elle vient, au format [Slide N].
- Si les passages ne permettent pas de répondre, réponds exactement : « {refus} »
- Réponds en {langue}, de façon claire et concise (5 phrases au maximum)."""


class Recherche(Protocol):
    """Ce dont l'agent a besoin : la recherche finale de B2 (``RechercheReranked``)."""

    def rechercher(self, requete: str, course_id: str | None = None, k: int | None = None) -> list[SearchHit]:
        ...


def construire_prompt(
    question: str, passages: Sequence[SearchHit], corrections: Sequence[str] = ()
) -> str:
    """Passages numérotés par slide, la question, puis les corrections du Critic (O3) s'il y en a."""
    blocs = []
    for hit in passages:
        c = hit.chunk
        titre = f" — {c.titre}" if c.titre else ""
        blocs.append(f"[Slide {c.numero}]{titre}\n{c.contenu[:LONGUEUR_PASSAGE]}")
    texte = "Passages du cours :\n\n" + "\n\n".join(blocs) + f"\n\nQuestion : {question}\n"
    if corrections:
        texte += (
            "\nTa réponse précédente contenait des affirmations non appuyées par les passages :\n"
            + "\n".join(f"- {c}" for c in corrections)
            + "\nRéécris la réponse en retirant ou en corrigeant ces affirmations.\n"
        )
    return texte + "Réponse :"


def slides_citees(texte: str) -> list[int]:
    """Numéros cités dans un texte (« [Slide 3] », « [Slides 3, 4] »), dans l'ordre, sans doublon."""
    vus: list[int] = []
    for groupe in CITATION.findall(texte):
        for n in re.split(r"[,;]", groupe):
            numero = int(n)
            if numero not in vus:
                vus.append(numero)
    return vus


def nettoyer_citations(texte: str, autorisees: set[int]) -> str:
    """Retirer les citations de slides absentes des passages (citations inventées)."""

    def remplacer(m: re.Match[str]) -> str:
        gardes = [n.strip() for n in re.split(r"[,;]", m.group(1)) if int(n) in autorisees]
        if not gardes:
            return ""
        return f"[Slide {gardes[0]}]" if len(gardes) == 1 else f"[Slides {', '.join(gardes)}]"

    texte = CITATION.sub(remplacer, texte)
    texte = re.sub(r"\s+([.,;:!?])", r"\1", texte)  # espace laissé avant la ponctuation
    return re.sub(r"\s{2,}", " ", texte).strip()


def est_refus(texte: str) -> bool:
    """La réponse est-elle le refus « hors cours » ?"""
    return REPONSE_HORS_COURS.lower().rstrip(".") in texte.lower()


class AgentQA:
    """Agent Q&A (B3), utilisable seul (``repondre``) ou comme nœud du graphe (appel direct)."""

    def __init__(
        self,
        recherche: Recherche,
        seuil: float = SEUIL_PERTINENCE,
        k: int = K_PASSAGES,
        max_tokens: int = MAX_TOKENS,
        generer: Callable[..., str] | None = None,
    ) -> None:
        self.recherche = recherche
        self.seuil = seuil
        self.k = k
        self.max_tokens = max_tokens
        self._generer = generer or llm.generer_texte

    def passages(self, question: str, course_id: str) -> list[SearchHit]:
        """Passages du cours assez pertinents (score du reranker ≥ seuil)."""
        hits = self.recherche.rechercher(question, course_id=course_id, k=self.k)
        return [h for h in hits if h.score >= self.seuil]

    def repondre(
        self, question: str, course_id: str, langue: str = "fr", corrections: Sequence[str] = ()
    ) -> AgentResponse:
        """Répondre à une question sur un cours, avec les sources citées.

        ``corrections`` : affirmations rejetées par le Critic (O3) au tour précédent.
        """
        passages = self.passages(question, course_id) if question.strip() else []
        if not passages:
            return AgentResponse(agent="qa", reponse=REPONSE_HORS_COURS, sources=[])

        systeme = SYSTEME.format(refus=REPONSE_HORS_COURS, langue=LANGUES.get(langue, "français"))
        try:
            prompt = construire_prompt(question, passages, corrections)
            texte = self._generer(systeme, prompt, max_tokens=self.max_tokens)
        except llm.LLMIndisponible as e:
            log.warning("LLM indisponible, repli extractif : %s", e)
            meilleur = passages[0].chunk
            texte = f"Voici le passage du cours le plus pertinent : {meilleur.contenu[:400]} [Slide {meilleur.numero}]"

        if est_refus(texte):
            return AgentResponse(agent="qa", reponse=REPONSE_HORS_COURS, sources=[])

        par_numero = {h.chunk.numero: h.chunk for h in passages}
        texte = nettoyer_citations(texte, set(par_numero))
        citees = slides_citees(texte)
        if not citees:  # le LLM n'a rien cité : on rattache la réponse au meilleur passage
            citees = [passages[0].chunk.numero]
            texte = f"{texte} [Slide {citees[0]}]"
        sources = [
            Source(course_id=course_id, numero=n, extrait=par_numero[n].contenu[:LONGUEUR_EXTRAIT])
            for n in citees
        ]
        return AgentResponse(agent="qa", reponse=texte, sources=sources)

    def __call__(self, state: TutorState) -> dict[str, Any]:
        """Nœud LangGraph : met à jour la réponse, les sources et l'historique."""
        corrections = getattr(state, "corrections", None) or []  # rempli par le Critic (O3)
        resultat = self.repondre(state.question, state.course_id, state.langue_reponse, corrections)
        historique = list(state.historique)
        if state.question:
            historique.append(Message(role="utilisateur", contenu=state.question))
        historique.append(Message(role="tuteur", contenu=resultat.reponse))
        return {"reponse": resultat.reponse, "sources": resultat.sources, "historique": historique}


def _demo() -> None:
    """python -m agents.qa "question" [--cours course.json] : B1 + B2 + A0 + B3 sur un cours."""
    import argparse

    from rag.index import charger_cours, indexer_cours
    from rag.rerank import BgeReranker, RechercheReranked
    from rag.search import RechercheHybride
    from rag.store import BgeM3Embedder, VectorStore

    parser = argparse.ArgumentParser(description="Démo de l'agent Q&A (B3).")
    parser.add_argument("question")
    parser.add_argument("--cours", default="schemas/exemples/exemple_cours.json", help="course.json à interroger")
    args = parser.parse_args()

    cours = charger_cours(args.cours)
    store = VectorStore(BgeM3Embedder())  # en mémoire : rien n'est écrit sur le disque
    indexer_cours(store, cours)
    agent = AgentQA(RechercheReranked(RechercheHybride(store), BgeReranker()))
    print(f"LLM : {llm.backend()} ({llm.modele()}), configuré : {llm.est_configure()}")
    r = agent.repondre(args.question, cours.id, cours.langue)
    print(f"\n{r.reponse}\n")
    for s in r.sources:
        print(f"  [Slide {s.numero}] {s.extrait[:80]}")


if __name__ == "__main__":
    _demo()


__all__ = [
    "AgentQA",
    "K_PASSAGES",
    "SEUIL_PERTINENCE",
    "construire_prompt",
    "est_refus",
    "nettoyer_citations",
    "slides_citees",
]
