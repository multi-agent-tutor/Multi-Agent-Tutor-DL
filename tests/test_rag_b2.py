"""Tests B2 : slides -> chunks (contexte des voisines), indexation, reranking.

Sans modèle : HashEmbedder, MotsCommunsReranker et Qdrant en mémoire.
"""

import json
from pathlib import Path

import pytest

from rag.index import (
    charger_cours,
    chunks_du_cours,
    contenu_slide,
    fichiers_cours,
    indexer_cours,
    indexer_dossier,
    main,
    resume_slide,
)
from rag.rerank import MotsCommunsReranker, RechercheReranked, reranker
from rag.search import RechercheHybride
from rag.store import HashEmbedder, VectorStore
from schemas.models import Course, SearchHit, Slide

EXEMPLE = Path("schemas/exemples/exemple_cours.json")


def _cours(course_id: str = "bd_test_fr", langue: str = "fr") -> Course:
    slides = [
        Slide(id=f"{course_id}__s001", course_id=course_id, numero=1, titre="Introduction",
              texte="Plan du cours de bases de données."),
        Slide(id=f"{course_id}__s002", course_id=course_id, numero=2, titre="Clé primaire",
              texte="La clé primaire identifie chaque n-uplet.", notes="Insister sur l'unicité.",
              description_figures=["Table PERSONNE avec la colonne Id soulignée."]),
        Slide(id=f"{course_id}__s003", course_id=course_id, numero=3, titre="",
              texte="La jointure naturelle combine deux relations sur leurs attributs communs."),
        Slide(id=f"{course_id}__s004", course_id=course_id, numero=4, titre="SGBD",
              texte="Un SGBD gère une base de données partagée."),
    ]
    return Course(id=course_id, titre="Bases de données", fichier_source=f"data/corpus/{course_id}.pdf",
                  format="pdf", langue=langue, nombre_slides=len(slides), slides=slides)


def test_contenu_slide_concatene_texte_notes_figures():
    slide = _cours().slides[1]
    contenu = contenu_slide(slide)
    assert "identifie chaque n-uplet" in contenu
    assert "Notes : Insister sur l'unicité." in contenu
    assert "Figure : Table PERSONNE" in contenu


def test_resume_slide_titre_sinon_debut_du_texte():
    cours = _cours()
    assert resume_slide(cours.slides[1]) == "Clé primaire"
    assert resume_slide(cours.slides[2]).startswith("La jointure naturelle")


def test_chunks_du_cours_un_par_slide_avec_contexte():
    chunks = chunks_du_cours(_cours())
    assert [c.id for c in chunks] == [f"bd_test_fr__s00{i}" for i in range(1, 5)]
    assert chunks[0].contexte_precedent == "" and chunks[0].contexte_suivant == "Clé primaire"
    assert chunks[1].contexte_precedent == "Introduction"
    assert chunks[1].contexte_suivant.startswith("La jointure")
    assert chunks[-1].contexte_suivant == ""
    assert all(c.langue == "fr" and c.course_id == "bd_test_fr" for c in chunks)


def test_exemple_officiel_t0():
    cours = charger_cours(EXEMPLE)
    chunks = chunks_du_cours(cours)
    assert len(chunks) == cours.nombre_slides
    assert chunks[0].id == cours.slides[0].id


def test_indexer_cours_remplace_l_ancienne_version():
    store = VectorStore(HashEmbedder())
    cours = _cours()
    assert indexer_cours(store, cours) == 4
    plus_court = Course(**{**cours.model_dump(), "nombre_slides": 2, "slides": cours.model_dump()["slides"][:2]})
    indexer_cours(store, plus_court)
    assert store.compter("bd_test_fr") == 2  # les anciennes slides 3 et 4 ont disparu
    store.fermer()


def _ecrire(dossier: Path, cours: Course) -> None:
    (dossier / cours.id).mkdir(parents=True)
    (dossier / cours.id / "course.json").write_text(cours.model_dump_json(), encoding="utf-8")


def test_indexer_dossier_et_cli(tmp_path, capsys):
    processed = tmp_path / "processed"
    _ecrire(processed, _cours("bd_test_fr"))
    _ecrire(processed, _cours("bd_autre_en", langue="en"))
    assert [p.parent.name for p in fichiers_cours(processed)] == ["bd_autre_en", "bd_test_fr"]

    store = VectorStore(HashEmbedder())
    assert indexer_dossier(store, processed) == {"bd_autre_en": 4, "bd_test_fr": 4}
    store.fermer()

    main([str(processed), "--hash", "--chemin", str(tmp_path / "qdrant")])
    assert "Total dans la collection 'slides_hash' : 8 chunks" in capsys.readouterr().out


def test_course_json_invalide_refuse(tmp_path):
    mauvais = tmp_path / "course.json"
    mauvais.write_text(json.dumps({"id": "x"}), encoding="utf-8")
    with pytest.raises(Exception):
        charger_cours(mauvais)


def test_reranker_reclasse_et_coupe():
    chunks = chunks_du_cours(_cours())
    hits = [SearchHit(chunk=c, score=1.0) for c in chunks]  # ordre initial : s001..s004
    resultat = reranker(MotsCommunsReranker(), "jointure naturelle", hits, top=2)
    assert len(resultat) == 2
    assert resultat[0].chunk.id == "bd_test_fr__s003"
    assert resultat[0].score == pytest.approx(1.0)
    assert resultat[0].score >= resultat[1].score
    assert reranker(MotsCommunsReranker(), "jointure", [], top=5) == []


def test_pipeline_hybride_puis_rerank_top5():
    store = VectorStore(HashEmbedder())
    indexer_cours(store, _cours("bd_test_fr"))
    indexer_cours(store, _cours("bd_autre_en", langue="en"))
    pipeline = RechercheReranked(RechercheHybride(store), MotsCommunsReranker())
    hits = pipeline.rechercher("Qu'est-ce qu'une clé primaire ?", course_id="bd_test_fr")
    assert 1 <= len(hits) <= 5
    assert hits[0].chunk.id == "bd_test_fr__s002"
    assert all(h.chunk.course_id == "bd_test_fr" for h in hits)
    assert all(0.0 <= h.score <= 1.0 for h in hits)
    store.fermer()
