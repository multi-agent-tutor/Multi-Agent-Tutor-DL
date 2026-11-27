"""H1 — parsers PDF/PPTX : fichiers synthétiques créés à la volée (rapides, sans dépendance système)."""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from ingestion import parse
from ingestion.parse import charger_course, course_id_depuis_fichier, detecter_langue, parse_course
from schemas import Course


def _png(taille: int = 120) -> bytes:
    """Image bruitée (donc distincte et assez lourde pour passer les seuils de taille)."""
    tampon = io.BytesIO()
    Image.effect_noise((taille, taille), 60 + taille % 7).convert("RGB").save(tampon, "PNG")
    return tampon.getvalue()


@pytest.fixture
def pdf_cours(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    logo = _png(64)
    contenus = [
        ("Introduction", "La régression linéaire est une méthode de base pour prédire une valeur."),
        ("Moindres carrés", "On minimise la somme des carrés des erreurs entre prédiction et cible."),
        ("Gradient", "La descente de gradient met à jour les poids dans la direction opposée."),
        ("", ""),  # page vide : déclenche l'OCR
    ]
    for titre, texte in contenus:
        page = doc.new_page(width=720, height=405)
        if titre:
            page.insert_text((40, 60), titre, fontsize=28)
            page.insert_text((40, 120), texte, fontsize=12)
            page.insert_text((40, 380), "Cours de ML - Université X", fontsize=9)  # pied de page répété
        page.insert_image(pymupdf.Rect(640, 10, 700, 70), stream=logo)  # logo sur chaque page
    doc[1].insert_image(pymupdf.Rect(300, 150, 500, 350), stream=_png(200))
    chemin = tmp_path / "ml_regression_test_fr.pdf"
    doc.save(chemin)
    return chemin


@pytest.fixture
def pptx_cours(tmp_path: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Self-attention"
    s1.placeholders[1].text = "Each vector attends to all the others in the sequence"
    s1.notes_slide.notes_text_frame.text = "Mention the link with CNN"
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Results table"
    table = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    table.cell(0, 0).text, table.cell(0, 1).text = "Model", "Accuracy"
    table.cell(1, 0).text, table.cell(1, 1).text = "Transformer", "92%"
    s2.shapes.add_picture(io.BytesIO(_png(150)), Inches(5), Inches(2))
    chemin = tmp_path / "dl_attention_test_en.pptx"
    prs.save(chemin)
    return chemin


def test_course_id_depuis_fichier() -> None:
    assert course_id_depuis_fichier(Path("ML Régression-Linéaire (v2).pdf")) == "ml_regression_lineaire_v2"
    assert course_id_depuis_fichier(Path("dl_cnn_ntu_en.pptx")) == "dl_cnn_ntu_en"


def test_detecter_langue() -> None:
    assert detecter_langue("Le modèle est entraîné sur les données et la perte est calculée pour " * 3) == "fr"
    assert detecter_langue("The model is trained on the data and the loss is computed for the batch " * 3) == "en"
    assert detecter_langue("x y z") is None


def test_pdf_texte_titres_images_rendus(pdf_cours: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(parse, "ocr_page", lambda page, langue="fr": "Texte reconnu par OCR sur la page scannée")
    sortie = tmp_path / "out"
    course = parse_course(pdf_cours, dossier_sortie=sortie)

    assert isinstance(course, Course)
    assert course.id == "ml_regression_test_fr" and course.format == "pdf" and course.langue == "fr"
    assert course.nombre_slides == 4
    s1, s2, _, s4 = course.slides
    assert s1.id == "ml_regression_test_fr__s001"
    assert s1.titre == "Introduction"
    assert "régression linéaire" in s1.texte
    assert "Université X" not in s1.texte, "pied de page répété non retiré"
    # Le logo (sur toutes les pages) est ignoré, l'image propre à la slide 2 est gardée.
    assert s1.images == [] and len(s2.images) == 1
    assert (sortie / s2.images[0]).is_file()
    # Rendus PNG 150 dpi : 720 pt de large → 1500 px.
    assert s1.image_rendu == "slides/s001.png"
    assert Image.open(sortie / s1.image_rendu).width == 1500
    # Page sans texte → OCR.
    assert s4.ocr and "OCR" in s4.texte and not s1.ocr
    # course.json relu à l'identique.
    assert charger_course(course.id, sortie) == course


def test_pdf_texte_brut_sans_rendu_ni_ocr(pdf_cours: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(parse, "ocr_page", lambda *a, **k: pytest.fail("OCR appelé"))
    course = parse_course(pdf_cours, dossier_sortie=tmp_path / "out", rendu=False, ocr=False,
                          extraire_images=False)
    assert all(s.image_rendu is None and s.images == [] and not s.ocr for s in course.slides)
    assert course.slides[3].texte == ""


def test_pptx_texte_notes_tableau_image(pptx_cours: Path, tmp_path: Path) -> None:
    sortie = tmp_path / "out"
    course = parse_course(pptx_cours, dossier_sortie=sortie, rendu=False, ocr=False)

    assert course.format == "pptx" and course.langue == "en" and course.nombre_slides == 2
    s1, s2 = course.slides
    assert s1.titre == "Self-attention"
    assert "attends to all the others" in s1.texte
    assert s1.notes == "Mention the link with CNN"
    assert s2.titre == "Results table"
    assert "Transformer | 92%" in s2.texte
    assert len(s2.images) == 1 and (sortie / s2.images[0]).is_file()


def test_texte_incomplet_puces_vides() -> None:
    assert parse._texte_incomplet("Today\n• \n• \n• \n")
    assert not parse._texte_incomplet("Today we study\n• supervised learning\n• risk")


def test_format_refuse(tmp_path: Path) -> None:
    fichier = tmp_path / "cours.docx"
    fichier.write_text("x")
    with pytest.raises(ValueError, match="format"):
        parse_course(fichier)
