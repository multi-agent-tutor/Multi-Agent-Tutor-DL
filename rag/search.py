"""B1 — Recherche hybride : dense (Qdrant) + lexicale (BM25), fusionnées par RRF.

Utilisation :

    from rag.store import VectorStore, BgeM3Embedder
    from rag.search import RechercheHybride

    store = VectorStore(BgeM3Embedder(), chemin="qdrant_storage")
    store.ajouter(chunks)                     # chunks au format schemas.models.Chunk
    recherche = RechercheHybride(store)
    hits = recherche.rechercher("Qu'est-ce qu'une clé primaire ?", k=5, course_id="...")
    # -> list[SearchHit], du plus pertinent au moins pertinent

Pourquoi l'hybride : la recherche dense comprend les reformulations et les autres
langues ; BM25 retrouve les termes exacts (sigles, noms propres, formules) que
les embeddings ratent parfois. La fusion RRF combine les deux classements sans
avoir à rendre leurs scores comparables.

B2 ajoutera le reranker sur les candidats de ``rechercher`` ; B4 compare la
version « avant » (``dense`` seul) et la version « après » (hybride + reranker).

Démo :  python -m rag.search "ma question"          (modèle bge-m3)
        python -m rag.search "ma question" --hash   (sans modèle, pour tester)
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from collections.abc import Sequence

from rag.store import VectorStore, tokeniser
from schemas.models import Chunk, SearchHit

K_RRF = 60  # constante habituelle de la Reciprocal Rank Fusion (Cormack et al., 2009)


class BM25:
    """BM25 Okapi sur les chunks (titre + contenu), filtrable par cours."""

    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks = list(chunks)
        self._docs = [Counter(tokeniser(f"{c.titre} {c.contenu}")) for c in self.chunks]
        self._longueurs = [sum(d.values()) for d in self._docs]
        n = len(self.chunks)
        self._longueur_moyenne = (sum(self._longueurs) / n) if n else 0.0
        frequences_doc: Counter[str] = Counter()
        for doc in self._docs:
            frequences_doc.update(doc.keys())
        self._idf = {
            mot: math.log((n - df + 0.5) / (df + 0.5) + 1.0) for mot, df in frequences_doc.items()
        }

    def score(self, mots_requete: Sequence[str], indice: int) -> float:
        """Score BM25 d'un chunk pour une requête déjà tokenisée."""
        doc = self._docs[indice]
        longueur = self._longueurs[indice]
        total = 0.0
        for mot in mots_requete:
            tf = doc.get(mot, 0)
            if not tf:
                continue
            norme = self.k1 * (1 - self.b + self.b * longueur / (self._longueur_moyenne or 1.0))
            total += self._idf[mot] * tf * (self.k1 + 1) / (tf + norme)
        return total

    def rechercher(
        self, requete: str, k: int = 20, course_id: str | None = None
    ) -> list[tuple[Chunk, float]]:
        """Les ``k`` chunks au meilleur score BM25 (score > 0 uniquement)."""
        mots = tokeniser(requete)
        if not mots:
            return []
        resultats = []
        for i, chunk in enumerate(self.chunks):
            if course_id is not None and chunk.course_id != course_id:
                continue
            s = self.score(mots, i)
            if s > 0:
                resultats.append((chunk, s))
        resultats.sort(key=lambda r: (-r[1], r[0].id))
        return resultats[:k]


def fusion_rrf(
    classements: Sequence[Sequence[Chunk]], k_rrf: int = K_RRF
) -> list[tuple[Chunk, float]]:
    """Reciprocal Rank Fusion : score(c) = somme sur les classements de 1 / (k_rrf + rang).

    Le rang commence à 1. Un chunk absent d'un classement n'y gagne rien.
    Renvoie tous les chunks rencontrés, du meilleur score au moins bon.
    """
    scores: dict[str, float] = {}
    par_id: dict[str, Chunk] = {}
    for classement in classements:
        for rang, chunk in enumerate(classement, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k_rrf + rang)
            par_id.setdefault(chunk.id, chunk)
    ordre = sorted(scores, key=lambda cid: (-scores[cid], cid))
    return [(par_id[cid], scores[cid]) for cid in ordre]


class RechercheHybride:
    """Recherche dense + BM25 fusionnées par RRF, au-dessus d'un ``VectorStore``.

    L'index BM25 est construit à partir des chunks du store au premier appel.
    Après avoir ajouté ou supprimé des chunks, appeler ``rafraichir()``.
    """

    def __init__(self, store: VectorStore, k_rrf: int = K_RRF) -> None:
        self.store = store
        self.k_rrf = k_rrf
        self._bm25: BM25 | None = None

    def rafraichir(self) -> None:
        """Reconstruire l'index BM25 depuis le contenu actuel du store."""
        self._bm25 = BM25(self.store.tous_les_chunks())

    @property
    def bm25(self) -> BM25:
        if self._bm25 is None:
            self.rafraichir()
        return self._bm25

    def dense(self, requete: str, k: int = 5, course_id: str | None = None) -> list[SearchHit]:
        """Recherche dense seule (version « avant » de B4)."""
        return [
            SearchHit(chunk=c, score=s) for c, s in self.store.rechercher(requete, k, course_id)
        ]

    def lexicale(self, requete: str, k: int = 5, course_id: str | None = None) -> list[SearchHit]:
        """Recherche BM25 seule (utile pour comparer et déboguer)."""
        return [SearchHit(chunk=c, score=s) for c, s in self.bm25.rechercher(requete, k, course_id)]

    def rechercher(
        self, requete: str, k: int = 5, course_id: str | None = None, k_candidats: int = 20
    ) -> list[SearchHit]:
        """Recherche hybride : ``k_candidats`` de chaque côté, fusion RRF, ``k`` meilleurs.

        Pour B2, demander ``k=20`` puis reranker et garder les 5 premiers.
        """
        denses = [c for c, _ in self.store.rechercher(requete, k_candidats, course_id)]
        lexicaux = [c for c, _ in self.bm25.rechercher(requete, k_candidats, course_id)]
        fusion = fusion_rrf([denses, lexicaux], self.k_rrf)
        return [SearchHit(chunk=c, score=s) for c, s in fusion[:k]]


def _chunks_exemple() -> list[Chunk]:
    """Petits chunks factices au format T0 (FR et EN), pour la démo."""
    donnees = [
        ("bd_intro_fr", 1, "fr", "Clé primaire", "La clé primaire identifie de façon unique chaque n-uplet d'une relation."),
        ("bd_intro_fr", 2, "fr", "Jointure", "La jointure naturelle combine deux relations sur leurs attributs communs."),
        ("bd_intro_fr", 3, "fr", "SGBD", "Un SGBD est un logiciel qui gère une base de données partagée."),
        ("cloud_intro_en", 1, "en", "Hypervisor", "A hypervisor (VMM) runs several virtual machines on one physical server."),
        ("cloud_intro_en", 2, "en", "Live migration", "Live migration moves a running VM to another host without downtime."),
        ("cloud_intro_en", 3, "en", "Elasticity", "Rapid elasticity lets resources scale out and in with demand."),
    ]
    return [
        Chunk(id=f"{cid}__s{n:03d}", course_id=cid, numero=n, titre=t, contenu=c, langue=lang)
        for cid, n, lang, t, c in donnees
    ]


def _demo() -> None:
    from rag.store import BgeM3Embedder, HashEmbedder

    parser = argparse.ArgumentParser(description="Démo de la recherche hybride (B1).")
    parser.add_argument("question")
    parser.add_argument("--hash", action="store_true", help="embedder factice, sans modèle")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    store = VectorStore(HashEmbedder() if args.hash else BgeM3Embedder())
    store.ajouter(_chunks_exemple())
    recherche = RechercheHybride(store)
    for titre, hits in [
        ("Dense", recherche.dense(args.question, args.k)),
        ("BM25", recherche.lexicale(args.question, args.k)),
        ("Hybride (RRF)", recherche.rechercher(args.question, args.k)),
    ]:
        print(f"\n== {titre}")
        for h in hits:
            print(f"  {h.score:.4f}  {h.chunk.id}  {h.chunk.titre}")


if __name__ == "__main__":
    _demo()


__all__ = ["BM25", "K_RRF", "RechercheHybride", "fusion_rrf"]
