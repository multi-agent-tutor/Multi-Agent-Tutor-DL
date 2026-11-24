"""A6 — Révision espacée (SM-2) des flashcards, stockage SQLite et export Anki, sans aucune API.

1. ``revoir(etat, qualite)`` : algorithme SM-2 pur (aucune E/S) ;
2. stockage SQLite local (``SRS_DB_PATH``, défaut ``data/srs.db``) des cartes de chaque
   utilisateur et de leur état SM-2 : ``ajouter_cartes``, ``cartes_a_reviser``,
   ``enregistrer_revision`` ;
3. ``exporter_apkg`` : paquet Anki (.apkg, genanki) d'un deck par cours, avec des ids de modèle
   et de deck stables dérivés du ``course_id`` (réimporter met à jour le même deck).

SM-2 (Wozniak, 1990) ; ``qualite`` va de 0 (oubli total) à 5 (réponse parfaite) :

- ``facilite += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)``, jamais sous 1.3 (départ 2.5) ;
- ``q < 3`` : ``repetitions = 0`` et ``intervalle = 1`` (la carte revient demain) ;
- sinon intervalles 1, puis 6, puis ``intervalle * facilite`` arrondi (facilité d'avant la note).
"""

from __future__ import annotations

import hashlib
import html
import math
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from api.models import CarteSRS, EtatSM2, Flashcard
from schemas.models import Source

load_dotenv()

RACINE = Path(__file__).resolve().parent.parent
DB_PAR_DEFAUT = "data/srs.db"

FACILITE_INITIALE = 2.5
FACILITE_MIN = 1.3
QUALITE_REUSSITE = 3
PREMIER_INTERVALLE = 1
DEUXIEME_INTERVALLE = 6


# --------------------------------------------------------------------------- SM-2


@dataclass(frozen=True)
class EtatCarte:
    """État SM-2 d'une carte ; une carte neuve est à réviser aujourd'hui."""

    repetitions: int = 0
    intervalle: int = 0
    facilite: float = FACILITE_INITIALE
    prochaine_revision: date | None = None


def _arrondir(valeur: float) -> int:
    """Arrondi au plus proche, demi vers le haut, insensible au bruit flottant (45 * 2.9 -> 131)."""
    return math.floor(round(valeur, 6) + 0.5)


def revoir(etat: EtatCarte, qualite: int, aujourd_hui: date | None = None) -> EtatCarte:
    """Nouvel état SM-2 d'une carte après une révision notée ``qualite`` (0..5)."""
    if isinstance(qualite, bool) or not isinstance(qualite, int) or not 0 <= qualite <= 5:
        raise ValueError(f"qualite doit être un entier de 0 à 5, reçu {qualite!r}")
    jour = aujourd_hui or date.today()

    if qualite < QUALITE_REUSSITE:
        repetitions, intervalle = 0, PREMIER_INTERVALLE
    else:
        if etat.repetitions == 0:
            intervalle = PREMIER_INTERVALLE
        elif etat.repetitions == 1:
            intervalle = DEUXIEME_INTERVALLE
        else:
            intervalle = max(1, _arrondir(etat.intervalle * etat.facilite))
        repetitions = etat.repetitions + 1

    ecart = 5 - qualite
    facilite = max(FACILITE_MIN, round(etat.facilite + 0.1 - ecart * (0.08 + ecart * 0.02), 4))
    return replace(
        etat,
        repetitions=repetitions,
        intervalle=intervalle,
        facilite=facilite,
        prochaine_revision=jour + timedelta(days=intervalle),
    )


# --------------------------------------------------------------------------- stockage SQLite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cartes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user       TEXT NOT NULL,
    course_id  TEXT NOT NULL,
    recto      TEXT NOT NULL,
    verso      TEXT NOT NULL,
    source     TEXT NOT NULL,
    cree_le    TEXT NOT NULL,
    UNIQUE (user, course_id, recto, verso)
);
CREATE TABLE IF NOT EXISTS etats (
    carte_id           INTEGER PRIMARY KEY REFERENCES cartes(id) ON DELETE CASCADE,
    repetitions        INTEGER NOT NULL,
    intervalle         INTEGER NOT NULL,
    facilite           REAL NOT NULL,
    prochaine_revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    carte_id  INTEGER NOT NULL REFERENCES cartes(id) ON DELETE CASCADE,
    jour      TEXT NOT NULL,
    qualite   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cartes_user ON cartes(user, course_id);
CREATE INDEX IF NOT EXISTS idx_etats_revision ON etats(prochaine_revision);
"""

_SELECT = """
SELECT c.id, c.user, c.course_id, c.recto, c.verso, c.source,
       e.repetitions, e.intervalle, e.facilite, e.prochaine_revision
FROM cartes c JOIN etats e ON e.carte_id = c.id
"""


def chemin_db() -> Path:
    """Base SQLite : ``SRS_DB_PATH`` (relatif à la racine du dépôt), défaut ``data/srs.db``."""
    chemin = Path(os.getenv("SRS_DB_PATH", "").strip() or DB_PAR_DEFAUT)
    return chemin if chemin.is_absolute() else RACINE / chemin


@contextmanager
def _connexion(db: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Connexion ouverte puis fermée (indispensable sous Windows), transaction validée en sortie."""
    chemin = Path(db) if db is not None else chemin_db()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(chemin)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        with conn:
            yield conn


def _carte(ligne: sqlite3.Row) -> CarteSRS:
    return CarteSRS(
        id=ligne["id"],
        user=ligne["user"],
        course_id=ligne["course_id"],
        recto=ligne["recto"],
        verso=ligne["verso"],
        source=Source.model_validate_json(ligne["source"]),
        etat=EtatSM2(
            repetitions=ligne["repetitions"],
            intervalle=ligne["intervalle"],
            facilite=ligne["facilite"],
            prochaine_revision=date.fromisoformat(ligne["prochaine_revision"]),
        ),
    )


def ajouter_cartes(
    user: str,
    flashcards: Iterable[Flashcard],
    aujourd_hui: date | None = None,
    db: str | Path | None = None,
) -> list[CarteSRS]:
    """Enregistrer les flashcards (A2) d'un utilisateur ; une carte déjà connue n'est pas dupliquée.

    Les cartes neuves sont à réviser dès ``aujourd_hui``. Renvoie les cartes dans l'ordre reçu.
    """
    jour = (aujourd_hui or date.today()).isoformat()
    ids: list[int] = []
    with _connexion(db) as conn:
        for carte in flashcards:
            course_id = carte.source.course_id
            conn.execute(
                "INSERT OR IGNORE INTO cartes (user, course_id, recto, verso, source, cree_le) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user, course_id, carte.recto, carte.verso, carte.source.model_dump_json(), jour),
            )
            (carte_id,) = conn.execute(
                "SELECT id FROM cartes WHERE user = ? AND course_id = ? AND recto = ? AND verso = ?",
                (user, course_id, carte.recto, carte.verso),
            ).fetchone()
            conn.execute(
                "INSERT OR IGNORE INTO etats VALUES (?, 0, 0, ?, ?)",
                (carte_id, FACILITE_INITIALE, jour),
            )
            ids.append(carte_id)
        marques = ",".join("?" * len(ids))
        lignes = conn.execute(_SELECT + f" WHERE c.id IN ({marques})", ids).fetchall() if ids else []
    par_id = {ligne["id"]: _carte(ligne) for ligne in lignes}
    return [par_id[i] for i in ids]


def cartes_a_reviser(
    user: str,
    jour: date | None = None,
    course_id: str | None = None,
    db: str | Path | None = None,
) -> list[CarteSRS]:
    """Cartes de ``user`` dont la révision est due au plus tard ``jour`` (défaut : aujourd'hui)."""
    requete = _SELECT + " WHERE c.user = ? AND e.prochaine_revision <= ?"
    params: list[object] = [user, (jour or date.today()).isoformat()]
    if course_id is not None:
        requete += " AND c.course_id = ?"
        params.append(course_id)
    with _connexion(db) as conn:
        lignes = conn.execute(requete + " ORDER BY e.prochaine_revision, c.id", params).fetchall()
    return [_carte(ligne) for ligne in lignes]


def cartes_du_cours(user: str, course_id: str, db: str | Path | None = None) -> list[CarteSRS]:
    """Toutes les cartes de ``user`` pour un cours, dans l'ordre d'enregistrement."""
    with _connexion(db) as conn:
        lignes = conn.execute(
            _SELECT + " WHERE c.user = ? AND c.course_id = ? ORDER BY c.id", (user, course_id)
        ).fetchall()
    return [_carte(ligne) for ligne in lignes]


def enregistrer_revision(
    user: str,
    carte_id: int,
    qualite: int,
    aujourd_hui: date | None = None,
    db: str | Path | None = None,
) -> CarteSRS:
    """Appliquer SM-2 à une carte de ``user`` et enregistrer la révision.

    ``KeyError`` si la carte n'existe pas pour cet utilisateur, ``ValueError`` si la note est hors 0..5.
    """
    jour = aujourd_hui or date.today()
    with _connexion(db) as conn:
        ligne = conn.execute(_SELECT + " WHERE c.id = ? AND c.user = ?", (carte_id, user)).fetchone()
        if ligne is None:
            raise KeyError(f"Carte {carte_id} inconnue pour l'utilisateur {user!r}")
        actuel = EtatCarte(ligne["repetitions"], ligne["intervalle"], ligne["facilite"])
        nouvel = revoir(actuel, qualite, jour)
        conn.execute(
            "UPDATE etats SET repetitions = ?, intervalle = ?, facilite = ?, prochaine_revision = ? "
            "WHERE carte_id = ?",
            (nouvel.repetitions, nouvel.intervalle, nouvel.facilite,
             nouvel.prochaine_revision.isoformat(), carte_id),
        )
        conn.execute(
            "INSERT INTO revisions (carte_id, jour, qualite) VALUES (?, ?, ?)",
            (carte_id, jour.isoformat(), qualite),
        )
        ligne = conn.execute(_SELECT + " WHERE c.id = ?", (carte_id,)).fetchone()
    return _carte(ligne)


# --------------------------------------------------------------------------- export Anki


def id_stable(course_id: str, sel: str) -> int:
    """Id Anki stable (31 bits, jamais 0) dérivé du ``course_id`` : même cours, même id."""
    empreinte = hashlib.sha256(f"multi_agent_tutor:{sel}:{course_id}".encode()).digest()
    return (1 << 30) + int.from_bytes(empreinte[:4], "big") % (1 << 30)


def _modele(course_id: str):  # -> genanki.Model
    import genanki

    return genanki.Model(
        id_stable(course_id, "modele"),
        f"Tuteur multi-agent — {course_id}",
        fields=[{"name": "Recto"}, {"name": "Verso"}, {"name": "Source"}],
        templates=[{
            "name": "Carte",
            "qfmt": "{{Recto}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Verso}}<br><small>{{Source}}</small>',
        }],
    )


def construire_deck(course_id: str, cartes: Iterable[CarteSRS | Flashcard]):  # -> genanki.Deck
    """Deck Anki d'un cours (id stable) ; le guid de chaque note dépend de son contenu."""
    import genanki

    modele = _modele(course_id)
    deck = genanki.Deck(id_stable(course_id, "deck"), f"Tuteur::{course_id}")
    for carte in cartes:
        source = f"[Slide {carte.source.numero}] {carte.source.course_id}"
        deck.add_note(genanki.Note(
            model=modele,
            fields=[html.escape(carte.recto), html.escape(carte.verso), html.escape(source)],
            guid=genanki.guid_for(course_id, carte.recto, carte.verso),
            tags=[course_id],
        ))
    return deck


def exporter_apkg(
    user: str,
    course_id: str,
    destination: str | Path | None = None,
    db: str | Path | None = None,
) -> bytes:
    """Paquet .apkg des cartes de ``user`` pour un cours (écrit aussi dans ``destination``).

    ``LookupError`` si l'utilisateur n'a aucune carte pour ce cours.
    """
    import genanki

    cartes = cartes_du_cours(user, course_id, db)
    if not cartes:
        raise LookupError(f"Aucune carte pour {user!r} dans le cours {course_id}")
    paquet = genanki.Package(construire_deck(course_id, cartes))
    with tempfile.TemporaryDirectory() as dossier:
        fichier = Path(dossier) / f"{course_id}.apkg"
        paquet.write_to_file(str(fichier))
        contenu = fichier.read_bytes()
    if destination is not None:
        Path(destination).write_bytes(contenu)
    return contenu


__all__ = [
    "EtatCarte",
    "ajouter_cartes",
    "cartes_a_reviser",
    "cartes_du_cours",
    "chemin_db",
    "construire_deck",
    "enregistrer_revision",
    "exporter_apkg",
    "id_stable",
    "revoir",
]
