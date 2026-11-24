"""Tests du Critic (O3) et de la boucle de correction : LLM fake, aucun réseau."""

from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from agents import critic as cr
from agents import explainer as ex
from agents import llm
from agents import quiz as qz
from agents.graph import construire_graphe, executer
from api.models import QCM
from schemas import Message, Source, TutorState

COURSE_ID = "ml_regression_lineaire_fr"  # cours d'exemple : slide 2 = fonction de coût (MSE)


def _src(n: int = 2, extrait: str = "") -> Source:
    return Source(course_id=COURSE_ID, numero=n, extrait=extrait)


def _jugement(*verdicts: bool) -> dict[str, Any]:
    return {"affirmations": [{"affirmation": f"affirmation {i}", "appuyee": v}
                             for i, v in enumerate(verdicts, 1)]}


def _imposer(monkeypatch: pytest.MonkeyPatch, reponse: dict[str, Any]) -> None:
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps(reponse, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.delenv("LLM_FAKE_REPONSE", raising=False)
    monkeypatch.setattr(qz, "_recherche_rag", lambda: None)
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


# --------------------------------------------------------------------------- sources et citations


def test_texte_sources_lit_la_slide_complete() -> None:
    textes = cr.texte_sources([_src(2)])
    assert "erreur quadratique" in textes[2].lower()


def test_texte_sources_repli_sur_l_extrait() -> None:
    textes = cr.texte_sources([Source(course_id="cours_inconnu", numero=4, extrait="extrait seul")])
    assert textes == {4: "extrait seul"}


def test_citations_orphelines() -> None:
    assert cr.citations_orphelines("A [Slide 2]. B [Slide 7]. C [Slide 9]", [_src(2)]) == [7, 9]


def test_affirmations_sans_rubriques_ni_citations() -> None:
    texte = "**Idée clé** : La régression prédit une valeur continue. [Slide 1]\n\n**À retenir**\n- Ok."
    assert cr.affirmations(texte) == ["La régression prédit une valeur continue."]


# --------------------------------------------------------------------------- évaluation


def test_score_llm_part_des_affirmations_appuyees(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, _jugement(True, True, True, False))
    ev = cr.evaluer("La MSE est la fonction de coût. [Slide 2]", [_src(2)])
    assert ev is not None and ev.via_llm
    assert ev.score == 0.75 and ev.non_appuyees == ["affirmation 4"]
    assert ev.acceptee()


def test_citation_orpheline_compte_comme_non_appuyee(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, _jugement(True))
    ev = cr.evaluer("La MSE est la fonction de coût. [Slide 8]", [_src(2)])
    assert ev is not None and ev.score == 0.5
    assert "[Slide 8]" in ev.non_appuyees[-1]


def test_refus_et_cas_non_verifiables() -> None:
    ev = cr.evaluer(cr.REPONSE_HORS_COURS, [_src(2)])
    assert ev is not None and ev.score == 1.0
    assert cr.evaluer("", [_src(2)]) is None
    assert cr.evaluer("Une réponse.", []) is None


def test_repli_lexical_sans_llm(sans_llm: None) -> None:
    fidele = "La fonction de coût mesure l'erreur quadratique moyenne. [Slide 2]"
    invente = "Les transformeurs utilisent l'attention multi-têtes pour traduire. [Slide 2]"
    ev = cr.evaluer(f"{fidele}\n{invente}", [_src(2)])
    assert ev is not None and not ev.via_llm
    assert ev.score == 0.5
    assert ev.non_appuyees == ["Les transformeurs utilisent l'attention multi-têtes pour traduire."]


# --------------------------------------------------------------------------- nœud critic


def _etat(**kw: Any) -> TutorState:
    base = dict(course_id=COURSE_ID, slide_courante=2, intention="expliquer", question="Explique",
                reponse="Une réponse. [Slide 2]", sources=[_src(2)],
                historique=[Message(role="utilisateur", contenu="Explique"),
                            Message(role="tuteur", contenu="Une réponse. [Slide 2]")])
    return TutorState(**{**base, **kw})


def test_critiquer_accepte(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, _jugement(True, True))
    sortie = cr.critiquer(_etat())
    assert sortie == {"score_fidelite": 1.0, "corrections": []}


def test_critiquer_renvoie_avec_corrections(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, _jugement(True, False, False))
    sortie = cr.critiquer(_etat())
    assert sortie["corrections"] == ["affirmation 2", "affirmation 3"]
    assert sortie["iterations_critic"] == 1
    assert sortie["historique"] == []  # le dernier échange sera rejoué par l'agent


def test_critiquer_abandonne_apres_deux_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, _jugement(False))
    sortie = cr.critiquer(_etat(iterations_critic=cr.MAX_ITERATIONS))
    assert sortie["corrections"] == []
    assert "iterations_critic" not in sortie
    assert sortie["reponse"].endswith("Vérifie-les sur les slides citées.")
    assert sortie["historique"][-1].contenu == sortie["reponse"]


# --------------------------------------------------------------------------- boucle dans le graphe


EXPLICATION = {
    "idee_cle": "La fonction de coût mesure l'erreur.",
    "explication": "On minimise l'erreur quadratique moyenne.",
    "exemple": "",
    "lien_precedente": "",
    "a_retenir": ["MSE"],
}


def _llm_scenario(monkeypatch: pytest.MonkeyPatch, verdicts: list[list[bool]]) -> list[str]:
    """Explainer → réponse fixe ; Critic → verdicts successifs. Renvoie les prompts de l'Explainer."""
    prompts: list[str] = []
    restants = list(verdicts)

    def _faux(system: str, prompt: str, schema: Any, **_: Any) -> Any:
        if schema is ex.Explication:
            prompts.append(prompt)
            return schema.model_validate(EXPLICATION)
        return schema.model_validate(_jugement(*restants.pop(0)))

    monkeypatch.setattr(llm, "generer_structure", _faux)
    return prompts


def _graphe() -> Any:
    return construire_graphe({"expliquer": ex.explainer_agent}, critic=cr.critic_agent)


def test_boucle_corrige_puis_accepte(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = _llm_scenario(monkeypatch, [[True, False], [True, True]])
    final = executer(TutorState(course_id=COURSE_ID, slide_courante=2, question="Explique cette slide"),
                     _graphe())
    assert len(prompts) == 2
    assert "Corrections du relecteur" not in prompts[0]
    assert "- affirmation 2" in prompts[1]
    assert final.score_fidelite == 1.0 and final.corrections == []
    assert final.iterations_critic == 1
    assert [m.role for m in final.historique] == ["utilisateur", "tuteur"]
    assert "⚠" not in final.reponse


def test_boucle_bornee_a_deux_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = _llm_scenario(monkeypatch, [[False]] * 3)
    final = executer(TutorState(course_id=COURSE_ID, slide_courante=2, question="Explique cette slide"),
                     _graphe())
    assert len(prompts) == 3  # réponse initiale + 2 corrections
    assert final.iterations_critic == 2
    assert final.score_fidelite == 0.0
    assert "⚠" in final.reponse
    assert [m.role for m in final.historique] == ["utilisateur", "tuteur"]


def test_quiz_et_ressources_ne_passent_pas_par_le_critic(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[str] = []
    monkeypatch.setattr(cr, "critic_agent", lambda s: appels.append("critic") or {})
    graphe = construire_graphe(critic=cr.critic_agent)
    executer(TutorState(course_id=COURSE_ID, slide_courante=2, question="fais-moi un quiz"), graphe)
    executer(TutorState(course_id=COURSE_ID, slide_courante=2, question="une vidéo youtube ?"), graphe)
    assert appels == []


def test_etat_du_critic_remis_a_zero_a_chaque_tour(monkeypatch: pytest.MonkeyPatch) -> None:
    _llm_scenario(monkeypatch, [[True]])
    etat = TutorState(course_id=COURSE_ID, slide_courante=2, question="Explique cette slide",
                      iterations_critic=2, corrections=["vieux"], score_fidelite=0.1)
    final = executer(etat, _graphe())
    assert final.iterations_critic == 0 and final.score_fidelite == 1.0


# --------------------------------------------------------------------------- quiz


def _qcm(choix: list[str] | None = None, bonne: int = 0) -> QCM:
    return QCM(question="Que minimise la régression linéaire ?",
               choix=choix or ["L'erreur quadratique moyenne", "L'erreur absolue maximale",
                               "Le nombre de paramètres", "La variance des entrées"],
               bonne_reponse=bonne, source=_src(2))


def test_structure_qcm() -> None:
    assert cr.problemes_structure(_qcm()) == []
    assert cr.problemes_structure(_qcm(["A", "A", "B", "C"])) == ["la bonne réponse apparaît plusieurs fois"]
    assert cr.problemes_structure(_qcm(["A", "B", "B", "C"])) == ["choix en double"]


def test_verifier_qcm_avec_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _imposer(monkeypatch, {"bonne_reponse_juste": True, "distracteurs_faux": True, "motif": ""})
    assert cr.verifier_qcm(_qcm(), "MSE") == []
    _imposer(monkeypatch, {"bonne_reponse_juste": True, "distracteurs_faux": False,
                           "motif": "B est aussi juste"})
    assert cr.verifier_qcm(_qcm(), "MSE") == ["B est aussi juste"]


def test_verifier_qcm_sans_llm_garde_la_structure(sans_llm: None) -> None:
    assert cr.verifier_qcm(_qcm(), "MSE") == []


def test_quiz_verifie_ecarte_les_qcm_rejetes(monkeypatch: pytest.MonkeyPatch) -> None:
    bon, mauvais = _qcm(), _qcm(["Vrai", "Vrai aussi", "Faux", "Faux 2"]).model_copy(
        update={"question": "Question ambiguë ?"})
    monkeypatch.setattr(qz, "generer_quiz_detaille", lambda *a, **k: qz.ResultatQuiz([bon, mauvais]))
    verdicts = iter([{"bonne_reponse_juste": True, "distracteurs_faux": True, "motif": ""},
                     {"bonne_reponse_juste": True, "distracteurs_faux": False, "motif": "deux bonnes"}])
    monkeypatch.setattr(llm, "generer_structure", lambda *a, **k: cr.VerdictQCM(**next(verdicts)))
    sortie = cr.quiz_verifie_agent(TutorState(course_id=COURSE_ID, slide_courante=2, question="quiz"))
    assert "Que minimise" in sortie["reponse"] and "ambiguë" not in sortie["reponse"]
    assert sortie["score_fidelite"] == 0.5


def test_quiz_verifie_tout_rejete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qz, "generer_quiz_detaille", lambda *a, **k: qz.ResultatQuiz([_qcm()]))
    _imposer(monkeypatch, {"bonne_reponse_juste": False, "distracteurs_faux": True, "motif": "faux"})
    sortie = cr.quiz_verifie_agent(TutorState(course_id=COURSE_ID, slide_courante=2, question="quiz"))
    assert sortie["reponse"] == "Quiz indisponible : aucun QCM n'a passé la vérification du Critic."
    assert sortie["score_fidelite"] == 0.0
