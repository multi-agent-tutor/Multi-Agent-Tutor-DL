"""Tests de l'agent Explainer (O2) : backend LLM fake, aucun réseau, aucun modèle chargé."""

from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from agents import explainer as ex
from agents import llm
from agents.graph import construire_graphe, executer
from schemas import Course, Slide, TutorState
from schemas.models import slide_id

COURSE_ID = "ml_regression_lineaire_fr"  # cours d'exemple (2 slides)
_PREREQUIS_H3_ORIGINAL = ex._prerequis_h3  # la fixture le remplace : garder la vraie recherche de H3
TEST_ID = "dl_test_explainer"


def _slide(n: int, titre: str, texte: str = "", **kw: Any) -> Slide:
    return Slide(id=slide_id(TEST_ID, n), course_id=TEST_ID, numero=n, titre=titre, texte=texte, **kw)


COURS = Course(
    id=TEST_ID, titre="Réseaux de neurones", fichier_source="data/raw/x.pptx", format="pptx",
    langue="fr", nombre_slides=3,
    slides=[
        _slide(1, "Le perceptron", "Un neurone calcule une somme pondérée.", concepts=["perceptron"]),
        _slide(2, "Fonctions d'activation", "ReLU, sigmoïde, tanh.",
               concepts=["fonction d'activation", "ReLU"],
               description_figures=["Courbe de la sigmoïde entre 0 et 1"],
               formules_latex=["\\sigma(x) = 1 / (1 + e^{-x})"]),
        _slide(3, "Rétropropagation", "Calcul du gradient couche par couche.", concepts=["gradient"]),
    ],
)


def _charger(course_id: str) -> Course | None:
    return COURS if course_id == TEST_ID else None


EXPLICATION = {
    "idee_cle": "Une activation rend le réseau non linéaire.",
    "explication": "Sans activation, empiler des couches revient à une seule couche linéaire.",
    "exemple": "ReLU(-2) = 0 et ReLU(3) = 3.",
    "lien_precedente": "Le perceptron produisait une somme pondérée ; l'activation la transforme.",
    "a_retenir": ["ReLU est la plus utilisée", "La sigmoïde sort entre 0 et 1"],
}


def _imposer(monkeypatch: pytest.MonkeyPatch, reponse: dict[str, Any]) -> None:
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps(reponse, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend LLM fake, pas de module H3 et toute connexion hors boucle locale interdite."""
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    monkeypatch.setattr(ex, "_prerequis_h3", lambda: None)
    connect = socket.socket.connect

    def _local_seulement(sock: socket.socket, adresse: Any, *args: Any) -> Any:
        hote = adresse[0] if isinstance(adresse, tuple) else adresse
        if hote not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"appel réseau inattendu vers {adresse!r}")
        return connect(sock, adresse, *args)

    monkeypatch.setattr(socket.socket, "connect", _local_seulement)


@pytest.fixture
def sans_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_: Any, **__: Any) -> Any:
        raise llm.LLMIndisponible("modèle absent (test)")

    monkeypatch.setattr(llm, "generer_structure", _echec)


# --------------------------------------------------------------------------- prompts


@pytest.mark.parametrize("niveau,marque", [
    ("debutant", "débutant"), ("intermediaire", "intermédiaire"), ("avance", "avancé"),
])
def test_prompt_systeme_commun_plus_niveau(niveau: str, marque: str) -> None:
    prompt = ex.prompt_systeme(niveau)  # type: ignore[arg-type]
    assert "UNIQUEMENT sur la slide" in prompt  # section Commun
    assert f"Niveau de l'étudiant : {marque}" in prompt
    assert prompt != ex.PROMPT_SECOURS


def test_les_trois_niveaux_ont_des_prompts_differents() -> None:
    assert len({ex.prompt_systeme(n) for n in ("debutant", "intermediaire", "avance")}) == 3


def test_prompt_contient_slide_voisines_figures_et_prerequis() -> None:
    prompt = ex.construire_prompt(COURS, 2, "fr", ["perceptron"])
    assert "Slide à expliquer — [Slide 2] Fonctions d'activation" in prompt
    assert "Figure : Courbe de la sigmoïde" in prompt
    assert "Formule : \\sigma(x)" in prompt
    assert "Slide précédente — [Slide 1] Le perceptron" in prompt
    assert "Slide suivante — [Slide 3] Rétropropagation" in prompt
    assert "Prérequis déjà vus : perceptron." in prompt
    assert "français" in prompt


def test_prompt_premiere_slide_sans_precedente() -> None:
    prompt = ex.construire_prompt(COURS, 1, "en", [])
    assert "aucune (première slide)" in prompt
    assert "anglais" in prompt
    assert "Prérequis" not in prompt


# --------------------------------------------------------------------------- prérequis (bouchon H3)


def test_prerequis_bouchon_concepts_des_slides_precedentes() -> None:
    assert ex.prerequis(COURS, 3) == ["perceptron", "fonction d'activation", "ReLU"]
    assert ex.prerequis(COURS, 1) == []


def test_prerequis_utilise_h3_et_se_replie_en_cas_d_erreur() -> None:
    assert ex.prerequis(COURS, 2, lambda sid: [f"vu dans {sid}"]) == [f"vu dans {TEST_ID}__s002"]

    def _casse(_: str) -> list[str]:
        raise RuntimeError("H3 pas prêt")

    assert ex.prerequis(COURS, 2, _casse) == ["perceptron"]


def test_prerequis_h3_ids_de_slides_rendus_lisibles() -> None:
    ids = lambda _: [f"{TEST_ID}__s001", f"{TEST_ID}__s002", f"{TEST_ID}__s001", f"{TEST_ID}__s042"]  # noqa: E731
    assert ex.prerequis(COURS, 3, ids) == ["Slide 1 : Le perceptron", "Slide 2 : Fonctions d'activation"]


def test_prerequis_h3_vide_repli_sur_les_concepts() -> None:
    # Carte du cours pas encore calculée : H3 renvoie [], l'Explainer garde un contexte utile.
    assert ex.prerequis(COURS, 3, lambda _: []) == ["perceptron", "fonction d'activation", "ReLU"]


def test_h3_de_ghayth_est_trouve() -> None:
    from ingestion.course_map import get_prerequisites

    assert _PREREQUIS_H3_ORIGINAL() is get_prerequisites


# --------------------------------------------------------------------------- génération


def test_expliquer_slide_avec_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, EXPLICATION)
    r = ex.expliquer_slide(TEST_ID, 2, "debutant", charger=_charger)
    assert r is not None and r.via_llm
    assert r.explication.idee_cle == EXPLICATION["idee_cle"]
    assert [s.numero for s in r.sources] == [2, 1]
    assert r.precedente == 1
    assert r.prerequis == ["perceptron"]


def test_niveau_choisit_prompt_et_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[tuple[str, int]] = []

    def _espion(system: str, prompt: str, schema: Any, *, max_tokens: int) -> Any:
        appels.append((system, max_tokens))
        return schema.model_validate(EXPLICATION)

    monkeypatch.setattr(llm, "generer_structure", _espion)
    for niveau in ("debutant", "avance"):
        ex.expliquer_slide(TEST_ID, 2, niveau, charger=_charger)  # type: ignore[arg-type]
    assert "débutant" in appels[0][0] and "avancé" in appels[1][0]
    assert all(t == ex.TOKENS_PAR_NIVEAU[n] for (_, t), n in zip(appels, ("debutant", "avance")))


def test_pas_de_lien_invente_sur_la_premiere_slide(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, EXPLICATION)
    r = ex.expliquer_slide(TEST_ID, 1, charger=_charger)
    assert r is not None
    assert r.explication.lien_precedente == ""
    assert r.precedente is None
    assert [s.numero for s in r.sources] == [1]


def test_a_retenir_borne_a_trois(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {**EXPLICATION, "a_retenir": ["a", "b", "c", "d", " "]})
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None and r.explication.a_retenir == ["a", "b", "c"]


def test_latex_casse_repare(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {**EXPLICATION, "exemple": "\theta est le paramètre"})
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None and r.explication.exemple == "\\theta est le paramètre"


def test_repli_sans_llm(sans_llm: None) -> None:
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None and not r.via_llm
    e = r.explication
    assert e.idee_cle == "Fonctions d'activation"
    assert "ReLU, sigmoïde, tanh." in e.explication and "Figure : Courbe" in e.explication
    assert e.lien_precedente == "Fait suite à « Le perceptron »."
    assert e.a_retenir == ["fonction d'activation", "ReLU"]


def test_slide_ou_cours_absents() -> None:
    assert ex.expliquer_slide(TEST_ID, 9, charger=_charger) is None
    assert ex.expliquer_slide("cours_inconnu", 1, charger=_charger) is None


# --------------------------------------------------------------------------- mise en forme et agent


def test_formater_ordre_et_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, EXPLICATION)
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None
    texte = ex.formater(r, "fr")
    positions = [texte.index(m) for m in ("Idée clé", EXPLICATION["explication"], "Exemple",
                                          "Lien avec la slide 1", "À retenir")]
    assert positions == sorted(positions)
    assert "[Slide 1]" in texte and texte.count("[Slide 2]") == 4
    assert "modèle local" not in texte


@pytest.mark.parametrize("langue,titre", [("en", "Key idea"), ("ar", "الفكرة الأساسية")])
def test_formater_langue_de_l_interface(monkeypatch: pytest.MonkeyPatch, langue: str, titre: str) -> None:
    _imposer(monkeypatch, EXPLICATION)
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None and titre in ex.formater(r, langue)  # type: ignore[arg-type]


def test_formater_signale_le_repli(sans_llm: None) -> None:
    r = ex.expliquer_slide(TEST_ID, 2, charger=_charger)
    assert r is not None and "le modèle local n'a pas pu répondre" in ex.formater(r)


@pytest.mark.parametrize("question,attendu", [
    ("explique la slide 5", 5), ("Explain slide 12 please", 12), ("diapo n°3 ?", 3),
    ("explique-moi ça", 7), ("", 7),
])
def test_slide_demandee(question: str, attendu: int) -> None:
    assert ex.slide_demandee(question, 7) == attendu


def test_agent_dans_le_graphe_sur_le_cours_exemple(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, EXPLICATION)
    graphe = construire_graphe({"expliquer": ex.explainer_agent})
    etat = TutorState(course_id=COURSE_ID, slide_courante=2, niveau="debutant",
                      question="Explique cette slide")
    final = executer(etat, graphe)
    assert final.intention == "expliquer"
    assert final.reponse.startswith("**Idée clé**")
    assert [s.numero for s in final.sources] == [2, 1]
    assert [m.role for m in final.historique] == ["utilisateur", "tuteur"]


def test_agent_slide_inexistante() -> None:
    etat = TutorState(course_id=COURSE_ID, slide_courante=1, question="explique la slide 40")
    sortie = ex.explainer_agent(etat)
    assert sortie["reponse"] == "La slide 40 n'existe pas dans ce cours."
