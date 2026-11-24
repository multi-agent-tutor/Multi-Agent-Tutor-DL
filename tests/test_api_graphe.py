"""Tests A3 : routes de l'API branchées sur le graphe, SSE, 504, CORS 8765, bouchon / agents.qa.

LLM fake, aucun appel réseau (connexions hors boucle locale interdites).
"""

from __future__ import annotations

import json
import socket
import sys
import time
import types
from typing import Any
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

import agents.explainer as ex
from agents import llm
from agents.graph import AGENTS_BOUCHONS
from api import graphe as tuteur
from api import main
from schemas import AgentResponse, Message, TutorState

client = TestClient(main.app)

COURSE_ID = "ml_regression_lineaire_fr"
SLIDE_ID = f"{COURSE_ID}__s002"
QUESTION = {"course_id": COURSE_ID, "slide_courante": 2, "question": "Que minimise-t-on ?"}


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    monkeypatch.delenv("API_TIMEOUT_LLM", raising=False)
    monkeypatch.setattr(ex, "_prerequis_h3", lambda: None)
    monkeypatch.setenv("API_QA", "bouchon")  # jamais bge-m3 / reranker / index Qdrant ici
    tuteur.graphe.cache_clear()
    connect = socket.socket.connect

    def _local_seulement(sock: socket.socket, adresse: Any, *args: Any) -> Any:
        hote = adresse[0] if isinstance(adresse, tuple) else adresse
        if hote not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"appel réseau inattendu vers {adresse!r}")
        return connect(sock, adresse, *args)

    monkeypatch.setattr(socket.socket, "connect", _local_seulement)


class FauxGraphe:
    """Graphe minimal : mémorise l'état reçu, peut dormir ou échouer."""

    def __init__(self, *, attente: float = 0.0, erreur: Exception | None = None) -> None:
        self.attente, self.erreur, self.recu = attente, erreur, None

    def stream(self, state: TutorState, stream_mode: str = "updates"):  # noqa: ANN201
        self.recu = state
        yield {"router": {"intention": state.intention or "question"}}
        time.sleep(self.attente)
        if self.erreur is not None:
            raise self.erreur
        yield {"qa": {"reponse": "Réponse [Slide 2]", "sources": [{"course_id": state.course_id, "numero": 2}]}}
        yield {"critic": {"score_fidelite": 1.0, "corrections": []}}


def _evenements(texte: str) -> list[dict[str, Any]]:
    """Découper un flux SSE comme lireReponseAgent (frontend/src/api.ts)."""
    sortie = []
    for bloc in texte.replace("\r\n", "\n").split("\n\n"):
        lignes = bloc.split("\n")
        donnees = "\n".join(ligne[5:].lstrip(" ") for ligne in lignes if ligne.startswith("data:"))
        nom = next((ligne[6:].strip() for ligne in lignes if ligne.startswith("event:")), None)
        if donnees:
            sortie.append({"event": nom, "data": donnees})
    return sortie


# --------------------------------------------------------------------------- routes branchées


def test_graphe_construit_une_seule_fois() -> None:
    tuteur.graphe.cache_clear()
    assert tuteur.graphe() is tuteur.graphe()


@pytest.fixture
def graphe_neuf():  # noqa: ANN201
    """Reconstruire le graphe avec l'environnement du test, puis le cache par défaut."""
    tuteur.graphe.cache_clear()
    yield
    tuteur.graphe.cache_clear()


@pytest.mark.parametrize(("valeur", "attendu"), [
    (None, True), ("on", True), ("ON", True), ("off", False), ("0", False), ("n'importe", True),
])
def test_api_critic_lecture(monkeypatch: pytest.MonkeyPatch, valeur: str | None, attendu: bool) -> None:
    if valeur is None:
        monkeypatch.delenv("API_CRITIC", raising=False)
    else:
        monkeypatch.setenv("API_CRITIC", valeur)
    assert tuteur.critic_actif() is attendu


@pytest.mark.usefixtures("graphe_neuf")
@pytest.mark.parametrize("mode", ["on", "off"])
def test_api_critic_modes(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("API_CRITIC", mode)
    appels: list[str] = []
    vrai_critic = tuteur.critic_agent

    def critic_espion(state: TutorState) -> dict:
        appels.append("critic")
        return vrai_critic(state)

    monkeypatch.setattr(tuteur, "critic_agent", critic_espion)
    assert ("critic" in tuteur.graphe().nodes) is (mode == "on")

    r = client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant", "stream": 1})
    evs = _evenements(r.text)
    etapes = [json.loads(e["data"])["etape"] for e in evs if e["event"] == "progression"]
    finale = AgentResponse.model_validate_json(evs[-2]["data"])
    assert finale.agent == "explainer" and "[Slide 2]" in finale.reponse
    if mode == "on":
        assert etapes == ["debut", "generation", "verification"] and appels == ["critic"]
        assert finale.score_fidelite is not None
    else:
        assert etapes == ["debut", "generation"] and appels == []
        assert finale.score_fidelite is None


def test_explain_passe_par_explainer_et_critic() -> None:
    r = client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant"})
    rep = AgentResponse.model_validate(r.json())
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert rep.agent == "explainer" and "**Idée clé**" in rep.reponse and "[Slide 2]" in rep.reponse
    assert rep.sources[0].numero == 2 and rep.score_fidelite is not None  # rempli par le Critic


def test_ask_question_va_au_qa() -> None:
    r = client.post("/ask", json=QUESTION)
    rep = AgentResponse.model_validate(r.json())
    assert r.status_code == 200 and rep.agent == "qa" and "[Slide 2]" in rep.reponse


def test_ask_router_choisit_explainer() -> None:
    r = client.post("/ask", json={**QUESTION, "question": "Explique la slide 1"})
    rep = AgentResponse.model_validate(r.json())
    assert rep.agent == "explainer" and "[Slide 1]" in rep.reponse


def test_ask_construit_le_tutorstate(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = FauxGraphe()
    monkeypatch.setattr(tuteur, "graphe", lambda: faux)
    historique = [{"role": "utilisateur", "contenu": "Bonjour"}, {"role": "tuteur", "contenu": "Salut"}]
    r = client.post("/ask", json={**QUESTION, "niveau": "avance", "langue": "en", "historique": historique})
    assert r.status_code == 200
    assert faux.recu == TutorState(course_id=COURSE_ID, slide_courante=2, niveau="avance", langue_reponse="en",
                                   question="Que minimise-t-on ?",
                                   historique=[Message(**m) for m in historique])


def test_explain_impose_intention_expliquer(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = FauxGraphe()
    monkeypatch.setattr(tuteur, "graphe", lambda: faux)
    client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant"})
    assert faux.recu.intention == "expliquer" and faux.recu.niveau == "debutant" and faux.recu.slide_courante == 2


def test_quiz_filtre_par_le_critic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps({"qcm": [{
        "question": "Que minimise-t-on ?", "choix": ["MSE", "MAE", "R2", "AUC"], "bonne_reponse": 0,
        "explication": "MSE.", "niveau_bloom": "memoriser", "slide": 2}]}))
    vus: list[str] = []
    monkeypatch.setattr(tuteur, "verifier_qcm", lambda q, texte="": vus.append(q.question) or ["rejeté (test)"])
    r = client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200 and r.json() == [] and vus
    assert "Critic" in unquote(r.headers["x-quiz-message"])


def test_quiz_garde_les_qcm_valides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps({"qcm": [{
        "question": "Que minimise-t-on ?", "choix": ["MSE", "MAE", "R2", "AUC"], "bonne_reponse": 0,
        "explication": "MSE.", "niveau_bloom": "memoriser", "slide": 2}]}))
    monkeypatch.setattr(tuteur, "verifier_qcm", lambda q, texte="": [])
    r = client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200 and len(r.json()) == 1


# --------------------------------------------------------------------------- SSE


@pytest.mark.parametrize("mode", ["param", "accept"])
def test_explain_sse(mode: str) -> None:
    if mode == "param":
        r = client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant", "stream": 1})
    else:
        r = client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant"},
                       headers={"Accept": "text/event-stream, application/json"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    evs = _evenements(r.text)
    progression = [json.loads(e["data"]) for e in evs if e["event"] == "progression"]
    assert [p["etape"] for p in progression][:3] == ["debut", "generation", "verification"]
    # Les événements de progression ne modifient pas le texte affiché par le frontend.
    assert all("token" not in p and "reponse" not in p for p in progression)
    finale = AgentResponse.model_validate_json(evs[-2]["data"])
    assert finale.agent == "explainer" and "[Slide 2]" in finale.reponse
    assert evs[-1]["data"] == "[DONE]"


def test_ask_sse() -> None:
    r = client.post("/ask", params={"stream": "1"}, json=QUESTION)
    evs = _evenements(r.text)
    assert r.headers["content-type"].startswith("text/event-stream")
    assert AgentResponse.model_validate_json(evs[-2]["data"]).agent == "qa" and evs[-1]["data"] == "[DONE]"


def test_sse_correction_critic(monkeypatch: pytest.MonkeyPatch) -> None:
    class AvecCorrection(FauxGraphe):
        def stream(self, state, stream_mode="updates"):  # noqa: ANN001, ANN201
            yield {"router": {"intention": "question"}}
            yield {"qa": {"reponse": "x [Slide 2]"}}
            yield {"critic": {"corrections": ["faux"], "iterations_critic": 1, "score_fidelite": 0.2}}
            yield {"qa": {"reponse": "y [Slide 2]"}}
            yield {"critic": {"corrections": [], "score_fidelite": 1.0}}

    monkeypatch.setattr(tuteur, "graphe", lambda: AvecCorrection())
    evs = _evenements(client.post("/ask?stream=1", json=QUESTION).text)
    etapes = [json.loads(e["data"])["etape"] for e in evs if e["event"] == "progression"]
    assert etapes == ["debut", "generation", "verification", "correction", "verification"]
    assert AgentResponse.model_validate_json(evs[-2]["data"]).reponse == "y [Slide 2]"


def test_sse_sans_stream_reste_json() -> None:
    r = client.post("/ask", json=QUESTION, headers={"Accept": "application/json"})
    assert r.headers["content-type"].startswith("application/json")


# --------------------------------------------------------------------------- erreurs


def test_504_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TIMEOUT_LLM", "0.2")
    monkeypatch.setattr(tuteur, "graphe", lambda: FauxGraphe(attente=1.0))
    r = client.get(f"/slide/{SLIDE_ID}/explain")
    assert r.status_code == 504 and "n'a pas répondu" in r.json()["detail"]


def test_504_timeout_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TIMEOUT_LLM", "0.2")
    monkeypatch.setattr(tuteur, "graphe", lambda: FauxGraphe(attente=1.0))
    evs = _evenements(client.post("/ask?stream=1", json=QUESTION).text)
    erreur = next(json.loads(e["data"]) for e in evs if e["event"] == "erreur")
    assert erreur["statut"] == 504
    assert "trop de temps" in AgentResponse.model_validate_json(evs[-2]["data"]).reponse


def test_504_sse_pendant_critic_livre_le_brouillon(monkeypatch: pytest.MonkeyPatch) -> None:
    class CriticLent(FauxGraphe):
        def stream(self, state, stream_mode="updates"):  # noqa: ANN001, ANN201
            yield {"router": {"intention": "question"}}
            yield {"qa": {"reponse": "Brouillon [Slide 2]", "sources": [{"course_id": COURSE_ID, "numero": 2}]}}
            time.sleep(1.0)
            yield {"critic": {"corrections": []}}

    monkeypatch.setenv("API_TIMEOUT_LLM", "0.3")
    monkeypatch.setattr(tuteur, "graphe", lambda: CriticLent())
    evs = _evenements(client.post("/ask?stream=1", json=QUESTION).text)
    finale = AgentResponse.model_validate_json(evs[-2]["data"])
    assert any(e["event"] == "erreur" for e in evs)
    assert finale.reponse.startswith("Brouillon [Slide 2]") and "non vérifiée" in finale.reponse
    assert finale.sources[0].numero == 2 and finale.score_fidelite is None


def test_504_timeout_quiz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TIMEOUT_LLM", "0.2")
    monkeypatch.setattr(tuteur, "quiz_verifie", lambda *a: time.sleep(1.0))
    assert client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2}).status_code == 504


def test_timeout_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tuteur.timeout_llm() == tuteur.TIMEOUT_LLM_PAR_DEFAUT == 400.0
    monkeypatch.setenv("API_TIMEOUT_LLM", "abc")
    assert tuteur.timeout_llm() == tuteur.TIMEOUT_LLM_PAR_DEFAUT == 400.0


def test_repli_llm_indisponible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tuteur, "graphe", lambda: FauxGraphe(erreur=llm.LLMIndisponible("absent")))
    rep = AgentResponse.model_validate(client.post("/ask", json=QUESTION).json())
    assert "indisponible" in rep.reponse and "[Slide 2]" in rep.reponse and rep.sources[0].numero == 2


@pytest.mark.parametrize(("methode", "url", "corps"), [
    ("get", "/slide/cours_inconnu__s001/explain", None),
    ("get", f"/slide/{COURSE_ID}__s099/explain", None),
    ("post", "/ask", {**QUESTION, "course_id": "cours_inconnu"}),
    ("post", "/ask", {**QUESTION, "slide_courante": 99}),
])
def test_404(methode: str, url: str, corps: dict | None) -> None:
    r = client.request(methode, url, json=corps)
    assert r.status_code == 404


@pytest.mark.parametrize(("methode", "url", "corps"), [
    ("get", f"/slide/{SLIDE_ID}/explain?niveau=expert", None),
    ("get", "/slide/pas-un-id/explain", None),
    ("post", "/ask", {k: v for k, v in QUESTION.items() if k != "question"}),
    ("post", "/ask", {**QUESTION, "historique": [{"role": "systeme", "contenu": "x"}]}),
])
def test_422(methode: str, url: str, corps: dict | None) -> None:
    assert client.request(methode, url, json=corps).status_code == 422


def test_temps_de_reponse_logge(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="api"):
        r = client.get("/health")
    assert float(r.headers["x-temps-reponse"]) >= 0
    assert any("/health" in m and "200" in m for m in caplog.messages)


# --------------------------------------------------------------------------- CORS


def test_cors_depot_8765() -> None:
    origine = "http://localhost:8765"
    pre = client.options("/upload", headers={"Origin": origine, "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == origine


# --------------------------------------------------------------------------- bouchon / agents.qa (B3)


def test_qa_bouchon_sans_agents_qa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tuteur, "agent_qa_disponible", lambda: False)
    agent, origine = tuteur.construire_agent_qa()
    assert origine == "bouchon" and agent is AGENTS_BOUCHONS["question"]


def test_qa_presence_reflete_le_depot() -> None:
    from importlib.util import find_spec
    assert tuteur.agent_qa_disponible() == (find_spec("agents.qa") is not None)


def _faux_modules(monkeypatch: pytest.MonkeyPatch, *, store_ko: bool = False) -> None:
    class AgentQA:
        def __init__(self, recherche: Any) -> None:
            self.recherche = recherche

        def __call__(self, state: TutorState) -> dict:
            return {"reponse": "qa [Slide 2]"}

    def _store(*a: Any, **k: Any) -> Any:
        if store_ko:
            raise RuntimeError("index absent")
        return ("store", a, k)

    modules = {
        "agents.qa": {"AgentQA": AgentQA},
        "rag.rerank": {"BgeReranker": lambda: "reranker",
                       "RechercheReranked": lambda base, rr: ("reranked", base, rr)},
        "rag.search": {"RechercheHybride": lambda store: ("hybride", store)},
        "rag.store": {"VectorStore": _store, "BgeM3Embedder": lambda: "embedder"},
    }
    for nom, attributs in modules.items():
        monkeypatch.setitem(sys.modules, nom, types.SimpleNamespace(**attributs))
    monkeypatch.setattr(tuteur, "agent_qa_disponible", lambda: True)


def test_qa_branche_quand_agents_qa_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_QA", "auto")
    _faux_modules(monkeypatch)
    agent, origine = tuteur.construire_agent_qa()
    assert origine == "qa"
    nom, hybride, reranker = agent.recherche
    assert (nom, hybride[0], reranker) == ("reranked", "hybride", "reranker")


def test_qa_repli_bouchon_si_construction_echoue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_QA", "auto")
    _faux_modules(monkeypatch, store_ko=True)
    agent, origine = tuteur.construire_agent_qa()
    assert origine == "bouchon"
    etat = TutorState(course_id=COURSE_ID, slide_courante=2, question="Que minimise-t-on ?")
    assert agent(etat)["reponse"] == tuteur.MESSAGE_QA_INDISPONIBLE


@pytest.mark.parametrize(("valeur", "attendu"), [
    (None, "auto"), ("auto", "auto"), ("bouchon", "bouchon"), ("BOUCHON", "bouchon"), ("n'importe", "auto"),
])
def test_api_qa_lecture(monkeypatch: pytest.MonkeyPatch, valeur: str | None, attendu: str) -> None:
    if valeur is None:
        monkeypatch.delenv("API_QA", raising=False)
    else:
        monkeypatch.setenv("API_QA", valeur)
    assert tuteur.mode_qa() == attendu


def test_api_qa_bouchon_force(monkeypatch: pytest.MonkeyPatch) -> None:
    _faux_modules(monkeypatch)  # agents.qa « présent »
    monkeypatch.setenv("API_QA", "bouchon")
    agent, origine = tuteur.construire_agent_qa()
    assert origine == "bouchon" and agent is AGENTS_BOUCHONS["question"]


@pytest.mark.usefixtures("graphe_neuf")
def test_ask_repli_si_qa_leve_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """bge-m3 non téléchargé : OSError au premier appel → /ask 200 avec le message de repli, sans réessai."""
    appels: list[str] = []

    def qa_en_panne(state: TutorState) -> dict:
        appels.append(state.question)
        raise OSError("bge-m3 introuvable dans le cache Hugging Face")

    monkeypatch.setenv("API_CRITIC", "off")
    monkeypatch.setattr(tuteur, "construire_agent_qa", lambda: (tuteur.AgentQAProtege(qa_en_panne), "qa"))
    for _ in range(2):
        r = client.post("/ask", json=QUESTION)
        rep = AgentResponse.model_validate(r.json())
        assert r.status_code == 200 and rep.agent == "qa"
        assert rep.reponse == tuteur.MESSAGE_QA_INDISPONIBLE and rep.sources[0].numero == 2
    assert appels == [QUESTION["question"]]  # indisponibilité mémorisée après le premier échec
