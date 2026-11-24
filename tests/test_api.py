"""Tests de l'API (A1) : une assertion par route (LLM fake, voir aussi test_api_graphe.py)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import agents.explainer as ex
from api import graphe as tuteur
from api.main import app
from api.models import QCM, Ressource
from schemas import AgentResponse, Course

client = TestClient(app)

COURSE_ID = "ml_regression_lineaire_fr"
SLIDE_ID = f"{COURSE_ID}__s002"


@pytest.fixture(autouse=True)
def _llm_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """/explain et /ask passent par le graphe (A3) : jamais le vrai modèle dans ces tests."""
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    monkeypatch.setattr(ex, "_prerequis_h3", lambda: None)
    monkeypatch.setenv("API_QA", "bouchon")  # jamais bge-m3 / reranker / index Qdrant ici
    tuteur.graphe.cache_clear()


def test_upload() -> None:
    r = client.post(
        "/upload",
        files={"fichier": ("cours.pdf", b"%PDF-1.4 factice", "application/pdf")},
    )
    assert r.status_code == 200 and Course.model_validate(r.json()).id == COURSE_ID


def test_get_course() -> None:
    r = client.get(f"/course/{COURSE_ID}")
    assert r.status_code == 200 and Course.model_validate(r.json()).nombre_slides == 2


def test_explain() -> None:
    r = client.get(f"/slide/{SLIDE_ID}/explain", params={"niveau": "debutant"})
    assert r.status_code == 200 and AgentResponse.model_validate(r.json()).agent == "explainer"


def test_ask() -> None:
    r = client.post(
        "/ask",
        json={
            "course_id": COURSE_ID,
            "slide_courante": 2,
            "question": "Que minimise-t-on ?",
            "niveau": "intermediaire",
            "langue": "fr",
        },
    )
    rep = AgentResponse.model_validate(r.json())
    assert r.status_code == 200 and "[Slide 2]" in rep.reponse and rep.sources[0].numero == 2


def test_quiz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps({"qcm": [{
        "question": "Que minimise-t-on ?", "choix": ["MSE", "MAE", "R2", "AUC"], "bonne_reponse": 0,
        "explication": "MSE.", "niveau_bloom": "memoriser", "slide": 2}]}))
    r = client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200 and len([QCM.model_validate(q) for q in r.json()]) > 0


def test_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    r = client.get("/resources", params={"slide_id": SLIDE_ID})
    assert r.status_code == 200 and len([Ressource.model_validate(x) for x in r.json()]) > 0


def test_cors_frontend_vite() -> None:
    """Le frontend Vite (A5, port 5173) peut appeler l'API et lire X-Quiz-Message."""
    origine = "http://localhost:5173"
    pre = client.options(
        "/ask",
        headers={"Origin": origine, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    r = client.get("/health", headers={"Origin": origine})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == origine
    assert "x-quiz-message" in r.headers["access-control-expose-headers"].lower()
