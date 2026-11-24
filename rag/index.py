"""B2 — Indexation des slides : un chunk = une slide, avec le contexte des voisines.

Entrée : les ``course.json`` produits par l'ingestion (H1), au format ``schemas.models.Course``,
rangés dans ``data/processed/<course_id>/course.json``.
Sortie : des ``Chunk`` indexés dans le ``VectorStore`` de B1.

Contenu d'un chunk (contrat T0) : texte + notes + descriptions des figures.
Quand H2 (VLM) ajoute les descriptions des figures, il suffit de relancer l'indexation :
chaque slide garde le même identifiant, et l'ancienne version du cours est remplacée.

Ligne de commande :
    python -m rag.index                                   # tous les cours de data/processed/
    python -m rag.index data/processed/<id>/course.json   # un seul cours
    python -m rag.index --hash                            # embedder factice, sans modèle
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from rag.store import CHEMIN_PAR_DEFAUT, NOM_COLLECTION, VectorStore
from schemas.models import Chunk, Course, Slide

DOSSIER_PAR_DEFAUT = "data/processed"
LONGUEUR_RESUME = 150  # caractères gardés quand une slide voisine n'a pas de titre


def contenu_slide(slide: Slide) -> str:
    """Texte indexé d'une slide : texte visible, notes, puis descriptions des figures."""
    parties = []
    if slide.texte.strip():
        parties.append(slide.texte.strip())
    if slide.notes.strip():
        parties.append(f"Notes : {slide.notes.strip()}")
    parties += [f"Figure : {d.strip()}" for d in slide.description_figures if d.strip()]
    return "\n".join(parties)


def resume_slide(slide: Slide | None) -> str:
    """Contexte d'une slide voisine : son titre, sinon le début de son texte."""
    if slide is None:
        return ""
    if slide.titre.strip():
        return slide.titre.strip()
    return " ".join(slide.texte.split())[:LONGUEUR_RESUME]


def chunks_du_cours(course: Course) -> list[Chunk]:
    """Transformer un cours en chunks : une slide = un chunk.

    Les slides sans titre ni contenu (pages blanches) ne sont pas indexées, mais
    le contexte vient toujours des slides N-1 et N+1 du cours.
    """
    chunks = []
    for i, slide in enumerate(course.slides):
        contenu = contenu_slide(slide)
        if not contenu and not slide.titre.strip():
            continue
        precedente = course.slides[i - 1] if i > 0 else None
        suivante = course.slides[i + 1] if i + 1 < len(course.slides) else None
        chunks.append(
            Chunk(
                id=slide.id,
                course_id=course.id,
                numero=slide.numero,
                titre=slide.titre,
                contenu=contenu or slide.titre,
                contexte_precedent=resume_slide(precedente),
                contexte_suivant=resume_slide(suivante),
                langue=course.langue,
            )
        )
    return chunks


def charger_cours(chemin: str | Path) -> Course:
    """Lire et valider un ``course.json`` (erreur Pydantic s'il ne suit pas le schéma T0)."""
    return Course.model_validate(json.loads(Path(chemin).read_text(encoding="utf-8")))


def indexer_cours(store: VectorStore, course: Course) -> int:
    """(Ré)indexer un cours : ses anciens chunks sont supprimés puis remplacés.

    Supprimer d'abord évite de garder des slides qui n'existent plus après une
    nouvelle ingestion. Renvoie le nombre de chunks indexés.
    """
    store.supprimer_cours(course.id)
    return store.ajouter(chunks_du_cours(course))


def fichiers_cours(chemin: str | Path = DOSSIER_PAR_DEFAUT) -> list[Path]:
    """Les ``course.json`` à indexer : le fichier donné, ou tous les ``<dossier>/*/course.json``."""
    chemin = Path(chemin)
    if chemin.is_file():
        return [chemin]
    return sorted(chemin.glob("*/course.json"))


def indexer_dossier(store: VectorStore, chemin: str | Path = DOSSIER_PAR_DEFAUT) -> dict[str, int]:
    """Indexer tous les cours d'un dossier (ou un seul fichier). Renvoie {course_id: nombre de chunks}."""
    resultat = {}
    for fichier in fichiers_cours(chemin):
        course = charger_cours(fichier)
        resultat[course.id] = indexer_cours(store, course)
    return resultat


def main(arguments: Sequence[str] | None = None) -> None:
    from rag.store import BgeM3Embedder, HashEmbedder

    parser = argparse.ArgumentParser(description="Indexer des course.json dans Qdrant (B2).")
    parser.add_argument(
        "chemins", nargs="*", default=[DOSSIER_PAR_DEFAUT],
        help="course.json ou dossiers contenant <course_id>/course.json (défaut : data/processed)",
    )
    parser.add_argument("--chemin", default=CHEMIN_PAR_DEFAUT, help="dossier Qdrant local")
    parser.add_argument("--url", default=None, help="serveur Qdrant (Docker), à la place de --chemin")
    parser.add_argument("--hash", action="store_true", help="embedder factice, sans modèle")
    args = parser.parse_args(arguments)

    # Collection séparée pour l'embedder factice : ses vecteurs n'ont pas la taille de ceux de bge-m3.
    collection = f"{NOM_COLLECTION}_hash" if args.hash else NOM_COLLECTION
    embedder = HashEmbedder() if args.hash else BgeM3Embedder()
    store = VectorStore(embedder, chemin=None if args.url else args.chemin, url=args.url, collection=collection)
    try:
        total = 0
        for chemin in args.chemins:
            for course_id, n in indexer_dossier(store, chemin).items():
                print(f"{course_id} : {n} chunks indexés")
                total += n
        if total == 0:
            print("Aucun course.json trouvé (attendu : <dossier>/<course_id>/course.json).")
        print(f"Total dans la collection '{collection}' : {store.compter()} chunks")
    finally:
        store.fermer()


if __name__ == "__main__":
    main()


__all__ = [
    "DOSSIER_PAR_DEFAUT",
    "charger_cours",
    "chunks_du_cours",
    "contenu_slide",
    "fichiers_cours",
    "indexer_cours",
    "indexer_dossier",
    "main",
    "resume_slide",
]
