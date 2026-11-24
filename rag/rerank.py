"""B2 — Reranking des candidats de la recherche hybride avec bge-reranker.

La recherche hybride (B1) ramène 20 candidats ; le reranker (un cross-encoder, qui lit
la question et la slide ensemble) les reclasse plus finement et on garde les 5 meilleurs.

    from rag.rerank import BgeReranker, RechercheReranked
    pipeline = RechercheReranked(recherche_hybride, BgeReranker())
    hits = pipeline.rechercher("Qu'est-ce qu'une clé primaire ?", course_id="...")  # top-5

Le score des ``SearchHit`` renvoyés est alors le score du reranker, entre 0 et 1 :
B3 peut s'en servir comme seuil (« l'information n'est pas dans le cours »).

Modèle par défaut : BAAI/bge-reranker-v2-m3 (multilingue, local, ~2,2 Go au premier usage).
``MotsCommunsReranker`` le remplace dans les tests : il ne télécharge rien.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from rag.search import RechercheHybride
from rag.store import texte_a_encoder, tokeniser
from schemas.models import SearchHit

MODELE_RERANKER = "BAAI/bge-reranker-v2-m3"
K_CANDIDATS = 20
K_FINAL = 5


class Reranker(Protocol):
    """Interface commune : un score de pertinence par texte, pour une même requête."""

    def scorer(self, requete: str, textes: Sequence[str]) -> list[float]:
        ...


class BgeReranker:
    """Cross-encoder bge-reranker via sentence-transformers (scores entre 0 et 1)."""

    def __init__(self, nom_modele: str = MODELE_RERANKER, device: str | None = None,
                 batch_size: int = 16, max_length: int = 512) -> None:
        self.nom_modele = nom_modele
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        self._modele = None

    def _charger(self):
        if self._modele is None:
            from sentence_transformers import CrossEncoder  # import lourd : à la demande

            self._modele = CrossEncoder(self.nom_modele, device=self.device, max_length=self.max_length)
        return self._modele

    def scorer(self, requete: str, textes: Sequence[str]) -> list[float]:
        if not textes:
            return []
        import torch

        scores = self._charger().predict(
            [(requete, t) for t in textes],
            batch_size=self.batch_size,
            activation_fn=torch.nn.Sigmoid(),  # logits -> probabilité de pertinence (0..1)
        )
        return [float(s) for s in scores]


class MotsCommunsReranker:
    """Reranker factice pour les tests : part des mots de la requête présents dans le texte."""

    def scorer(self, requete: str, textes: Sequence[str]) -> list[float]:
        mots = set(tokeniser(requete))
        if not mots:
            return [0.0 for _ in textes]
        return [len(mots & set(tokeniser(t))) / len(mots) for t in textes]


def reranker(reranker: Reranker, requete: str, hits: Sequence[SearchHit], top: int = K_FINAL) -> list[SearchHit]:
    """Reclasser des hits avec le reranker et garder les ``top`` meilleurs (score = score du reranker)."""
    if not hits:
        return []
    scores = reranker.scorer(requete, [texte_a_encoder(h.chunk) for h in hits])
    reclasses = sorted(zip(hits, scores, strict=True), key=lambda p: (-p[1], p[0].chunk.id))
    return [SearchHit(chunk=h.chunk, score=s) for h, s in reclasses[:top]]


class RechercheReranked:
    """Pipeline complet B1 + B2 : hybride (top-20) puis reranker (top-5)."""

    def __init__(self, recherche: RechercheHybride, modele: Reranker,
                 k_candidats: int = K_CANDIDATS, k_final: int = K_FINAL) -> None:
        self.recherche = recherche
        self.modele = modele
        self.k_candidats = k_candidats
        self.k_final = k_final

    def rechercher(self, requete: str, course_id: str | None = None, k: int | None = None) -> list[SearchHit]:
        candidats = self.recherche.rechercher(
            requete, k=self.k_candidats, course_id=course_id, k_candidats=self.k_candidats
        )
        return reranker(self.modele, requete, candidats, top=k or self.k_final)


__all__ = [
    "BgeReranker",
    "K_CANDIDATS",
    "K_FINAL",
    "MODELE_RERANKER",
    "MotsCommunsReranker",
    "RechercheReranked",
    "Reranker",
    "reranker",
]


def _demo() -> None:
    """python -m rag.rerank "ma question" [--hash] : hybride puis reranking sur les chunks de démo de B1."""
    import argparse

    from rag.search import _chunks_exemple
    from rag.store import BgeM3Embedder, HashEmbedder, VectorStore

    parser = argparse.ArgumentParser(description="Démo du reranking (B2).")
    parser.add_argument("question")
    parser.add_argument("--hash", action="store_true", help="modèles factices, sans téléchargement")
    args = parser.parse_args()

    store = VectorStore(HashEmbedder() if args.hash else BgeM3Embedder())
    store.ajouter(_chunks_exemple())
    pipeline = RechercheReranked(RechercheHybride(store), MotsCommunsReranker() if args.hash else BgeReranker(), k_final=3)
    for h in pipeline.rechercher(args.question):
        print(f"  {h.score:.3f}  {h.chunk.id}  {h.chunk.titre}")


if __name__ == "__main__":
    _demo()
