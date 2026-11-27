"""Pipeline d'ingestion complet : H1 (parse) → H2 (VLM) → H3 (carte du cours).

Usage : ``python -m ingestion <fichier|dossier> [...] [--sans-vlm] [--sans-llm] [--texte-brut]``.
Sortie : ``data/processed/<course_id>/course.json`` + ``course_map.json`` + rendus PNG.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from schemas import Course

from ingestion.course_map import build_course_map
from ingestion.parse import _fichiers, parse_course
from ingestion.vlm import enrich_with_vlm
from ingestion.vlm import est_configure as vlm_configure

log = logging.getLogger(__name__)


def ingest(path: Path | str, course_id: str | None = None, *, vlm: bool = True, llm: bool | None = None,
           texte_brut: bool = False, dossier_sortie: Path | None = None) -> Course:
    """Ingérer un cours de bout en bout et renvoyer le ``Course`` final (aussi écrit sur disque).

    - ``vlm`` : lancer H2 si le VLM est configuré (sinon H2 est sauté avec un avertissement) ;
    - ``llm`` : ``None`` = LLM pour H3 s'il est configuré, ``False`` = heuristique ;
    - ``texte_brut`` : H1 rapide (ni rendu, ni OCR, ni images), donc pas de H2.
    """
    course = parse_course(path, course_id, dossier_sortie=dossier_sortie, rendu=not texte_brut,
                          ocr=not texte_brut, extraire_images=not texte_brut)
    dossier = Path(dossier_sortie) if dossier_sortie else None
    if vlm and not texte_brut:
        if vlm_configure():
            course = enrich_with_vlm(course, dossier=dossier)
        else:
            log.warning("VLM non configuré : H2 sauté (voir ingestion/README.md)")
    return build_course_map(course, dossier=dossier, utiliser_llm=llm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingestion complète H1 → H2 → H3")
    parser.add_argument("cibles", nargs="+", type=Path, help="fichiers .pdf/.pptx ou dossiers")
    parser.add_argument("--sans-vlm", action="store_true", help="sauter H2")
    parser.add_argument("--sans-llm", action="store_true", help="H3 en mode heuristique")
    parser.add_argument("--texte-brut", action="store_true", help="H1 rapide (texte seul), sans H2")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    erreurs = 0
    for fichier in _fichiers(args.cibles):
        debut = time.perf_counter()
        try:
            course = ingest(fichier, vlm=not args.sans_vlm, llm=False if args.sans_llm else None,
                            texte_brut=args.texte_brut)
        except Exception as e:  # noqa: BLE001
            erreurs += 1
            print(f"ÉCHEC {fichier} : {e}")
            continue
        figures = sum(len(s.description_figures) for s in course.slides)
        formules = sum(len(s.formules_latex) for s in course.slides)
        concepts = len({c for s in course.slides for c in s.concepts})
        print(f"{course.id}: {course.nombre_slides} slides, {figures} figures, {formules} formules, "
              f"{concepts} concepts, {time.perf_counter() - debut:.0f}s")
    return 1 if erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main())
