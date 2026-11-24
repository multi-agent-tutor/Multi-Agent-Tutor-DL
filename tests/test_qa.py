"""Tests B3 : agent Q&A avec citations, sans modèle (recherche factice ou HashEmbedder, LLM fake)."""

from __future__ import annotations

from typing import Any

import pytest

from agents import llm
from agents.graph import construire_graphe, executer
from agents.qa import AgentQA, construire_prompt, est_refus, nettoyer_citations, slides_citees
from eval.schema import REPONSE_HORS_COURS
from rag.index import indexer_cours
from rag.rerank import MotsCommunsReranker, RechercheReranked
from rag.search import RechercheHybride
from rag.store import HashEmbedder, VectorStore
from schemas.models import Chunk, Course, SearchHit, Slide, TutorState

COURS = "bd_test_fr"


def _hit(numero: int, contenu: str, score: float, titre: str = "") -> SearchHit:
    chunk = Chunk(id=f"{COURS}__s{numero:03d}", course_id=COURS, numero=numero, titre=titre,
                  contenu=contenu, langue="fr")
    return SearchHit(chunk=chunk, score=score)


class RechercheFixe:
    """Recherche factice : renvoie toujours les mêmes hits."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.appels: list[tuple[str, str | None]] = []

    def rechercher(self, requete: str, course_id: str | None = None, k: int | None = None) -> list[SearchHit]:
        self.appels.append((requete, course_id))
        return self.hits[: k or 5]


HITS = [
    _hit(2, "La clé primaire identifie de façon unique chaque n-uplet.", 0.92, "Clé primaire"),
    _hit(4, "Un SGBD gère une base de données partagée.", 0.55, "SGBD"),
    _hit(7, "La jointure combine deux relations.", 0.001, "Jointure"),  # sous le seuil
]


def _generer_fixe(texte: str):
    appels: list[dict[str, Any]] = []

    def generer(system: str, prompt: str, *, max_tokens: int) -> str:
        appels.append({"system": system, "prompt": prompt, "max_tokens": max_tokens})
        return texte

    generer.appels = appels  # type: ignore[attr-defined]
    return generer


def test_slides_citees_et_nettoyage():
    assert slides_citees("A [Slide 3]. B [slide 5] et [Slides 3, 8].") == [3, 5, 8]
    assert nettoyer_citations("A [Slide 2]. B [Slide 9]. C [Slides 2, 9].", {2}) == "A [Slide 2]. B. C [Slide 2]."
    assert est_refus("L'information n'est pas dans le cours.")
    assert not est_refus("La clé primaire identifie chaque n-uplet [Slide 2].")


def test_prompt_contient_les_passages_numerotes():
    prompt = construire_prompt("Qu'est-ce qu'une clé primaire ?", HITS[:2])
    assert "[Slide 2] — Clé primaire" in prompt and "[Slide 4] — SGBD" in prompt
    assert prompt.rstrip().endswith("Réponse :")


def test_reponse_citee_et_sources():
    generer = _generer_fixe("La clé primaire identifie chaque n-uplet [Slide 2].")
    agent = AgentQA(RechercheFixe(HITS), generer=generer)
    r = agent.repondre("Qu'est-ce qu'une clé primaire ?", COURS)
    assert r.agent == "qa"
    assert r.reponse == "La clé primaire identifie chaque n-uplet [Slide 2]."
    assert [(s.course_id, s.numero) for s in r.sources] == [(COURS, 2)]
    assert r.sources[0].extrait.startswith("La clé primaire")
    # le passage sous le seuil (slide 7) n'est pas envoyé au LLM
    assert "[Slide 7]" not in generer.appels[0]["prompt"]


def test_citation_inventee_retiree():
    agent = AgentQA(RechercheFixe(HITS), generer=_generer_fixe("Réponse [Slide 2]. Autre chose [Slide 42]."))
    r = agent.repondre("question", COURS)
    assert "[Slide 42]" not in r.reponse
    assert [s.numero for s in r.sources] == [2]


def test_sans_citation_on_rattache_au_meilleur_passage():
    agent = AgentQA(RechercheFixe(HITS), generer=_generer_fixe("Une clé primaire identifie chaque n-uplet."))
    r = agent.repondre("question", COURS)
    assert r.reponse.endswith("[Slide 2]")
    assert [s.numero for s in r.sources] == [2]


def test_refus_si_aucun_passage_pertinent_sans_appeler_le_llm():
    generer = _generer_fixe("ne doit pas être appelé")
    agent = AgentQA(RechercheFixe([HITS[2]]), generer=generer)
    r = agent.repondre("Quelle est la syntaxe SQL d'un index ?", COURS)
    assert r.reponse == REPONSE_HORS_COURS and r.sources == []
    assert generer.appels == []


def test_refus_formule_par_le_llm():
    agent = AgentQA(RechercheFixe(HITS), generer=_generer_fixe(f"« {REPONSE_HORS_COURS} »"))
    r = agent.repondre("question", COURS)
    assert r.reponse == REPONSE_HORS_COURS and r.sources == []


def test_repli_extractif_si_llm_indisponible():
    def en_panne(system: str, prompt: str, *, max_tokens: int) -> str:
        raise llm.LLMIndisponible("modèle absent")

    r = AgentQA(RechercheFixe(HITS), generer=en_panne).repondre("question", COURS)
    assert "[Slide 2]" in r.reponse and "clé primaire" in r.reponse
    assert [s.numero for s in r.sources] == [2]


def test_question_vide():
    r = AgentQA(RechercheFixe(HITS), generer=_generer_fixe("x")).repondre("   ", COURS)
    assert r.reponse == REPONSE_HORS_COURS


def test_branchement_dans_le_graphe():
    agent = AgentQA(RechercheFixe(HITS), generer=_generer_fixe("La clé primaire est unique [Slide 2]."))
    graphe = construire_graphe({"question": agent})
    final = executer(TutorState(course_id=COURS, slide_courante=1, question="Pourquoi une clé primaire ?"), graphe)
    assert final.reponse == "La clé primaire est unique [Slide 2]."
    assert [s.numero for s in final.sources] == [2]
    assert [m.role for m in final.historique] == ["utilisateur", "tuteur"]
    # les autres intentions restent des bouchons
    assert executer(TutorState(course_id=COURS, slide_courante=1, question="Un quiz"), graphe).reponse.startswith("[quiz]")


def test_bout_en_bout_rag_et_llm_fake(monkeypatch: pytest.MonkeyPatch):
    """B1 + B2 + A0 (fake) + B3 : indexation, recherche, reranking, réponse citée."""
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.setenv("LLM_FAKE_REPONSE", "Elle identifie chaque n-uplet [Slide 2].")
    llm.reinitialiser()
    slides = [
        Slide(id=f"{COURS}__s001", course_id=COURS, numero=1, titre="Introduction", texte="Plan du cours."),
        Slide(id=f"{COURS}__s002", course_id=COURS, numero=2, titre="Clé primaire",
              texte="La clé primaire identifie chaque n-uplet d'une relation."),
        Slide(id=f"{COURS}__s003", course_id=COURS, numero=3, titre="SGBD", texte="Un SGBD gère une base."),
    ]
    store = VectorStore(HashEmbedder())
    indexer_cours(store, Course(id=COURS, titre="BD", fichier_source="x.pdf", format="pdf", langue="fr",
                                nombre_slides=3, slides=slides))
    agent = AgentQA(RechercheReranked(RechercheHybride(store), MotsCommunsReranker()))

    r = agent.repondre("Qu'est-ce qu'une clé primaire ?", COURS)
    assert r.reponse == "Elle identifie chaque n-uplet [Slide 2]."
    assert [s.numero for s in r.sources] == [2]
    assert agent.repondre("Quel temps fera-t-il demain ?", COURS).reponse == REPONSE_HORS_COURS
    store.fermer()
