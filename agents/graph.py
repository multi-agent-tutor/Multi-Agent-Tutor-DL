"""O1 — Squelette LangGraph : orchestrateur multi-agent et état partagé.

Le graphe reçoit un ``TutorState`` (schéma T0), classe l'intention de l'utilisateur
dans le nœud ``router``, puis appelle l'agent correspondant :

    START → router → explainer | qa | quiz | resources → END

Les agents sont pour l'instant des **bouchons** qui renvoient une réponse fixe.
Chaque membre remplace le sien sans toucher au graphe, en passant sa fonction
à ``construire_graphe`` :

    graphe = construire_graphe({"question": agent_qa})       # Both (B3)
    graphe = construire_graphe({"quiz": agent_quiz})         # Ali (A2)

Un agent est une fonction ``(TutorState) -> dict`` qui renvoie les champs mis à jour
(``reponse``, ``sources``, ``historique``…), comme tout nœud LangGraph.

Boucle de correction (O3) : avec ``critic=``, les réponses texte (explication, question)
passent par le Critic avant ``END`` ; s'il renvoie des ``corrections``, la réponse repart vers
l'agent d'origine (2 fois au plus, ``iterations_critic``) :

    START → router → explainer | qa ⇄ critic → END
                   → quiz | resources → END

    graphe = construire_graphe({...}, critic=critic_agent)   # agents.critic
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from schemas import Message, Source, TutorState
from schemas.models import Intention

Agent = Callable[[TutorState], dict[str, Any]]

# Nom du nœud LangGraph associé à chaque intention.
NOEUD_PAR_INTENTION: dict[Intention, str] = {
    "expliquer": "explainer",
    "question": "qa",
    "quiz": "quiz",
    "ressources": "resources",
}

# Mots-clés (FR / EN), sans accents, testés dans cet ordre ; « question » est le cas par défaut.
MOTS_CLES: list[tuple[Intention, tuple[str, ...]]] = [
    ("quiz", ("quiz", "qcm", "flashcard", "teste moi", "interroge", "test me", "exercice")),
    # « lien » / « link » sont exclus : « quel est le lien entre X et Y » est une question.
    ("ressources", ("ressource", "resource", "video", "youtube", "pour aller plus loin",
                    "lecture complementaire", "further reading")),
    ("expliquer", ("explique", "explication", "expliquer", "explain", "resume la slide", "c est quoi cette slide",
                   "je ne comprends pas cette slide", "what does this slide")),
]


def _normaliser(texte: str) -> str:
    """Mettre en minuscules, retirer les accents et la ponctuation."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).strip()


def classer_intention(question: str) -> Intention:
    """Classer une demande par mots-clés (version provisoire, remplaçable par un LLM)."""
    texte = f" {_normaliser(question)} "
    for intention, mots in MOTS_CLES:
        if any(f" {mot}" in texte for mot in mots):
            return intention
    return "question"


def router(state: TutorState) -> dict[str, Any]:
    """Nœud Router : garde l'intention imposée par l'API, sinon la déduit de la question.

    Remet aussi à zéro l'état du Critic (O3), qui ne doit pas passer d'un tour à l'autre.
    """
    remise = {"iterations_critic": 0, "corrections": [], "score_fidelite": None}
    if state.intention is not None:
        return remise
    if not state.question.strip():
        return {**remise, "intention": "expliquer"}
    return {**remise, "intention": classer_intention(state.question)}


def _aiguiller(state: TutorState) -> str:
    """Choisir le nœud agent à partir de l'intention fixée par le router."""
    return NOEUD_PAR_INTENTION[state.intention or "question"]


def _bouchon(nom: str) -> Agent:
    """Créer un agent bouchon qui renvoie une réponse fixe citant la slide courante."""

    def agent(state: TutorState) -> dict[str, Any]:
        reponse = f"[{nom}] Réponse provisoire pour la slide {state.slide_courante} [Slide {state.slide_courante}]."
        historique = list(state.historique)
        if state.question:
            historique.append(Message(role="utilisateur", contenu=state.question))
        historique.append(Message(role="tuteur", contenu=reponse))
        return {
            "reponse": reponse,
            "sources": [Source(course_id=state.course_id, numero=state.slide_courante)],
            "historique": historique,
        }

    agent.__name__ = f"bouchon_{nom}"
    return agent


AGENTS_BOUCHONS: dict[Intention, Agent] = {
    intention: _bouchon(noeud) for intention, noeud in NOEUD_PAR_INTENTION.items()
}


# Intentions dont la réponse texte est vérifiée par le Critic (le quiz a son propre contrôle,
# les ressources viennent d'un catalogue externe au cours).
INTENTIONS_CRITIQUEES: tuple[Intention, ...] = ("expliquer", "question")


def _apres_critic(state: TutorState) -> str:
    """Corrections demandées : retour à l'agent d'origine ; sinon fin."""
    if state.corrections:
        return NOEUD_PAR_INTENTION[state.intention or "question"]
    return END


def construire_graphe(agents: Mapping[Intention, Agent] | None = None, *, critic: Agent | None = None) -> Any:
    """Construire et compiler le graphe ; ``agents`` remplace tout ou partie des bouchons.

    ``critic`` (O3) insère la boucle de correction après les agents de ``INTENTIONS_CRITIQUEES``.
    """
    inconnus = set(agents or {}) - set(NOEUD_PAR_INTENTION)
    if inconnus:
        raise ValueError(f"intentions inconnues : {sorted(inconnus)}")
    choisis = {**AGENTS_BOUCHONS, **(agents or {})}

    graphe = StateGraph(TutorState)
    graphe.add_node("router", router)
    if critic is not None:
        graphe.add_node("critic", critic)
        retours = [NOEUD_PAR_INTENTION[i] for i in INTENTIONS_CRITIQUEES]
        graphe.add_conditional_edges("critic", _apres_critic, [*retours, END])
    for intention, noeud in NOEUD_PAR_INTENTION.items():
        graphe.add_node(noeud, choisis[intention])
        critique = critic is not None and intention in INTENTIONS_CRITIQUEES
        graphe.add_edge(noeud, "critic" if critique else END)
    graphe.add_edge(START, "router")
    graphe.add_conditional_edges("router", _aiguiller, list(NOEUD_PAR_INTENTION.values()))
    return graphe.compile()


def executer(state: TutorState, graphe: Any | None = None) -> TutorState:
    """Exécuter un tour du tuteur et renvoyer l'état final validé."""
    resultat = (graphe or construire_graphe()).invoke(state)
    return TutorState.model_validate(resultat)
