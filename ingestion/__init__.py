"""Ingestion multimodale (Ghayth) : H1 parse → H2 VLM → H3 carte du cours.

Interfaces T0 (``docs/schema.md``) :

- ``parse_course(path, course_id=None) -> Course``  (H1, ``ingestion/parse.py``)
- ``enrich_with_vlm(course) -> Course``              (H2, ``ingestion/vlm.py``)
- ``build_course_map(course) -> Course``             (H3, ``ingestion/course_map.py``)
- ``get_prerequisites(slide_id) -> list[str]``       (H3)
- ``ingest(path) -> Course`` : les trois étapes à la suite (``ingestion/pipeline.py``).

Les imports sont paresseux : ``from ingestion import get_prerequisites`` ne charge ni PyMuPDF
ni le VLM.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "parse_course": "ingestion.parse",
    "charger_course": "ingestion.parse",
    "sauvegarder_course": "ingestion.parse",
    "enrich_with_vlm": "ingestion.vlm",
    "build_course_map": "ingestion.course_map",
    "get_prerequisites": "ingestion.course_map",
    "charger_carte": "ingestion.course_map",
    "ingest": "ingestion.pipeline",
}

__all__ = sorted(_EXPORTS)


def __getattr__(nom: str) -> Any:
    if nom in _EXPORTS:
        return getattr(import_module(_EXPORTS[nom]), nom)
    raise AttributeError(f"module 'ingestion' has no attribute {nom!r}")
