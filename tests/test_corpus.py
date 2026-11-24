"""Cohérence du corpus C1 : inventaires, fichiers, identifiants et noyau."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from schemas import est_course_id_valide

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"
INVENTAIRES = sorted(CORPUS.glob("inventaire_*.csv"))
TAILLE_MAX = 20 * 1024 * 1024


def _lignes() -> list[dict[str, str]]:
    lignes: list[dict[str, str]] = []
    for inv in INVENTAIRES:
        with open(inv, encoding="utf-8") as f:
            lignes.extend(csv.DictReader(f))
    return lignes


def test_inventaires_presents() -> None:
    assert INVENTAIRES, "aucun inventaire dans data/corpus/"


@pytest.mark.parametrize("ligne", _lignes(), ids=lambda x: x["fichier"])
def test_ligne_inventaire(ligne: dict[str, str]) -> None:
    chemin = CORPUS / ligne["fichier"]
    assert chemin.is_file(), f"fichier absent : {ligne['fichier']}"
    assert est_course_id_valide(chemin.stem), f"course_id invalide : {chemin.stem}"
    assert chemin.stat().st_size <= TAILLE_MAX, f"plus de 20 Mo : {ligne['fichier']}"
    langue, domaine = Path(ligne["fichier"]).parts[:2]
    assert langue == ligne["langue"]
    assert domaine == ligne["domaine"]
    assert int(ligne["nombre_slides"]) >= 1


def test_course_ids_uniques() -> None:
    ids = [Path(x["fichier"]).stem for x in _lignes()]
    doublons = {i for i in ids if ids.count(i) > 1}
    assert not doublons, f"course_id en double : {doublons}"


@pytest.mark.parametrize("nom", ["noyau_ons.json", "noyau_both.json"])
def test_noyau(nom: str) -> None:
    noyau = json.loads((CORPUS / nom).read_text(encoding="utf-8"))["cours"]
    inventaire = {x["fichier"]: x for x in _lignes()}
    assert 5 <= len(noyau) <= 10
    for cours in noyau:
        ligne = inventaire[cours["fichier"]]
        assert Path(cours["fichier"]).stem == cours["course_id"]
        assert 15 <= int(ligne["nombre_slides"]) <= 60, cours["course_id"]
    langues = {inventaire[c["fichier"]]["langue"] for c in noyau}
    formats = {inventaire[c["fichier"]]["format"] for c in noyau}
    assert langues == {"fr", "en"}
    assert formats == {"PDF", "PPTX"}
