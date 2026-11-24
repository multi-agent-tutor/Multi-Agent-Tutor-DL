"""H2 — VLM : sélection des slides, nettoyage LaTeX, cache et repli (backend fake, sans modèle)."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from ingestion import vlm
from ingestion.parse import parse_course
from ingestion.vlm import AnalyseVisuelle, enrich_with_vlm, nettoyer_latex, slide_visuelle
from schemas import Slide


@pytest.fixture
def cours(tmp_path: Path):
    doc = pymupdf.open()
    textes = [
        "Introduction au cours de statistique et plan de la séance",
        "La variance vaut s^2 = E[(X - m)^2] et f_{i} = 0",  # formules → visuelle
        "Conclusion et références bibliographiques du chapitre",
    ]
    for texte in textes:
        page = doc.new_page(width=400, height=300)
        page.insert_text((20, 40), "Titre", fontsize=20)
        page.insert_text((20, 100), texte, fontsize=11)
    chemin = tmp_path / "maths_stats_test_fr.pdf"
    doc.save(chemin)
    sortie = tmp_path / "out"
    return parse_course(chemin, dossier_sortie=sortie, ocr=False), sortie


@pytest.fixture(autouse=True)
def backend_fake(monkeypatch):
    monkeypatch.setenv("VLM_BACKEND", "fake")
    monkeypatch.delenv("VLM_FAKE_REPONSE", raising=False)


def test_nettoyer_latex() -> None:
    assert nettoyer_latex("$$ E = mc^2 $$") == "E = mc^2"
    assert nettoyer_latex("\\[ \\sum_i x_i \\]") == "\\sum_i x_i"
    assert nettoyer_latex("\\begin{equation} a+b \\end{equation}") == "a+b"
    assert nettoyer_latex("$x^2$") == "x^2"


def test_slide_visuelle() -> None:
    base = dict(id="c__s001", course_id="c", numero=1)
    assert not slide_visuelle(Slide(**base, texte="Plan du cours"))
    assert slide_visuelle(Slide(**base, images=["images/x1.png"]))
    assert slide_visuelle(Slide(**base, ocr=True))
    assert slide_visuelle(Slide(**base, texte="f(x) = ∑ a_i x^i"))
    assert slide_visuelle(Slide(**base), nb_dessins=30)


def test_enrichissement_slides_visuelles(cours, tmp_path: Path, monkeypatch) -> None:
    course, sortie = cours
    monkeypatch.setenv("VLM_FAKE_REPONSE", json.dumps({
        "figures": ["Aucune figure", "Courbe en cloche de la loi normale centrée en μ."],
        "formules": ["$\\sigma^2 = E[(X-\\mu)^2]$", "$\\sigma^2 = E[(X-\\mu)^2]$", "variance"],
    }))
    enrichi = enrich_with_vlm(course, dossier=sortie, cache=tmp_path / "cache")

    s1, s2, s3 = enrichi.slides
    assert s1.description_figures == [] and s3.formules_latex == []  # slides non visuelles ignorées
    assert s2.description_figures == ["Courbe en cloche de la loi normale centrée en μ."]
    assert s2.formules_latex == ["\\sigma^2 = E[(X-\\mu)^2]"]  # nettoyée, dédupliquée, « variance » rejetée
    # course.json réécrit et valide
    relu = json.loads((sortie / "course.json").read_text(encoding="utf-8"))
    assert relu["slides"][1]["formules_latex"] == s2.formules_latex


def test_toutes_les_slides(cours, tmp_path: Path) -> None:
    course, sortie = cours
    enrichi = enrich_with_vlm(course, dossier=sortie, cache=tmp_path / "cache", toutes=True, sauvegarder=False)
    assert all(s.formules_latex == ["E = mc^2"] for s in enrichi.slides)


def test_cache_evite_un_second_appel(cours, tmp_path: Path, monkeypatch) -> None:
    course, sortie = cours
    monkeypatch.setattr(vlm, "backend", lambda: "llamacpp")  # backend réel simulé : le cache est actif
    appels: list[int] = []

    def faux_vlm(chemin, slide, langue):
        appels.append(slide.numero)
        return AnalyseVisuelle(figures=["Histogramme des valeurs observées."], formules=["x^2"])

    monkeypatch.setattr(vlm, "analyser_image", faux_vlm)
    cache = tmp_path / "cache"
    premier = enrich_with_vlm(course, dossier=sortie, cache=cache, sauvegarder=False)
    second = enrich_with_vlm(course, dossier=sortie, cache=cache, sauvegarder=False)
    assert appels == [2], "le VLM doit être appelé une seule fois, puis lu dans le cache"
    assert premier == second
    assert len(list(cache.rglob("*.json"))) == 1
    enrich_with_vlm(course, dossier=sortie, cache=cache, sauvegarder=False, force=True)
    assert appels == [2, 2]


def test_vlm_indisponible_ne_bloque_pas(cours, tmp_path: Path, monkeypatch) -> None:
    course, sortie = cours
    monkeypatch.setattr(vlm, "backend", lambda: "llamacpp")

    def en_panne(*_a, **_k):
        raise vlm.VLMIndisponible("fichier GGUF introuvable : models/x.gguf")

    monkeypatch.setattr(vlm, "analyser_image", en_panne)
    enrichi = enrich_with_vlm(course, dossier=sortie, cache=tmp_path / "cache", toutes=True, sauvegarder=False)
    assert enrichi == course


def test_filtres_sur_sorties_reelles() -> None:
    """Sorties observées avec Qwen2.5-VL-3B : doublons, formule décrite, phrase en guise de formule."""
    analyse = AnalyseVisuelle(
        figures=[
            "A diagram illustrating self-attention in a neural network, showing how elements (q, k, v) "
            "are connected and weighted by attention coefficients.",
            "A formula for calculating b2 is shown, representing the sum of weighted elements.",
            "A diagram showing the self-attention mechanism in a neural network, with q, k, and v "
            "elements connected by attention coefficients.",
        ],
        formules=["M^{-1}=A^{-1}", r"\textbf{Defi Singular Matrix No all non-zero matrices A have an inverse.",
                  r"\text{softmax}(QK^T / \sqrt{d_k}) V", "x^2" * 120],
    )
    figures, formules = vlm._nettoyer(analyse)
    assert len(figures) == 1 and figures[0].startswith("A diagram illustrating")
    assert formules == ["M^{-1}=A^{-1}", r"\text{softmax}(QK^T / \sqrt{d_k}) V"]
