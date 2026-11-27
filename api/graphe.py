"""A3 — Graphe réel du tuteur pour l'API : agents O2 / O3 / A2 / A4 (+ B3 quand il sera mergé).

Le graphe LangGraph (O1) est construit **une seule fois** (``graphe()``), au premier appel :

    construire_graphe({"expliquer": explainer_agent, "quiz": quiz_verifie_agent,
                       "ressources": resources_agent, "question": <qa>}, critic=critic_agent)

``executer_avec_progression`` exécute un tour dans un thread (le LLM local est bloquant) et
produit des ``Evenement`` : progression (début, génération, vérification Critic, correction),
puis la réponse finale. ``/slide/{id}/explain`` et ``/ask`` s'en servent pour le JSON comme
pour le streaming SSE. Au-delà de ``API_TIMEOUT_LLM`` secondes (400 par défaut), ``DelaiDepasse``
est levée (504 côté API).

``API_CRITIC`` (``.env``) : ``on`` (défaut) insère la boucle Critic (O3) ; ``off`` construit le
graphe sans Critic, pour une démo sur CPU lent (une explication = un seul appel au LLM).

``API_QA`` (``.env``) : ``auto`` (défaut) branche le vrai Q&A (B3) si ``agents/qa.py`` existe,
protégé par ``AgentQAProtege`` (toute erreur pendant l'appel — modèles RAG absents, index Qdrant
vide… — donne une réponse de repli au lieu de faire échouer ``/ask``) ; ``bouchon`` force le
bouchon d'O1 (tests, démo sans modèles RAG).
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import os
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from agents import quiz as qz
from agents.critic import critic_agent, quiz_verifie_agent, texte_sources, verifier_qcm
from agents.explainer import explainer_agent
from agents.graph import AGENTS_BOUCHONS, INTENTIONS_CRITIQUEES, NOEUD_PAR_INTENTION, Agent, construire_graphe
from agents.resources import resources_agent
from api.models import NiveauBloom
from schemas.models import AgentResponse, Intention, Langue, Message, TutorState

log = logging.getLogger(__name__)

TIMEOUT_LLM_PAR_DEFAUT = 400.0  # Explainer + Critic sur CPU : ~290 s
INTERVALLE_PING = 15.0  # commentaire SSE ``: ping`` pendant les longues générations

# Valeur du champ ``agent`` d'``AgentResponse`` pour chaque intention (noms des nœuds O1).
AGENT_PAR_INTENTION: dict[Intention, str] = dict(NOEUD_PAR_INTENTION)

MESSAGES_ETAPES: dict[str, str] = {
    "debut": "Demande reçue, préparation du contexte…",
    "generation": "Le modèle local rédige la réponse…",
    "verification": "Le Critic vérifie la réponse sur les slides…",
    "correction": "Réponse corrigée selon le Critic…",
}


class DelaiDepasse(TimeoutError):
    """Le LLM local n'a pas répondu dans ``API_TIMEOUT_LLM`` secondes.

    ``brouillon`` : réponse de l'agent déjà produite mais pas encore validée par le Critic
    (le délai est tombé pendant la vérification), sinon ``None``.
    """

    def __init__(self, message: str, brouillon: AgentResponse | None = None) -> None:
        super().__init__(message)
        self.brouillon = brouillon


def critic_actif() -> bool:
    """Boucle Critic activée ? (``.env`` : ``API_CRITIC=on|off``, défaut ``on``)."""
    valeur = os.getenv("API_CRITIC", "on").strip().lower()
    if valeur in ("off", "0", "false", "non", "no"):
        return False
    if valeur not in ("on", "1", "true", "oui", "yes", ""):
        log.warning("API_CRITIC=%r inconnu, Critic activé (valeurs : on | off)", valeur)
    return True


def timeout_llm() -> float:
    """Délai maximal d'un tour (``.env`` : ``API_TIMEOUT_LLM``, défaut 400 s)."""
    try:
        valeur = float(os.getenv("API_TIMEOUT_LLM", TIMEOUT_LLM_PAR_DEFAUT))
    except ValueError:
        return TIMEOUT_LLM_PAR_DEFAUT
    return valeur if valeur > 0 else TIMEOUT_LLM_PAR_DEFAUT


def mode_qa() -> str:
    """Agent Q&A voulu (``.env`` : ``API_QA=auto|bouchon``, défaut ``auto``)."""
    valeur = os.getenv("API_QA", "auto").strip().lower()
    if valeur in ("bouchon", "stub", "off"):
        return "bouchon"
    if valeur not in ("auto", ""):
        log.warning("API_QA=%r inconnu, mode auto (valeurs : auto | bouchon)", valeur)
    return "auto"


# --------------------------------------------------------------------------- construction

MESSAGE_QA_INDISPONIBLE = "Le Q&A n'est pas disponible : modèles RAG non installés ou cours non indexé."


def repli_qa(state: TutorState) -> dict[str, Any]:
    """Réponse du bouchon d'O1, avec un message clair à la place du texte provisoire."""
    sortie = AGENTS_BOUCHONS["question"](state)
    historique = list(sortie.get("historique", []))
    if historique and historique[-1].role == "tuteur":
        historique[-1] = Message(role="tuteur", contenu=MESSAGE_QA_INDISPONIBLE)
    return {**sortie, "reponse": MESSAGE_QA_INDISPONIBLE, "historique": historique}


class AgentQAProtege:
    """Vrai agent Q&A (B3) qui ne fait jamais échouer ``/ask``.

    Le Q&A charge bge-m3, le reranker et l'index Qdrant au premier appel : si l'appel lève
    (``OSError`` modèle non téléchargé, ``ImportError``, index absent…), l'erreur est journalisée
    et ``repli_qa`` répond. L'indisponibilité est mémorisée : les requêtes suivantes vont
    directement au repli (redémarrer l'API après avoir installé les modèles / indexé le cours).
    """

    def __init__(self, agent: Agent | None, *, raison: str | None = None) -> None:
        self.agent = agent
        self.indisponible: str | None = raison or (None if agent is not None else "agent absent")
        self._verrou = threading.Lock()

    def __getattr__(self, nom: str) -> Any:  # attributs de l'agent réel (ex. ``recherche``)
        agent = self.__dict__.get("agent")
        if agent is None:
            raise AttributeError(nom)
        return getattr(agent, nom)

    def __call__(self, state: TutorState) -> dict[str, Any]:
        if self.indisponible is None and self.agent is not None:
            try:
                return self.agent(state)
            except Exception as e:  # noqa: BLE001 — /ask doit toujours répondre
                with self._verrou:
                    if self.indisponible is None:
                        log.error("agent Q&A indisponible, repli sur le bouchon jusqu'au redémarrage : %r",
                                  e, exc_info=True)
                    self.indisponible = repr(e)
        return repli_qa(state)



def agent_qa_disponible() -> bool:
    """``agents/qa.py`` (B3, Both) est-il présent ?"""
    return importlib.util.find_spec("agents.qa") is not None


def construire_agent_qa() -> tuple[Agent, str]:
    """Agent Q&A (B3) protégé s'il existe et se construit, sinon un bouchon ; renvoie ``(agent, origine)``.

    ``API_QA=bouchon`` ou ``agents/qa.py`` absent : bouchon d'O1. Construction en échec : repli
    avec ``MESSAGE_QA_INDISPONIBLE`` (origine ``bouchon``).
    """
    if mode_qa() == "bouchon" or not agent_qa_disponible():
        return AGENTS_BOUCHONS["question"], "bouchon"
    try:
        qa = importlib.import_module("agents.qa")
        rerank = importlib.import_module("rag.rerank")
        search = importlib.import_module("rag.search")
        store_mod = importlib.import_module("rag.store")
        store = store_mod.VectorStore(store_mod.BgeM3Embedder(), chemin=os.getenv("QDRANT_PATH", "qdrant_storage"))
        recherche = rerank.RechercheReranked(search.RechercheHybride(store), rerank.BgeReranker())
        return AgentQAProtege(qa.AgentQA(recherche)), "qa"
    except Exception as e:  # modèles d'embedding ou index absents : on garde l'API utilisable
        log.warning("agents.qa présent mais non construit (%r) : repli Q&A", e)
        return AgentQAProtege(None, raison=repr(e)), "bouchon"


@lru_cache(maxsize=1)
def graphe() -> Any:
    """Graphe compilé, construit au premier appel puis réutilisé (``API_CRITIC`` lu à ce moment)."""
    qa, origine = construire_agent_qa()
    critic = critic_agent if critic_actif() else None
    log.info("graphe du tuteur construit (Q&A : %s, Critic : %s)", origine, "on" if critic else "off")
    return construire_graphe(
        {"expliquer": explainer_agent, "quiz": quiz_verifie_agent,
         "ressources": resources_agent, "question": qa},
        critic=critic,
    )


# --------------------------------------------------------------------------- exécution


@dataclass
class Evenement:
    """Progression (``etape`` ≠ ``"fin"``) ou réponse finale (``etape == "fin"``, ``reponse``).

    ``brouillon`` (étape ``verification``) : réponse de l'agent avant le jugement du Critic.
    """

    etape: str
    donnees: dict[str, Any] = field(default_factory=dict)
    reponse: AgentResponse | None = None
    brouillon: AgentResponse | None = None


def vers_reponse(etat: TutorState) -> AgentResponse:
    return AgentResponse(
        agent=AGENT_PAR_INTENTION.get(etat.intention or "question", "qa"),  # type: ignore[arg-type]
        reponse=etat.reponse,
        sources=etat.sources,
        score_fidelite=etat.score_fidelite,
    )


def _progression(noeud: str, mise_a_jour: dict[str, Any], etat: dict[str, Any],
                 avec_critic: bool = True) -> Evenement | None:
    """Événement de progression émis après chaque nœud du graphe."""
    if noeud == "router":
        intention = etat.get("intention") or "question"
        return Evenement("generation", {"agent": AGENT_PAR_INTENTION.get(intention, "qa")})
    if noeud == "critic":
        if mise_a_jour.get("corrections"):
            return Evenement("correction", {"iteration": mise_a_jour.get("iterations_critic", 0),
                                            "score_fidelite": mise_a_jour.get("score_fidelite")})
        return None
    if (avec_critic and noeud in NOEUD_PAR_INTENTION.values()
            and etat.get("intention") in INTENTIONS_CRITIQUEES):
        return Evenement("verification", {}, brouillon=vers_reponse(TutorState.model_validate(etat)))
    return None


def _derouler(state: TutorState, g: Any, emettre: Any) -> None:
    """Exécuter le graphe (thread de travail) en émettant la progression puis la réponse."""
    etat = state.model_dump()
    avec_critic = "critic" in getattr(g, "nodes", {"critic": None})
    emettre(Evenement("debut", {}))
    for morceau in g.stream(state, stream_mode="updates"):
        for noeud, mise_a_jour in morceau.items():
            etat.update(mise_a_jour or {})
            evenement = _progression(noeud, mise_a_jour or {}, etat, avec_critic)
            if evenement is not None:
                emettre(evenement)
    emettre(Evenement("fin", {}, vers_reponse(TutorState.model_validate(etat))))


async def executer_avec_progression(
    state: TutorState, *, timeout: float | None = None, g: Any | None = None
) -> AsyncIterator[Evenement | None]:
    """Événements d'un tour ; ``None`` = rien de neuf depuis ``INTERVALLE_PING`` s (pour le ping SSE).

    Lève ``DelaiDepasse`` au-delà du timeout, ``agents.llm.LLMIndisponible`` (ou toute autre erreur)
    si le graphe échoue. Le thread de travail ne peut pas être interrompu : une génération
    abandonnée se termine en arrière-plan (``agents.llm`` sérialise les appels).
    """
    boucle = asyncio.get_running_loop()
    file: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    g = g if g is not None else graphe()
    limite = time.monotonic() + (timeout if timeout is not None else timeout_llm())

    def poster(genre: str, valeur: Any) -> None:
        try:
            boucle.call_soon_threadsafe(file.put_nowait, (genre, valeur))
        except RuntimeError:  # requête abandonnée (timeout, client parti) : boucle déjà fermée
            pass

    def travail() -> None:
        try:
            _derouler(state, g, lambda e: poster("ev", e))
        except BaseException as e:  # transmis au client asynchrone
            poster("erreur", e)
        finally:
            poster("fin", None)

    threading.Thread(target=travail, name="tuteur-graphe", daemon=True).start()
    brouillon: AgentResponse | None = None
    while True:
        reste = limite - time.monotonic()
        if reste <= 0:
            delai = timeout_llm() if timeout is None else timeout
            raise DelaiDepasse(f"le modèle local n'a pas répondu en {delai:.0f} s", brouillon)
        try:
            genre, valeur = await asyncio.wait_for(file.get(), min(reste, INTERVALLE_PING))
        except asyncio.TimeoutError:
            yield None
            continue
        if genre == "erreur":
            raise valeur
        if genre == "fin":
            return
        if valeur.brouillon is not None:
            brouillon = valeur.brouillon
        yield valeur


async def executer_tour(state: TutorState, *, timeout: float | None = None, g: Any | None = None) -> AgentResponse:
    """Réponse finale d'un tour (sans streaming)."""
    async for evenement in executer_avec_progression(state, timeout=timeout, g=g):
        if evenement is not None and evenement.reponse is not None:
            return evenement.reponse
    raise RuntimeError("le graphe s'est terminé sans réponse")


# --------------------------------------------------------------------------- quiz vérifié


def quiz_verifie(
    course_id: str,
    slide: int | None,
    n: int,
    niveau_bloom: NiveauBloom | None = None,
    langue: Langue | None = None,
) -> qz.ResultatQuiz:
    """QCM de l'agent Quiz (A2) filtrés par le Critic (O3), comme ``quiz_verifie_agent``.

    ``quiz_verifie_agent`` renvoie un texte formaté et ignore ``n`` / ``niveau_bloom`` / le
    quiz sur tout le cours ; ``GET /quiz`` a besoin de la liste de ``QCM`` : on applique donc
    les mêmes contrôles (``verifier_qcm``) à la sortie de ``generer_quiz_detaille``.
    """
    resultat = qz.generer_quiz_detaille(course_id, slide, n, niveau_bloom, langue=langue)
    textes = texte_sources([q.source for q in resultat.qcm], qz.charger_cours)
    retenus = []
    for q in resultat.qcm:
        problemes = verifier_qcm(q, textes.get(q.source.numero, ""))
        if problemes:
            log.info("QCM écarté par le Critic (%s) : %s", "; ".join(problemes), q.question[:80])
        else:
            retenus.append(q)
    if retenus:
        return qz.ResultatQuiz(retenus)
    return qz.ResultatQuiz([], resultat.message or "Quiz indisponible : aucun QCM n'a passé la vérification du Critic.")


__all__ = [
    "AgentQAProtege",
    "DelaiDepasse",
    "MESSAGE_QA_INDISPONIBLE",
    "Evenement",
    "MESSAGES_ETAPES",
    "agent_qa_disponible",
    "construire_agent_qa",
    "critic_actif",
    "executer_avec_progression",
    "executer_tour",
    "graphe",
    "mode_qa",
    "repli_qa",
    "quiz_verifie",
    "timeout_llm",
    "vers_reponse",
]
