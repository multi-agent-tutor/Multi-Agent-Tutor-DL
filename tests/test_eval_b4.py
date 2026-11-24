"""Tests B4 : métriques et benchmark de bout en bout, sans modèle (LLM fake, HashEmbedder)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import llm
from eval.metriques import centile, cosinus, fidelite, moyenne, pertinence, precision_contexte
from eval.run_eval import main, selectionner, synthese, Resultat
from eval.schema import REPONSE_HORS_COURS, QuestionEval
from rag.store import HashEmbedder
from schemas.models import Course, Slide

COURS = "bd_bench_fr"


@pytest.fixture(autouse=True)
def _llm_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    for cle in ("LLM_BACKEND", "LLM_FAKE_REPONSE"):
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.setenv("LLM_BACKEND", "fake")
    llm.reinitialiser()


# --------------------------------------------------------------------------- métriques


def test_precision_contexte():
    assert precision_contexte([2, 4, 9], {2}) == 1.0
    assert precision_contexte([4, 2, 9], {2}) == 0.5
    assert precision_contexte([2, 4, 3], {2, 3}) == pytest.approx((1 / 1 + 2 / 3) / 2)
    assert precision_contexte([4, 9], {2}) == 0.0
    assert precision_contexte([4, 9], set()) is None  # hors cours : pas de référence


def test_outils_numeriques():
    assert cosinus([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosinus([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosinus([0, 0], [1, 0]) == 0.0
    assert moyenne([0.5, None, 1.0]) == 0.75 and moyenne([None]) is None
    assert centile([1, 2, 3, 4, 5], 0.5) == 3 and centile([], 0.95) is None


def test_fidelite_et_pertinence_ignorent_les_refus():
    juge = lambda reponse, textes: 0.8  # noqa: E731
    assert fidelite(REPONSE_HORS_COURS, {1: "x"}, juge) is None
    assert fidelite("La clé primaire est unique [Slide 2].", {2: "clé primaire"}, juge) == 0.8
    assert pertinence("Q ?", REPONSE_HORS_COURS, HashEmbedder().encoder) is None


def test_pertinence_questions_generees_et_repli():
    enc = HashEmbedder().encoder
    proche = pertinence("Qu'est-ce qu'une clé primaire ?", "Une clé primaire identifie un n-uplet.", enc,
                        generer=lambda r: ["Qu'est-ce qu'une clé primaire ?"])
    assert proche == pytest.approx(1.0)

    def en_panne(reponse: str) -> list[str]:
        raise llm.LLMIndisponible("absent")

    repli = pertinence("clé primaire", "clé primaire unique", enc, generer=en_panne)
    sans = pertinence("clé primaire", "clé primaire unique", enc, generer=None)
    assert repli == pytest.approx(sans) and 0 < sans < 1


def _q(n: int, type_: str, slides: list[int], course_id: str = COURS) -> QuestionEval:
    return QuestionEval(id=f"{course_id}__q{n:02d}", course_id=course_id, auteur="both", type=type_,
                        langue="fr", question=f"Question numéro {n} ?",
                        reponse_reference=REPONSE_HORS_COURS if type_ == "hors_cours" else "ref",
                        slides=slides)


def test_selectionner_alterne_types_et_cours():
    qs = ([_q(i, "factuelle", [1]) for i in range(1, 5)] + [_q(5, "hors_cours", [])]
          + [_q(i, "factuelle", [1], "bd_autre_fr") for i in range(1, 5)])
    choix = selectionner(qs, 4)
    assert len(choix) == 4
    assert {q.course_id for q in choix} == {COURS, "bd_autre_fr"}
    assert any(q.type == "hors_cours" for q in choix)
    assert selectionner(qs, None) == qs


def test_synthese_refus():
    def r(type_: str, refus: bool) -> Resultat:
        return Resultat("apres", "x", COURS, type_, "q", "", [], [], 1.0, None, None, None, refus)

    s = synthese([r("hors_cours", True), r("hors_cours", False), r("factuelle", True), r("factuelle", False)], "apres")
    assert s.refus_correct == 0.5 and s.faux_refus == 0.5 and s.n == 4


# --------------------------------------------------------------------------- bout en bout


def test_benchmark_bout_en_bout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_FAKE_REPONSE", "La clé primaire identifie chaque n-uplet [Slide 2].")
    llm.reinitialiser()
    slides = [
        Slide(id=f"{COURS}__s001", course_id=COURS, numero=1, titre="Introduction", texte="Plan du cours de bases de données."),
        Slide(id=f"{COURS}__s002", course_id=COURS, numero=2, titre="Clé primaire",
              texte="La clé primaire identifie chaque n-uplet d'une relation."),
        Slide(id=f"{COURS}__s003", course_id=COURS, numero=3, titre="Jointure", texte="La jointure combine deux relations."),
    ]
    cours = Course(id=COURS, titre="BD", fichier_source="bd.pdf", format="pdf", langue="fr", nombre_slides=3, slides=slides)
    (tmp_path / "processed" / COURS).mkdir(parents=True)
    (tmp_path / "processed" / COURS / "course.json").write_text(cours.model_dump_json(), encoding="utf-8")
    questions = [
        {"id": f"{COURS}__q01", "course_id": COURS, "auteur": "both", "type": "factuelle", "langue": "fr",
         "question": "Qu'est-ce qu'une clé primaire ?", "reponse_reference": "Elle identifie un n-uplet.", "slides": [2]},
        {"id": f"{COURS}__q02", "course_id": COURS, "auteur": "both", "type": "comprehension", "langue": "fr",
         "question": "À quoi sert une jointure ?", "reponse_reference": "Combiner deux relations.", "slides": [3]},
        {"id": f"{COURS}__q03", "course_id": COURS, "auteur": "both", "type": "hors_cours", "langue": "fr",
         "question": "Quel temps fera-t-il demain ?", "reponse_reference": REPONSE_HORS_COURS, "slides": []},
        {"id": "absent_cours_fr__q01", "course_id": "absent_cours_fr", "auteur": "both", "type": "factuelle",
         "langue": "fr", "question": "Question sur un cours non ingéré ?", "reponse_reference": "x", "slides": [1]},
    ]
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps({"version": "1.0", "questions": questions}, ensure_ascii=False), encoding="utf-8")
    sortie = tmp_path / "out" / "results.md"

    main(["--factice", "--dataset", str(dataset), "--cours", str(tmp_path / "processed"), "--sortie", str(sortie)])

    rapport = sortie.read_text(encoding="utf-8")
    assert "| Context precision |" in rapport and "| Refus correct (hors cours) |" in rapport
    assert sortie.with_suffix(".svg").read_text(encoding="utf-8").startswith("<svg")
    details = [json.loads(l) for l in (sortie.parent / "results_details.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(details) == 6  # 3 questions évaluables × 2 versions ; le cours absent est ignoré
    apres = {d["id"]: d for d in details if d["version"] == "apres"}
    assert apres[f"{COURS}__q01"]["precision_contexte"] == 1.0  # slide 2 retrouvée en tête
    assert apres[f"{COURS}__q03"]["refus"] is True  # hors cours : refus sans LLM
    assert not any(d["erreur"] for d in details)


def test_sans_cours_ingere(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dataset = tmp_path / "dataset.json"
    q = _q(1, "factuelle", [1]).model_dump()
    dataset.write_text(json.dumps({"version": "1.0", "questions": [q]}), encoding="utf-8")
    main(["--factice", "--dataset", str(dataset), "--cours", str(tmp_path / "vide"), "--sortie", str(tmp_path / "r.md")])
    assert "Aucune question évaluable" in capsys.readouterr().out
