"""Tests de l'agent Quiz (A2) : backend LLM fake, aucun réseau, aucun modèle chargé."""

from __future__ import annotations

import json
import random
import socket
from collections import Counter
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agents import llm
from agents import quiz as qz
from agents.graph import construire_graphe, executer
from api.main import app
from api.models import QCM, Flashcard
from schemas import TutorState

COURSE_ID = "ml_regression_lineaire_fr"
client = TestClient(app)


def _qcm(question: str = "Que minimise la régression linéaire ?",
         choix: list[str] | None = None, bonne: int = 0, slide: int = 2) -> dict[str, Any]:
    return {
        "question": question,
        "choix": choix or ["L'erreur quadratique moyenne", "L'erreur absolue maximale",
                           "Le nombre de paramètres", "La variance des entrées"],
        "bonne_reponse": bonne,
        "explication": "La fonction de coût est l'erreur quadratique moyenne.",
        "niveau_bloom": "comprendre",
        "slide": slide,
    }


def _imposer(monkeypatch: pytest.MonkeyPatch, reponse: dict[str, Any]) -> None:
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps(reponse, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend LLM fake et toute connexion hors boucle locale interdite."""
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    monkeypatch.setattr(qz, "_recherche_rag", lambda: None)  # tester le bouchon local
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


# --------------------------------------------------------------------------- récupération du contenu


def test_recherche_bouchon_lit_le_cours_exemple() -> None:
    hits = qz.recherche(COURSE_ID, "fonction de coût erreur quadratique", 2)
    assert [h.chunk.numero for h in hits] == [2, 1]
    assert "erreur quadratique" in hits[0].chunk.contenu


def test_recherche_utilise_le_rag_s_il_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[tuple[str, str, int]] = []

    def _rag(course_id: str, requete: str, k: int) -> list[Any]:
        appels.append((course_id, requete, k))
        return qz.recherche_locale(course_id, requete, k)

    monkeypatch.setattr(qz, "_recherche_rag", lambda: _rag)
    assert qz.recherche(COURSE_ID, "coût", 1) and appels == [(COURSE_ID, "coût", 1)]


def test_contexte_slide_unique() -> None:
    chunks = qz.contexte(COURSE_ID, 2)
    assert [c.numero for c in chunks] == [2]
    assert qz.contexte("cours_inconnu", 1) == []


def test_prompt_lu_dans_prompts_quiz_md() -> None:
    assert "UNE SEULE bonne réponse" in qz.prompt_systeme("QCM")
    assert "recto" in qz.prompt_systeme("Flashcards")


# --------------------------------------------------------------------------- QCM


def test_generer_quiz_json_valide(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm()]})
    quiz = qz.generer_quiz(COURSE_ID, slide=2, rng=random.Random(0))
    assert len(quiz) == 1
    q = QCM.model_validate(quiz[0].model_dump())
    assert len(q.choix) == 4 and 0 <= q.bonne_reponse <= 3
    assert q.choix[q.bonne_reponse] == "L'erreur quadratique moyenne"
    assert q.source.course_id == COURSE_ID and q.source.numero == 2
    assert q.niveau_bloom == "comprendre"


def test_une_seule_bonne_reponse_et_rejets(monkeypatch: pytest.MonkeyPatch) -> None:
    valide = _qcm()
    doublon_bonne = _qcm("Q2 ?", ["A", "a", "B", "C"], bonne=0)
    doublon_autres = _qcm("Q3 ?", ["A", "B", "B", "C"], bonne=0)
    hors_limites = _qcm("Q4 ?", bonne=4)
    negatif = _qcm("Q5 ?", bonne=-1)
    vide = _qcm("Q6 ?", ["A", " ", "B", "C"])
    question_vide = _qcm("  ")
    en_double = _qcm()
    _imposer(monkeypatch, {"qcm": [valide, doublon_bonne, doublon_autres, hors_limites,
                                   negatif, vide, question_vide, en_double]})
    quiz = qz.generer_quiz(COURSE_ID, slide=2, n=10)
    assert len(quiz) == 1
    q = quiz[0]
    assert len({c.lower() for c in q.choix}) == 4
    assert sum(c == "L'erreur quadratique moyenne" for c in q.choix) == 1


def test_n_tronque_le_lot(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm(f"Question {i} ?") for i in range(5)]})
    assert len(qz.generer_quiz(COURSE_ID, slide=2, n=2)) == 2


def test_niveau_bloom_impose(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm()]})
    assert qz.generer_quiz(COURSE_ID, 2, niveau_bloom="analyser")[0].niveau_bloom == "analyser"


def test_melange_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    choix = ["bonne", "faux 1", "faux 2", "faux 3"]
    _imposer(monkeypatch, {"qcm": [_qcm(f"Question {i} ?", choix) for i in range(10)]})
    rng = random.Random(42)
    positions: Counter[int] = Counter()
    for _ in range(5):
        for q in qz.generer_quiz(COURSE_ID, 2, n=10, rng=rng):
            assert sorted(q.choix) == sorted(choix)
            assert q.choix[q.bonne_reponse] == "bonne"
            positions[q.bonne_reponse] += 1
    assert len(positions) == 4  # la bonne réponse n'est pas toujours en 0


def test_quiz_vide_si_llm_indisponible(sans_llm: None) -> None:
    resultat = qz.generer_quiz_detaille(COURSE_ID, 2)
    assert resultat.qcm == [] and "LLM local" in resultat.message
    assert qz.generer_quiz(COURSE_ID, 2) == []


def test_quiz_vide_si_tous_rejetes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sans LLM_FAKE_REPONSE, le backend fake renvoie 4 choix identiques : QCM rejeté.
    resultat = qz.generer_quiz_detaille(COURSE_ID, 2)
    assert resultat.qcm == [] and "vérification" in resultat.message


# --------------------------------------------------------------------------- nettoyage : préfixes et LaTeX


@pytest.mark.parametrize("brut, attendu", [
    ("A) Une droite", "Une droite"),
    ("B. Une parabole", "Une parabole"),
    ("c) un arbre", "un arbre"),
    ("(D) Un réseau", "Un réseau"),
    ("a: la variance", "la variance"),
    ("  b - le biais  ", "le biais"),
])
def test_nettoyer_retire_prefixe_de_choix(brut: str, attendu: str) -> None:
    assert qz.nettoyer(brut, choix=True) == attendu


@pytest.mark.parametrize("texte", ["A", "Apprentissage supervisé", "B.subtilis", "E) hors A-D", "3 paramètres"])
def test_nettoyer_garde_les_choix_sans_prefixe(texte: str) -> None:
    assert qz.nettoyer(texte, choix=True) == texte


def test_nettoyer_ne_retire_pas_de_prefixe_hors_choix() -> None:
    assert qz.nettoyer("A) ceci est une question ?") == "A) ceci est une question ?"


@pytest.mark.parametrize("brut", [
    "Que minimise la régression linéaire ?\n- A) L'erreur quadratique\n- B) Le biais\n- C) x\n- D) y",
    "Que minimise la régression linéaire ?\nA) L'erreur quadratique\nB) Le biais",
    "Que minimise la régression linéaire ?\n\nChoix :\na. L'erreur quadratique\nb. Le biais",
    "Que minimise la régression linéaire ?\n(a) L'erreur quadratique\n(b) Le biais",
    "Que minimise la régression linéaire ?\n• C: x\n• D: y",
    "Que minimise la régression linéaire ? A) L'erreur quadratique B) Le biais C) x D) y",
])
def test_nettoyer_question_retire_les_choix_recopies(brut: str) -> None:
    assert qz.nettoyer(brut, question=True) == "Que minimise la régression linéaire ?"


@pytest.mark.parametrize("texte", [
    "Que minimise la régression linéaire ?",
    "Soit le modèle suivant.\nQue vaut la pente ?",
    "A) est-elle une question ?",          # première ligne toujours gardée
    "Pourquoi la vitamine A) est-elle citée ?",  # « A) » seul, sans « B) » ensuite
    "Avec a = 2,\nAprès une itération, que vaut $\\theta$ ?",
])
def test_nettoyer_question_garde_l_enonce(texte: str) -> None:
    assert qz.nettoyer(texte, question=True) == texte


def test_qcm_question_sans_choix_recopies(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "Que minimise la régression linéaire ?\n- A) L'erreur quadratique moyenne\n- B) Le biais"
    _imposer(monkeypatch, {"qcm": [_qcm(question)]})
    q = qz.generer_quiz(COURSE_ID, slide=2, rng=random.Random(0))[0]
    assert q.question == "Que minimise la régression linéaire ?"
    assert "ne recopie jamais les choix" in qz.prompt_systeme("QCM")


@pytest.mark.parametrize("brut, attendu", [
    (r"J(\theta) = \frac{1}{m} \times \text{Erreur quadratique} moyenne.",
     r"$J(\theta) = \frac{1}{m} \times \text{Erreur quadratique}$ moyenne."),
    (r"Que vaut \theta ?", r"Que vaut $\theta$ ?"),
    (r"Si x_i est grand, h^{(i)} augmente.", r"Si $x_i$ est grand, $h^{(i)}$ augmente."),
    (r"Le modèle y = ax + \beta minimise.", r"Le modèle $y = ax + \beta$ minimise."),
    (r"il a \alpha et \beta", r"il a $\alpha$ et $\beta$"),
    (r"On somme \sum_{i=1}^{m} (h(x^{(i)}) - y^{(i)})^2 sur les données.",
     r"On somme $\sum_{i=1}^{m} (h(x^{(i)}) - y^{(i)})^2$ sur les données."),
])
def test_delimiter_latex_nu(brut: str, attendu: str) -> None:
    assert qz.delimiter_latex(brut) == attendu


@pytest.mark.parametrize("texte", [
    r"Déjà délimité : $\frac{1}{2m} \sum x_i$.",
    r"En bloc : $$J(\theta) = \frac{1}{2m}$$",
    r"Avec \(\theta\) et \[x^2\]",
    "Aucune formule ici, seulement du texte.",
    "Prix : 5 $ seulement",
])
def test_delimiter_latex_laisse_le_reste_intact(texte: str) -> None:
    assert qz.delimiter_latex(texte) == texte


def test_delimiter_latex_mixte_delimite_et_nu() -> None:
    assert qz.delimiter_latex(r"Avec $\alpha$ puis \beta seul.") == r"Avec $\alpha$ puis $\beta$ seul."


def test_nettoyer_ne_delimite_que_sur_demande() -> None:
    # Par défaut (Explainer) : réparation seule ; le quiz et les flashcards passent delimiter=True.
    assert qz.nettoyer(r"La pente \beta_1 est estimée") == r"La pente \beta_1 est estimée"
    assert qz.nettoyer(r"La pente \beta_1 est estimée", delimiter=True) == r"La pente $\beta_1$ est estimée"


def test_qcm_prefixes_retires_et_latex_delimite(monkeypatch: pytest.MonkeyPatch) -> None:
    choix = [r"A) J(\theta) = \frac{1}{2m}", "B) L'erreur absolue", "c) Le nombre de données", "D. Le biais"]
    brut = _qcm(r"Quelle formule définit J(\theta) ?", choix, bonne=0)
    brut["explication"] = r"La fonction de coût vaut \frac{1}{2m} \sum (h(x) - y)^2."
    _imposer(monkeypatch, {"qcm": [brut]})
    q = qz.generer_quiz(COURSE_ID, slide=2, rng=random.Random(0))[0]
    assert q.question == r"Quelle formule définit $J(\theta)$ ?"
    assert sorted(q.choix) == sorted([r"$J(\theta) = \frac{1}{2m}$", "L'erreur absolue",
                                      "Le nombre de données", "Le biais"])
    assert q.choix[q.bonne_reponse] == r"$J(\theta) = \frac{1}{2m}$"
    assert q.explication == r"La fonction de coût vaut $\frac{1}{2m} \sum (h(x) - y)^2$."


def test_qcm_choix_identiques_hors_prefixe_rejete(monkeypatch: pytest.MonkeyPatch) -> None:
    # Les préfixes sont retirés AVANT la vérification : « A) x » et « B) x » sont des doublons.
    _imposer(monkeypatch, {"qcm": [_qcm(choix=["A) Une droite", "B) Une droite", "C) Un arbre", "D) Un cercle"])]})
    resultat = qz.generer_quiz_detaille(COURSE_ID, 2)
    assert resultat.qcm == [] and "vérification" in resultat.message


def test_flashcards_latex_delimite(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"cartes": [
        {"recto": "Fonction de coût J(\\theta)", "verso": "J(\\theta) = \\frac{1}{2m} \\sum_i e_i^2", "slide": 2},
    ]})
    carte = qz.generer_flashcards(COURSE_ID, slide=2)[0]
    assert carte.recto == r"Fonction de coût $J(\theta)$"
    assert carte.verso == r"$J(\theta) = \frac{1}{2m} \sum_i e_i^2$"


def test_prompt_impose_dollars_et_interdit_prefixes() -> None:
    qcm, cartes = qz.prompt_systeme("QCM"), qz.prompt_systeme("Flashcards")
    assert "$...$" in qcm and "$...$" in cartes
    assert "SANS préfixe" in qcm and "« A) »" in qcm
    assert "sans LaTeX" not in qcm and "sans LaTeX" not in cartes


# --------------------------------------------------------------------------- flashcards


def test_generer_flashcards(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"cartes": [
        {"recto": "Que minimise-t-on ?", "verso": "L'erreur quadratique moyenne.", "slide": 2},
        {"recto": "que minimise-t-on ?", "verso": "doublon", "slide": 2},
        {"recto": "Interprétation ?", "verso": "Géométrique : résidus.", "slide": 2},
    ]})
    cartes = qz.generer_flashcards(COURSE_ID, slide=2)
    assert [c.recto for c in cartes] == ["Que minimise-t-on ?", "Interprétation ?"]
    assert all(isinstance(c, Flashcard) and c.source.numero == 2 for c in cartes)


def test_flashcards_repli_sans_llm(sans_llm: None) -> None:
    cartes = qz.generer_flashcards(COURSE_ID, slide=2)
    assert len(cartes) == 1
    assert cartes[0].recto == "Fonction de coût"
    assert cartes[0].verso.startswith("On minimise l'erreur quadratique moyenne.")
    tout = qz.generer_flashcards(COURSE_ID)
    assert {c.recto for c in tout} == {"Régression linéaire", "Fonction de coût"}


# --------------------------------------------------------------------------- agent et graphe


def _state(question: str = "Fais-moi un quiz") -> TutorState:
    return TutorState(course_id=COURSE_ID, slide_courante=2, question=question)


def test_quiz_agent_signature_bouchon(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm()]})
    sortie = qz.quiz_agent(_state())
    assert set(sortie) == {"reponse", "sources", "historique"}
    assert "[Slide 2]" in sortie["reponse"] and "Réponses" in sortie["reponse"]
    assert [s.numero for s in sortie["sources"]] == [2]
    assert [m.role for m in sortie["historique"]] == ["utilisateur", "tuteur"]


def test_quiz_agent_sans_llm_ne_plante_pas(sans_llm: None) -> None:
    sortie = qz.quiz_agent(_state())
    assert "LLM local" in sortie["reponse"] and sortie["sources"][0].numero == 2
    cartes = qz.quiz_agent(_state("Des flashcards stp"))
    assert "Fonction de coût →" in cartes["reponse"]


def test_quiz_agent_dans_le_graphe(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm()]})
    final = executer(_state("Teste moi avec un QCM"), construire_graphe({"quiz": qz.quiz_agent}))
    assert final.intention == "quiz" and "L'erreur quadratique moyenne" in final.reponse


# --------------------------------------------------------------------------- routes


def test_route_quiz(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"qcm": [_qcm()]})
    r = client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200
    quiz = [QCM.model_validate(q) for q in r.json()]
    assert len(quiz) == 1 and quiz[0].choix[quiz[0].bonne_reponse] == "L'erreur quadratique moyenne"


def test_route_quiz_sans_llm(sans_llm: None) -> None:
    r = client.get("/quiz", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200 and r.json() == [] and "X-Quiz-Message" in r.headers


def test_route_quiz_erreurs() -> None:
    assert client.get("/quiz", params={"course_id": "inconnu", "slide": 1}).status_code == 404
    assert client.get("/quiz", params={"course_id": COURSE_ID, "slide": 99}).status_code == 404


def test_route_flashcards(sans_llm: None) -> None:
    r = client.get("/flashcards", params={"course_id": COURSE_ID, "slide": 2})
    assert r.status_code == 200
    cartes = [Flashcard.model_validate(c) for c in r.json()]
    assert [c.recto for c in cartes] == ["Fonction de coût"]
    r = client.get("/flashcards", params={"course_id": COURSE_ID})
    assert r.status_code == 200 and len(r.json()) == 2
    assert client.get("/flashcards", params={"course_id": COURSE_ID, "slide": 99}).status_code == 404
