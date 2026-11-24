"""Tests de la révision espacée (A6) : SM-2, SQLite temporaire, export Anki, routes. Sans LLM."""

from __future__ import annotations

import io
import json
import socket
import sqlite3
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agents import llm
from agents import srs
from agents.srs import EtatCarte, revoir
from api.main import app
from api.models import Flashcard
from schemas.models import Source

COURSE_ID = "ml_regression_lineaire_fr"
JOUR = date(2026, 1, 1)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Base SQLite temporaire, LLM interdit, aucune connexion hors boucle locale."""
    db = tmp_path / "srs.db"
    monkeypatch.setenv("SRS_DB_PATH", str(db))

    def _pas_de_llm(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("le LLM ne doit pas être appelé par A6")

    monkeypatch.setattr(llm, "generer_structure", _pas_de_llm)
    connect = socket.socket.connect

    def _local_seulement(sock: socket.socket, adresse: Any, *args: Any) -> Any:
        hote = adresse[0] if isinstance(adresse, tuple) else adresse
        if hote not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"appel réseau inattendu vers {adresse!r}")
        return connect(sock, adresse, *args)

    monkeypatch.setattr(socket.socket, "connect", _local_seulement)
    return db


def _cartes(n: int = 3, course_id: str = COURSE_ID) -> list[Flashcard]:
    return [
        Flashcard(recto=f"Notion {i}", verso=f"Définition {i} <b>&</b>",
                  source=Source(course_id=course_id, numero=i, extrait=f"extrait {i}"))
        for i in range(1, n + 1)
    ]


# --------------------------------------------------------------------------- SM-2


def test_sm2_q5_repete() -> None:
    etat, vus = EtatCarte(), []
    for _ in range(5):
        etat = revoir(etat, 5, JOUR)
        vus.append((etat.repetitions, etat.intervalle, etat.facilite))
    assert vus == [(1, 1, 2.6), (2, 6, 2.7), (3, 16, 2.8), (4, 45, 2.9), (5, 131, 3.0)]
    assert etat.prochaine_revision == JOUR + timedelta(days=131)


def test_sm2_q3_baisse_facilite() -> None:
    etat = revoir(EtatCarte(), 3, JOUR)
    assert (etat.repetitions, etat.intervalle, etat.facilite) == (1, 1, 2.36)
    etat = revoir(etat, 3, JOUR)
    assert (etat.repetitions, etat.intervalle, etat.facilite) == (2, 6, 2.22)
    etat = revoir(etat, 3, JOUR)
    assert (etat.repetitions, etat.intervalle) == (3, 13)  # round(6 * 2.22)
    assert etat.facilite == pytest.approx(2.08)


def test_sm2_q4_garde_facilite() -> None:
    assert revoir(EtatCarte(), 4, JOUR).facilite == 2.5


@pytest.mark.parametrize("qualite, facilite", [(0, 1.7), (1, 1.96), (2, 2.18)])
def test_sm2_echec_remet_a_zero(qualite: int, facilite: float) -> None:
    avance = EtatCarte(repetitions=4, intervalle=45, facilite=2.5)
    etat = revoir(avance, qualite, JOUR)
    assert (etat.repetitions, etat.intervalle) == (0, 1)
    assert etat.facilite == pytest.approx(facilite)
    assert etat.prochaine_revision == JOUR + timedelta(days=1)
    # Après un échec, la séquence repart de 1 puis 6.
    etat = revoir(etat, 5, JOUR)
    assert (etat.repetitions, etat.intervalle) == (1, 1)
    assert revoir(etat, 5, JOUR).intervalle == 6


def test_sm2_facilite_jamais_sous_1_3() -> None:
    etat = EtatCarte()
    for qualite in [0] * 10 + [3] * 10:
        etat = revoir(etat, qualite, JOUR)
        assert etat.facilite >= 1.3
    assert etat.facilite == 1.3


@pytest.mark.parametrize("qualite", [-1, 6, 2.5, True, "4"])
def test_sm2_qualite_invalide(qualite: Any) -> None:
    with pytest.raises(ValueError):
        revoir(EtatCarte(), qualite, JOUR)


# --------------------------------------------------------------------------- stockage


def test_chemin_db_par_env(_isoler: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert srs.chemin_db() == _isoler
    monkeypatch.delenv("SRS_DB_PATH")
    assert srs.chemin_db() == srs.RACINE / "data" / "srs.db"


def test_ajouter_et_cartes_dues(_isoler: Path) -> None:
    cartes = srs.ajouter_cartes("alice", _cartes(3), JOUR)
    assert [c.recto for c in cartes] == ["Notion 1", "Notion 2", "Notion 3"]
    assert all(c.course_id == COURSE_ID and c.user == "alice" for c in cartes)
    assert cartes[0].source.extrait == "extrait 1"
    assert cartes[0].etat.model_dump() == {
        "repetitions": 0, "intervalle": 0, "facilite": 2.5, "prochaine_revision": JOUR}
    assert _isoler.exists()

    # Pas de doublon, et les cartes d'un autre utilisateur sont séparées.
    assert [c.id for c in srs.ajouter_cartes("alice", _cartes(3), JOUR)] == [c.id for c in cartes]
    srs.ajouter_cartes("bob", _cartes(1), JOUR)
    assert len(srs.cartes_a_reviser("alice", JOUR)) == 3
    assert len(srs.cartes_a_reviser("bob", JOUR)) == 1
    assert srs.cartes_a_reviser("alice", JOUR - timedelta(days=1)) == []
    assert srs.cartes_a_reviser("inconnu", JOUR) == []


def test_enregistrer_revision(_isoler: Path) -> None:
    c1, c2, c3 = srs.ajouter_cartes("alice", _cartes(3), JOUR)
    apres = srs.enregistrer_revision("alice", c1.id, 5, JOUR)
    assert apres.etat.repetitions == 1 and apres.etat.facilite == 2.6
    assert apres.etat.prochaine_revision == JOUR + timedelta(days=1)
    srs.enregistrer_revision("alice", c2.id, 1, JOUR)

    assert {c.id for c in srs.cartes_a_reviser("alice", JOUR)} == {c3.id}
    assert len(srs.cartes_a_reviser("alice", JOUR + timedelta(days=1))) == 3
    apres = srs.enregistrer_revision("alice", c1.id, 5, JOUR + timedelta(days=1))
    assert apres.etat.intervalle == 6

    with sqlite3.connect(_isoler) as conn:
        assert conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 3
    conn.close()

    with pytest.raises(KeyError):
        srs.enregistrer_revision("bob", c1.id, 5, JOUR)  # carte d'un autre utilisateur
    with pytest.raises(KeyError):
        srs.enregistrer_revision("alice", 9999, 5, JOUR)


def test_base_explicite(tmp_path: Path) -> None:
    autre = tmp_path / "sous" / "dossier" / "autre.db"
    srs.ajouter_cartes("alice", _cartes(2), JOUR, db=autre)
    assert len(srs.cartes_a_reviser("alice", JOUR, db=autre)) == 2
    assert srs.cartes_a_reviser("alice", JOUR) == []  # la base SRS_DB_PATH reste vide


# --------------------------------------------------------------------------- export Anki


def _notes_apkg(contenu: bytes, dossier: Path) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        assert "collection.anki2" in archive.namelist()
        archive.extract("collection.anki2", dossier)
    with sqlite3.connect(dossier / "collection.anki2") as conn:
        notes = conn.execute("SELECT guid, flds FROM notes ORDER BY id").fetchall()
        (decks,) = conn.execute("SELECT decks FROM col").fetchone()
    conn.close()
    return notes, json.loads(decks)


def test_id_stable() -> None:
    assert srs.id_stable(COURSE_ID, "deck") == srs.id_stable(COURSE_ID, "deck")
    assert srs.id_stable(COURSE_ID, "deck") != srs.id_stable(COURSE_ID, "modele")
    assert srs.id_stable(COURSE_ID, "deck") != srs.id_stable("autre_cours", "deck")
    assert 1 << 30 <= srs.id_stable(COURSE_ID, "deck") < 1 << 31
    deck = srs.construire_deck(COURSE_ID, _cartes(1))
    assert deck.deck_id == srs.id_stable(COURSE_ID, "deck")
    assert deck.notes[0].model.model_id == srs.id_stable(COURSE_ID, "modele")


def test_export_apkg(tmp_path: Path) -> None:
    srs.ajouter_cartes("alice", _cartes(3), JOUR)
    srs.ajouter_cartes("alice", _cartes(2, course_id="autre_cours"), JOUR)
    destination = tmp_path / "deck.apkg"
    contenu = srs.exporter_apkg("alice", COURSE_ID, destination)
    assert contenu and destination.read_bytes() == contenu

    notes, decks = _notes_apkg(contenu, tmp_path)
    assert len(notes) == 3  # seulement le cours demandé
    assert notes[0][1].split("\x1f")[:2] == ["Notion 1", "Définition 1 &lt;b&gt;&amp;&lt;/b&gt;"]
    assert str(srs.id_stable(COURSE_ID, "deck")) in decks

    # Même contenu, mêmes guid : réimporter met à jour le deck au lieu de dupliquer.
    notes_bis, _ = _notes_apkg(srs.exporter_apkg("alice", COURSE_ID), tmp_path / "bis")
    assert [g for g, _ in notes_bis] == [g for g, _ in notes]

    with pytest.raises(LookupError):
        srs.exporter_apkg("bob", COURSE_ID)


# --------------------------------------------------------------------------- routes API


def _payload(user: str = "alice", n: int = 2) -> dict[str, Any]:
    return {"user": user, "flashcards": [c.model_dump() for c in _cartes(n)]}


def test_route_save_et_due() -> None:
    r = client.post("/flashcards/save", json=_payload())
    assert r.status_code == 200, r.text
    cartes = r.json()
    assert [c["recto"] for c in cartes] == ["Notion 1", "Notion 2"]
    assert cartes[0]["etat"]["facilite"] == 2.5

    r = client.get("/flashcards/due", params={"user": "alice"})
    assert r.status_code == 200 and len(r.json()) == 2
    hier = (date.today() - timedelta(days=1)).isoformat()
    assert client.get("/flashcards/due", params={"user": "alice", "date": hier}).json() == []
    assert client.get("/flashcards/due", params={"user": "alice", "course_id": "autre"}).json() == []
    assert client.get("/flashcards/due").status_code == 422


def test_route_save_invalide() -> None:
    assert client.post("/flashcards/save", json={"user": "alice", "flashcards": []}).status_code == 422
    assert client.post("/flashcards/save", json=_payload(user="")).status_code == 422


def test_route_review() -> None:
    (carte, _) = client.post("/flashcards/save", json=_payload()).json()
    r = client.post(f"/flashcards/{carte['id']}/review", json={"user": "alice", "qualite": 5})
    assert r.status_code == 200, r.text
    etat = r.json()["etat"]
    assert (etat["repetitions"], etat["intervalle"], etat["facilite"]) == (1, 1, 2.6)
    assert etat["prochaine_revision"] == (date.today() + timedelta(days=1)).isoformat()
    assert [c["id"] for c in client.get("/flashcards/due", params={"user": "alice"}).json()] == [
        carte["id"] + 1]

    for qualite in (-1, 6):
        r = client.post(f"/flashcards/{carte['id']}/review", json={"user": "alice", "qualite": qualite})
        assert r.status_code == 422
    r = client.post(f"/flashcards/{carte['id']}/review", json={"user": "bob", "qualite": 4})
    assert r.status_code == 404
    assert client.post("/flashcards/9999/review", json={"user": "alice", "qualite": 4}).status_code == 404


def test_route_export(tmp_path: Path) -> None:
    client.post("/flashcards/save", json=_payload(n=3))
    r = client.get("/flashcards/export", params={"course_id": COURSE_ID, "user": "alice"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/apkg"
    assert f'filename="{COURSE_ID}.apkg"' in r.headers["content-disposition"]
    notes, _ = _notes_apkg(r.content, tmp_path)
    assert len(notes) == 3

    assert client.get("/flashcards/export",
                      params={"course_id": COURSE_ID, "user": "bob"}).status_code == 404
    assert client.get("/flashcards/export",
                      params={"course_id": "Pas Valide", "user": "alice"}).status_code == 422
