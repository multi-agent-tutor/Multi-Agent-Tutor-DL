"""A1 / A3 — API FastAPI du tuteur, branchée sur le graphe multi-agent (``api/graphe.py``).

- ``GET /slide/{id}/explain`` et ``POST /ask`` passent par le graphe LangGraph (O1) : Explainer (O2),
  Q&A (B3, bouchon tant qu'il n'est pas mergé), Quiz vérifié, Resources, boucle Critic (O3).
  Avec ``?stream=1`` ou ``Accept: text/event-stream``, réponse en SSE (progression puis réponse).
- ``GET /quiz`` : QCM de l'agent Quiz (A2) filtrés par le Critic (O3).
- ``GET /resources`` (A4), ``GET /flashcards`` (A2), ``/flashcards/save|due|export`` et
  ``/flashcards/{id}/review`` (SM-2, A6) : inchangés.
- Upload : cours d'exemple ``schemas/exemples/exemple_cours.json`` (ingestion non branchée).
- 504 si le LLM local dépasse ``API_TIMEOUT_LLM`` secondes (400 par défaut).

Lancement : ``uvicorn api.main:app --reload`` puis http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi import Path as PathParam
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agents import llm, srs
from agents.quiz import brancher_cours, charger_cours, generer_flashcards
from agents.resources import charger_slide, chercher_ressources
from api import graphe as tuteur
from api.models import (
    QCM,
    AskRequest,
    CarteSRS,
    Flashcard,
    NiveauBloom,
    Ressource,
    ReviewRequest,
    SaveFlashcardsRequest,
)
from schemas.models import (
    COURSE_ID_PATTERN,
    SLIDE_ID_PATTERN,
    AgentResponse,
    Course,
    Langue,
    Niveau,
    Slide,
    Source,
    TutorState,
)

log = logging.getLogger("api")
if not log.handlers:  # visible sous uvicorn, qui ne configure que ses propres loggers
    _sortie = logging.StreamHandler()
    _sortie.setFormatter(logging.Formatter("%(levelname)s:     [api] %(message)s"))
    log.addHandler(_sortie)
    log.setLevel(logging.INFO)

EXEMPLE_COURS = Path(__file__).resolve().parent.parent / "schemas" / "exemples" / "exemple_cours.json"
EXTENSIONS_ACCEPTEES = {".pdf": "pdf", ".pptx": "pptx"}

# Origines du frontend en développement (Vite, CRA, Streamlit, page depot.html servie sur 8765).
ORIGINES_FRONTEND = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8501",
    "http://localhost:8765",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8501",
    "http://127.0.0.1:8765",
]


def charger_cours_exemple() -> Course:
    """Charger et valider le cours factice."""
    return Course.model_validate(json.loads(EXEMPLE_COURS.read_text(encoding="utf-8")))


COURS: dict[str, Course] = {}
_exemple = charger_cours_exemple()
COURS[_exemple.id] = _exemple
brancher_cours(COURS.get)  # l'agent Quiz (A2) voit les cours chargés par l'API

app = FastAPI(
    title="Tuteur multi-agent — API",
    version="0.1.0",
    description="API du tuteur (A1/A3) : agents multi-agent sur LLM local, cours d'exemple.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINES_FRONTEND,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lisibles par le frontend (A5) : raison d'un quiz vide, nom du fichier Anki exporté.
    expose_headers=["X-Quiz-Message", "Content-Disposition", "X-Temps-Reponse"],
)


@app.middleware("http")
async def temps_de_reponse(request: Request, appel_suivant):  # type: ignore[no-untyped-def]
    """Loguer le temps de réponse de chaque route (jusqu'aux en-têtes pour un flux SSE)."""
    debut = time.perf_counter()
    reponse = await appel_suivant(request)
    duree = time.perf_counter() - debut
    reponse.headers["X-Temps-Reponse"] = f"{duree:.3f}"
    log.info("%s %s -> %d en %.2f s", request.method, request.url.path, reponse.status_code, duree)
    return reponse


def _cours(course_id: str) -> Course:
    cours = COURS.get(course_id)
    if cours is None:
        raise HTTPException(status_code=404, detail=f"Cours inconnu : {course_id}")
    return cours


def _slide(course_id: str, numero: int) -> Slide:
    cours = _cours(course_id)
    if not 1 <= numero <= cours.nombre_slides:
        raise HTTPException(
            status_code=404,
            detail=f"Slide {numero} hors limites (1..{cours.nombre_slides}) pour {course_id}",
        )
    return cours.slides[numero - 1]


def _slide_par_id(slide_id: str) -> Slide:
    course_id, _, numero = slide_id.rpartition("__s")
    return _slide(course_id, int(numero))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload", response_model=Course)
async def upload(fichier: UploadFile = File(...)) -> Course:
    """Recevoir un PDF/PPTX et renvoyer un cours factice (ingestion non branchée)."""
    extension = Path(fichier.filename or "").suffix.lower()
    if extension not in EXTENSIONS_ACCEPTEES:
        raise HTTPException(status_code=415, detail="Seuls les fichiers PDF et PPTX sont acceptés")
    await fichier.read()  # Le contenu sera transmis à l'ingestion (H1).
    return _cours(_exemple.id)


@app.get("/course/{course_id}", response_model=Course)
def get_course(course_id: str) -> Course:
    return _cours(course_id)


# --------------------------------------------------------------------------- agents texte (A3)


def _veut_flux(stream: bool, accept: str | None) -> bool:
    return stream or "text/event-stream" in (accept or "").lower()


def _repli(state: TutorState, motif: str) -> AgentResponse:
    """Réponse de secours (LLM indisponible ou trop lent) : le texte de la slide, cité."""
    cours = charger_cours(state.course_id)
    slide = cours.slides[state.slide_courante - 1] if cours else None
    contenu = (slide.texte or slide.titre).strip() if slide else ""
    agent = "explainer" if state.intention == "expliquer" else "qa"
    return AgentResponse(
        agent=agent,
        reponse=f"{motif}\n\nContenu de la slide : {contenu} [Slide {state.slide_courante}]",
        sources=[Source(course_id=state.course_id, numero=state.slide_courante, extrait=contenu[:300])],
    )


MOTIF_INDISPONIBLE = "Le modèle local est indisponible pour le moment."
MOTIF_DELAI = "Le modèle local a mis trop de temps à répondre ({s:.0f} s)."
NON_VERIFIEE: dict[str, str] = {
    "fr": "⚠ Réponse non vérifiée par le Critic (délai dépassé) : contrôle-la sur les slides citées.",
    "en": "⚠ Answer not checked by the Critic (timeout): check it against the cited slides.",
    "ar": "⚠ لم يتحقق المراجع من هذه الإجابة (انتهت المهلة): راجعها في الشرائح المذكورة.",
}


def _secours_delai(state: TutorState, erreur: tuteur.DelaiDepasse) -> AgentResponse:
    """Brouillon de l'agent (délai tombé pendant le Critic) avec avertissement, sinon texte de la slide."""
    if erreur.brouillon is not None and erreur.brouillon.reponse.strip():
        note = NON_VERIFIEE.get(state.langue_reponse, NON_VERIFIEE["fr"])
        reponse = f"{erreur.brouillon.reponse}\n\n{note}"
        return erreur.brouillon.model_copy(update={"reponse": reponse, "score_fidelite": None})
    return _repli(state, MOTIF_DELAI.format(s=tuteur.timeout_llm()))


def _sse(donnees: dict | str, evenement: str | None = None) -> str:
    """Un événement SSE ; ``frontend/src/api.ts`` (lireReponseAgent) ne lit que les lignes ``data:``."""
    corps = donnees if isinstance(donnees, str) else json.dumps(donnees, ensure_ascii=False)
    tete = f"event: {evenement}\n" if evenement else ""
    return f"{tete}data: {corps}\n\n"


async def _flux(state: TutorState, route: str) -> AsyncIterator[str]:
    """Flux SSE : ``event: progression`` (JSON sans ``token`` ni ``reponse``, ignoré du texte
    affiché), ``: ping`` toutes les 15 s, puis l'``AgentResponse`` final et ``[DONE]``.
    En cas d'erreur : ``event: erreur`` ({statut, detail}) puis une réponse de secours."""
    debut = time.perf_counter()
    try:
        async for ev in tuteur.executer_avec_progression(state):
            if ev is None:
                yield ": ping\n\n"
            elif ev.reponse is not None:
                yield _sse(ev.reponse.model_dump(mode="json"))
            else:
                yield _sse({"etape": ev.etape, "message": tuteur.MESSAGES_ETAPES.get(ev.etape, ""),
                            **ev.donnees}, "progression")
    except tuteur.DelaiDepasse as e:
        log.warning("%s : %s", route, e)
        yield _sse({"statut": 504, "detail": str(e)}, "erreur")
        yield _sse(_secours_delai(state, e).model_dump(mode="json"))
    except llm.LLMIndisponible as e:
        log.warning("%s : LLM indisponible : %s", route, e)
        yield _sse({"statut": 503, "detail": str(e)}, "erreur")
        yield _sse(_repli(state, MOTIF_INDISPONIBLE).model_dump(mode="json"))
    yield _sse("[DONE]")
    log.info("%s (SSE) terminé en %.2f s", route, time.perf_counter() - debut)


async def _repondre(state: TutorState, route: str, flux: bool) -> Response:
    if flux:
        return StreamingResponse(
            _flux(state, route),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    debut = time.perf_counter()
    try:
        reponse = await tuteur.executer_tour(state)
    except tuteur.DelaiDepasse as e:
        log.warning("%s : %s", route, e)
        raise HTTPException(status_code=504, detail=str(e)) from e
    except llm.LLMIndisponible as e:
        log.warning("%s : LLM indisponible : %s", route, e)
        reponse = _repli(state, MOTIF_INDISPONIBLE)
    log.info("%s : graphe en %.2f s (agent %s)", route, time.perf_counter() - debut, reponse.agent)
    return JSONResponse(reponse.model_dump(mode="json"))


DESCRIPTION_FLUX = "Réponse SSE (text/event-stream) : progression puis AgentResponse final"


@app.get("/slide/{slide_id}/explain", response_model=AgentResponse)
async def explain(
    slide_id: Annotated[str, PathParam(pattern=SLIDE_ID_PATTERN)],
    niveau: Niveau = "intermediaire",
    langue: Langue | None = None,
    stream: Annotated[bool, Query(description=DESCRIPTION_FLUX)] = False,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """Explication de la slide par l'Explainer (O2), vérifiée par le Critic (O3)."""
    course_id, _, numero = slide_id.rpartition("__s")
    cours = _verifier_cible(course_id, int(numero))
    state = TutorState(
        course_id=course_id,
        slide_courante=int(numero),
        niveau=niveau,
        langue_reponse=langue or cours.langue,
        intention="expliquer",
    )
    return await _repondre(state, "explain", _veut_flux(stream, accept))


@app.post("/ask", response_model=AgentResponse)
async def ask(
    requete: AskRequest,
    stream: Annotated[bool, Query(description=DESCRIPTION_FLUX)] = False,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """Question de l'étudiant : le router du graphe choisit l'agent (Q&A, Explainer, Quiz, Resources)."""
    _verifier_cible(requete.course_id, requete.slide_courante)
    state = TutorState(
        course_id=requete.course_id,
        slide_courante=requete.slide_courante,
        niveau=requete.niveau,
        langue_reponse=requete.langue,
        question=requete.question,
        historique=requete.historique,
    )
    return await _repondre(state, "ask", _veut_flux(stream, accept))


@app.get("/quiz", response_model=list[QCM])
async def quiz(
    response: Response,
    course_id: str,
    slide: Annotated[int | None, Query(ge=1)] = None,
    n: Annotated[int, Query(ge=1, le=10)] = 3,
    niveau_bloom: NiveauBloom | None = None,
    langue: Langue | None = None,
) -> list[QCM]:
    """QCM de l'agent Quiz (A2) vérifiés par le Critic (O3), sur une slide ou tout le cours.

    Liste vide (et en-tête ``X-Quiz-Message``) si le LLM local est indisponible ou si aucun QCM
    ne passe la vérification ; 504 au-delà de ``API_TIMEOUT_LLM``.
    """
    _verifier_cible(course_id, slide)
    try:
        resultat = await asyncio.wait_for(
            run_in_threadpool(tuteur.quiz_verifie, course_id, slide, n, niveau_bloom, langue),
            tuteur.timeout_llm(),
        )
    except asyncio.TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"le modèle local n'a pas répondu en "
                                                    f"{tuteur.timeout_llm():.0f} s") from e
    if resultat.message:
        response.headers["X-Quiz-Message"] = quote(resultat.message)
    return resultat.qcm


@app.get("/flashcards", response_model=list[Flashcard])
def flashcards(
    course_id: str,
    slide: Annotated[int | None, Query(ge=1)] = None,
    n: Annotated[int, Query(ge=1, le=10)] = 5,
    langue: Langue | None = None,
) -> list[Flashcard]:
    """Flashcards de l'agent Quiz (A2) ; sans LLM, une carte titre → texte par slide."""
    _verifier_cible(course_id, slide)
    return generer_flashcards(course_id, slide, n, langue=langue)


UtilisateurQuery = Annotated[str, Query(min_length=1, max_length=100)]


@app.post("/flashcards/save", response_model=list[CarteSRS])
def flashcards_save(requete: SaveFlashcardsRequest) -> list[CarteSRS]:
    """Mémoriser des flashcards (A2) pour un utilisateur (A6) ; une carte connue n'est pas dupliquée."""
    return srs.ajouter_cartes(requete.user, requete.flashcards)


@app.get("/flashcards/due", response_model=list[CarteSRS])
def flashcards_due(
    user: UtilisateurQuery,
    date_revision: Annotated[date | None, Query(alias="date")] = None,
    course_id: Annotated[str | None, Query(pattern=COURSE_ID_PATTERN)] = None,
) -> list[CarteSRS]:
    """Cartes de l'utilisateur à réviser au plus tard à ``date`` (défaut : aujourd'hui)."""
    return srs.cartes_a_reviser(user, date_revision, course_id)


@app.post("/flashcards/{carte_id}/review", response_model=CarteSRS)
def flashcards_review(carte_id: int, requete: ReviewRequest) -> CarteSRS:
    """Noter une révision (``qualite`` 0..5) et replanifier la carte selon SM-2."""
    try:
        return srs.enregistrer_revision(requete.user, carte_id, requete.qualite)
    except KeyError as erreur:
        raise HTTPException(status_code=404, detail=erreur.args[0]) from erreur


@app.get("/flashcards/export")
def flashcards_export(
    course_id: Annotated[str, Query(pattern=COURSE_ID_PATTERN)],
    user: UtilisateurQuery,
) -> Response:
    """Télécharger le deck Anki (.apkg) des cartes de l'utilisateur pour un cours."""
    try:
        contenu = srs.exporter_apkg(user, course_id)
    except LookupError as erreur:
        raise HTTPException(status_code=404, detail=erreur.args[0]) from erreur
    return Response(
        content=contenu,
        media_type="application/apkg",
        headers={"Content-Disposition": f'attachment; filename="{course_id}.apkg"'},
    )


def _verifier_cible(course_id: str, slide: int | None) -> Course:
    """404 si le cours (API, ``data/processed`` ou exemple) ou la slide n'existe pas."""
    cours = charger_cours(course_id)
    if cours is None:
        raise HTTPException(status_code=404, detail=f"Cours inconnu : {course_id}")
    if slide is not None and not 1 <= slide <= cours.nombre_slides:
        raise HTTPException(
            status_code=404,
            detail=f"Slide {slide} hors limites (1..{cours.nombre_slides}) pour {course_id}",
        )
    return cours


@app.get("/resources", response_model=list[Ressource])
def resources(
    slide_id: Annotated[str, Query(pattern=SLIDE_ID_PATTERN)],
    niveau: Niveau = "intermediaire",
    langue: Langue = "fr",
) -> list[Ressource]:
    """Ressources externes pour une slide (A4) : catalogue local, sans appel réseau."""
    s = _slide_par_id(slide_id)
    state = TutorState(course_id=s.course_id, slide_courante=s.numero, niveau=niveau, langue_reponse=langue)
    return chercher_ressources(state, charger=_slide_connue)


def _slide_connue(course_id: str, numero: int) -> Slide | None:
    """Slide d'un cours chargé par l'API, sinon d'un cours ingéré dans ``data/processed``."""
    cours = COURS.get(course_id)
    if cours is not None and 1 <= numero <= cours.nombre_slides:
        return cours.slides[numero - 1]
    return charger_slide(course_id, numero)
