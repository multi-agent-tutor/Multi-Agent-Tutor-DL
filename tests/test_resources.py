"""Tests de l'agent Resources (A4) : catalogue local, backend LLM fake, aucun réseau."""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest

from agents import llm
from agents import resources as res
from agents.graph import construire_graphe, executer
from api.models import Ressource
from schemas import Slide, TutorState

RACINE = Path(__file__).resolve().parent.parent
EXEMPLE = RACINE / "schemas" / "exemples" / "exemple_cours.json"
COURSE_ID = "ml_regression_lineaire_fr"


# --------------------------------------------------------------------------- utilitaires


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend LLM fake et toute connexion hors boucle locale interdite.

    (asyncio crée une paire de sockets sur 127.0.0.1 sous Windows : on la laisse passer.)
    """
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    connect = socket.socket.connect

    def _local_seulement(sock: socket.socket, adresse: Any, *args: Any) -> Any:
        hote = adresse[0] if isinstance(adresse, tuple) else adresse
        if hote not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"appel réseau inattendu vers {adresse!r}")
        return connect(sock, adresse, *args)

    monkeypatch.setattr(socket.socket, "connect", _local_seulement)


def _slide(titre: str = "Descente de gradient stochastique", concepts: list[str] | None = None) -> Slide:
    base = json.loads(EXEMPLE.read_text(encoding="utf-8"))["slides"][1]
    base.update(titre=titre, concepts=["SGD", "taux d'apprentissage"] if concepts is None else concepts)
    return Slide.model_validate(base)


def _entree(i: int, concepts: list[str], course_id: str = "", type_: str = "article",
            langue: str = "fr") -> res.EntreeCatalogue:
    return res.EntreeCatalogue(titre=f"R{i}", url=f"https://exemple.org/{i}", type=type_,
                               langue=langue, concepts=concepts, course_id=course_id)


def _state(**kwargs: Any) -> TutorState:
    return TutorState(course_id=kwargs.pop("course_id", COURSE_ID), slide_courante=2, **kwargs)


# --------------------------------------------------------------------------- slide et normalisation


def test_charger_slide_depuis_processed(tmp_path: Path) -> None:
    (tmp_path / COURSE_ID).mkdir()
    shutil.copy(EXEMPLE, tmp_path / COURSE_ID / "course.json")
    slide = res.charger_slide(COURSE_ID, 2, dossier=tmp_path)
    assert slide is not None and slide.titre == "Fonction de coût"
    assert res.charger_slide(COURSE_ID, 9, dossier=tmp_path) is None
    assert res.charger_slide("inconnu", 1, dossier=tmp_path) is None


def test_normaliser_et_mots_cles() -> None:
    assert res.normaliser("Réseaux de Neurones (CNN) !") == "reseaux de neurones cnn"
    assert res.mots_cles("Les réseaux de neurones") == {"reseau", "neurone"}


# --------------------------------------------------------------------------- catalogue


def test_catalogue_reel_valide() -> None:
    catalogue = res.charger_catalogue()
    assert len(catalogue) >= 15
    assert len({e.course_id for e in catalogue}) >= 3
    assert len({e.url for e in catalogue}) == len(catalogue)
    assert all(e.url.startswith("https://") and e.concepts for e in catalogue)


def test_catalogue_absent(tmp_path: Path) -> None:
    assert res.charger_catalogue(tmp_path / "absent.json") == []


def test_selection_score_et_bornes() -> None:
    catalogue = [
        _entree(0, ["clustering"]),
        _entree(1, ["SGD"]),
        _entree(2, ["descente de gradient", "SGD", "taux d'apprentissage"]),
        *(_entree(i, ["gradient"]) for i in range(3, 10)),
    ]
    choix = res.selectionner(_slide(), catalogue=catalogue)
    assert len(choix) == res.MAX_RESSOURCES
    assert choix[0][0].titre == "R2" and choix[1][0].titre == "R1"
    assert "R0" not in [e.titre for e, _ in choix]
    assert choix[0][1] == ["descente de gradient", "SGD", "taux d'apprentissage"]


def test_selection_sans_accents_et_bonus_cours() -> None:
    catalogue = [_entree(0, ["fonction de cout"]), _entree(1, ["Fonction de COÛT"], course_id=COURSE_ID)]
    choix = res.selectionner(_slide("Fonction de coût", []), course_id=COURSE_ID, catalogue=catalogue)
    assert [e.titre for e, _ in choix] == ["R1", "R0"]


def test_slide_exemple_trouve_le_catalogue_reel() -> None:
    choix = res.selectionner(_slide("Descente de gradient stochastique", ["SGD", "mini-lot"]))
    assert choix and choix[0][0].course_id == "ml_gradient_stochastique_esprit_fr"


# --------------------------------------------------------------------------- justifications


def test_justifier_un_seul_appel_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[dict[str, Any]] = []

    def faux_llm(system: str, prompt: str, schema: type, **kwargs: Any) -> Any:
        appels.append({"prompt": prompt, **kwargs})
        return schema(justifications=["Explique la SGD.", ""])

    monkeypatch.setattr(llm, "generer_structure", faux_llm)
    choix = [(_entree(i, ["SGD"]), ["SGD"]) for i in range(3)]
    assert res.justifier(choix, _slide(), "q") == ["Explique la SGD.", "Couvre : SGD.", "Couvre : SGD."]
    assert len(appels) == 1 and "R2" in appels[0]["prompt"]
    assert appels[0]["max_tokens"] <= 32 + res.MAX_TOKENS_PAR_RESSOURCE * 3


def test_justifier_repli_si_llm_indisponible(monkeypatch: pytest.MonkeyPatch) -> None:
    def en_panne(*_: Any, **__: Any) -> Any:
        raise llm.LLMIndisponible("modèle absent")

    monkeypatch.setattr(llm, "generer_structure", en_panne)
    choix = [(_entree(0, ["SGD", "momentum"]), ["SGD", "momentum"])]
    assert res.justifier(choix, _slide(), "q") == ["Couvre : SGD, momentum."]


def test_justifier_backend_fake_complete_par_modele() -> None:
    # Le backend fake renvoie une liste vide : chaque ressource reçoit la phrase modèle.
    assert res.justifier([(_entree(0, ["SGD"]), ["SGD"])], _slide(), "q") == ["Couvre : SGD."]


# --------------------------------------------------------------------------- pipeline


def test_chercher_ressources_catalogue() -> None:
    catalogue = [_entree(i, ["SGD"], type_="video" if i % 2 else "article") for i in range(4)]
    ressources = res.chercher_ressources(_state(), charger=lambda c, n: _slide(), catalogue=catalogue)
    assert [r.titre for r in ressources] == ["R0", "R1", "R2", "R3"]
    assert all(isinstance(r, Ressource) and r.justification == "Couvre : SGD." for r in ressources)


def test_chercher_ressources_complete_jusqu_au_minimum() -> None:
    ressources = res.chercher_ressources(_state(), charger=lambda c, n: _slide(),
                                         catalogue=[_entree(0, ["SGD"])])
    assert len(ressources) == res.MIN_RESSOURCES
    assert [r.type for r in ressources] == ["article", "recherche", "recherche"]


def test_aucune_correspondance_liens_de_recherche() -> None:
    ressources = res.chercher_ressources(
        _state(langue_reponse="en"), charger=lambda c, n: _slide("Théorie des graphes", ["arbre"]),
        catalogue=[_entree(0, ["SGD"])],
    )
    assert {r.type for r in ressources} == {"recherche"}
    urls = [r.url for r in ressources]
    assert urls[0].startswith("https://en.wikipedia.org/w/index.php?search=Th%C3%A9orie+des+graphes")
    assert urls[1].startswith("https://www.youtube.com/results?search_query=Th%C3%A9orie+des+graphes")


def test_sans_slide_utilise_la_question() -> None:
    ressources = res.chercher_ressources(_state(question="c'est quoi la SGD ?"),
                                         charger=lambda c, n: None, catalogue=[_entree(0, ["SGD"])])
    assert ressources[0].titre == "R0"
    assert res.chercher_ressources(_state(), charger=lambda c, n: None, catalogue=[]) == []


# --------------------------------------------------------------------------- agent, graphe, API


@pytest.fixture
def slide_mockee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(res, "charger_slide", lambda course_id, numero: _slide())


def test_resources_agent_signature_bouchon(slide_mockee: None) -> None:
    sortie = res.resources_agent(_state(question="Des vidéos ?"))
    assert set(sortie) == {"reponse", "sources", "historique"}
    assert "[Slide 2]" in sortie["reponse"] and "Couvre :" in sortie["reponse"]
    assert sortie["sources"][0].numero == 2
    assert [m.role for m in sortie["historique"]] == ["utilisateur", "tuteur"]


def test_resources_agent_dans_le_graphe(slide_mockee: None) -> None:
    graphe = construire_graphe({"ressources": res.resources_agent})
    final = executer(_state(question="Donne-moi des ressources"), graphe)
    assert final.intention == "ressources" and "Pour aller plus loin" in final.reponse


def test_api_resources_branchee_sur_l_agent() -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    r = TestClient(app).get("/resources", params={"slide_id": f"{COURSE_ID}__s002"})
    assert r.status_code == 200
    ressources = [Ressource.model_validate(x) for x in r.json()]
    assert len(ressources) >= res.MIN_RESSOURCES and all(x.justification for x in ressources)
