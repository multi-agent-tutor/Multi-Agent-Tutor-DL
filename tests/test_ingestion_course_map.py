"""H3 — carte du cours : graphe de prérequis, get_prerequisites, LLM simulé et repli heuristique."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion import course_map
from ingestion.course_map import (
    build_course_map,
    cle_concept,
    concepts_heuristiques,
    construire_graphe,
    exporter_mermaid,
    get_prerequisites,
)
from schemas import Course, Slide, slide_id

CID = "maths_algebre_test_fr"
CONTENUS = [
    ("Les vecteurs", "Un vecteur est une liste de nombres réels. Addition de vecteurs."),
    ("Les matrices", "Une matrice est un tableau de nombres ; ses colonnes sont des vecteurs."),
    ("Produit matriciel", "Le produit matriciel combine deux matrices ; chaque colonne est un vecteur."),
    ("Valeurs propres", "Pour une matrice A, un vecteur propre v vérifie A v = λ v ; λ est la valeur propre."),
    ("Diagonalisation", "Une matrice est diagonalisable si elle admet une base de vecteurs propres."),
]
CONCEPTS = {
    1: ["vecteur"],
    2: ["matrice", "vecteurs"],
    3: ["produit matriciel", "matrices"],
    4: ["valeur propre", "vecteur propre"],
    5: ["diagonalisation", "vecteurs propres"],
}


@pytest.fixture
def course() -> Course:
    slides = [Slide(id=slide_id(CID, i), course_id=CID, numero=i, titre=t, texte=x)
              for i, (t, x) in enumerate(CONTENUS, start=1)]
    return Course(id=CID, titre="Algèbre linéaire", fichier_source="x.pdf", format="pdf", langue="fr",
                  nombre_slides=len(slides), slides=slides)


class _FauxLLM:
    """Remplace agents.llm : concepts imposés par slide et résumé fixe."""

    class LLMIndisponible(RuntimeError):
        pass

    def __init__(self, en_panne: bool = False) -> None:
        self.en_panne = en_panne
        self.appels = 0

    def backend(self) -> str:
        return "fake"

    def modele(self) -> str:
        return "faux"

    def est_configure(self) -> bool:
        return True

    def generer_structure(self, system, prompt, schema, *, max_tokens=0):
        self.appels += 1
        if self.en_panne:
            raise self.LLMIndisponible("modèle absent")
        numero = int(prompt.split("Slide ")[1].split()[0])
        return schema(concepts=CONCEPTS[numero])

    def generer_texte(self, system, prompt, *, max_tokens=0):
        return "Ce cours présente les vecteurs, les matrices puis la diagonalisation."


def test_cle_concept() -> None:
    assert cle_concept("Les Matrices") == cle_concept("matrice")
    assert cle_concept("Valeurs propres") == cle_concept("valeur propre")
    assert cle_concept("Réseau de neurones") == "reseau de neurone"


def test_graphe_et_prerequis(course: Course) -> None:
    carte = construire_graphe(course, CONCEPTS)
    concepts = carte["concepts"]
    assert concepts["matrice"]["introduit_slide"] == 2
    assert concepts["vecteur"]["slides"] == [1, 2, 3, 4, 5]  # extrait + cité dans le texte
    assert "vecteur" in concepts["matrice"]["prerequis"]
    assert {"matrice", "vecteur"} <= set(concepts["valeur propre"]["prerequis"])
    # Acyclique : un prérequis est toujours introduit avant.
    for c in concepts.values():
        for p in c["prerequis"]:
            assert concepts[p]["introduit_slide"] < c["introduit_slide"]
    assert carte["slides"][slide_id(CID, 1)]["prerequis"] == []
    s5 = carte["slides"][slide_id(CID, 5)]["prerequis"]
    assert slide_id(CID, 4) in s5 and slide_id(CID, 2) in s5
    assert "-->" in exporter_mermaid(carte)


def test_build_course_map_avec_llm(course: Course, tmp_path: Path, monkeypatch) -> None:
    faux = _FauxLLM()
    monkeypatch.setattr(course_map, "_llm", lambda: faux)
    resultat = build_course_map(course, dossier=tmp_path, utiliser_llm=True, cache=tmp_path / "cache")

    assert resultat.slides[3].concepts == ["valeur propre", "vecteur propre"]
    assert resultat.resume.startswith("Ce cours présente")
    carte = json.loads((tmp_path / "course_map.json").read_text(encoding="utf-8"))
    assert carte["methode"] == "llm:faux"
    assert Course.model_validate_json((tmp_path / "course.json").read_text(encoding="utf-8")) == resultat
    # get_prerequisites lit la carte écrite sur disque.
    prerequis = get_prerequisites(slide_id(CID, 4), dossier=tmp_path)
    assert prerequis == sorted(prerequis) and slide_id(CID, 2) in prerequis
    assert get_prerequisites(slide_id(CID, 1), dossier=tmp_path) == []


def test_repli_si_llm_en_panne(course: Course, tmp_path: Path, monkeypatch) -> None:
    faux = _FauxLLM(en_panne=True)
    monkeypatch.setattr(course_map, "_llm", lambda: faux)
    resultat = build_course_map(course, dossier=tmp_path, utiliser_llm=True, cache=tmp_path / "cache")
    carte = json.loads((tmp_path / "course_map.json").read_text(encoding="utf-8"))
    assert carte["methode"] == "heuristique"
    assert faux.appels == 3, "abandon du LLM après 3 échecs consécutifs"
    assert any(s.concepts for s in resultat.slides)
    assert "Algèbre linéaire" in resultat.resume


def test_heuristique_titre_prioritaire(course: Course) -> None:
    concepts = concepts_heuristiques(course)
    assert any("diagonalisation" in c.lower() for c in concepts[5])


def test_get_prerequisites_sans_carte(tmp_path: Path) -> None:
    assert get_prerequisites("cours_inconnu__s001", dossier=tmp_path) == []
    with pytest.raises(ValueError):
        get_prerequisites("pas_un_id")
