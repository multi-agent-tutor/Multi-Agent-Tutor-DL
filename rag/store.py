"""B1 — Stockage vectoriel des chunks (Qdrant) et modèle d'embeddings.

Un chunk (``schemas.models.Chunk``) est encodé en un vecteur dense et rangé dans
une collection Qdrant, avec tout le chunk en payload. Trois modes de connexion :

- en mémoire (par défaut, pour les tests) : ``VectorStore(embedder)``
- sur disque, sans Docker : ``VectorStore(embedder, chemin="qdrant_storage")``
- serveur Docker : ``VectorStore(embedder, url="http://localhost:6333")``
  (``docker run -p 6333:6333 qdrant/qdrant``)

Le modèle d'embeddings par défaut est bge-m3 (multilingue, 1024 dimensions).
``HashEmbedder`` le remplace dans les tests : il ne télécharge rien.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from collections.abc import Sequence
from typing import Protocol

from qdrant_client import QdrantClient, models

from schemas.models import Chunk

NOM_COLLECTION = "slides"
MODELE_EMBEDDINGS = "BAAI/bge-m3"
CHEMIN_PAR_DEFAUT = "qdrant_storage"  # déjà ignoré par .gitignore


def tokeniser(texte: str) -> list[str]:
    """Découper un texte en mots minuscules sans accents (FR/EN).

    Utilisé par ``HashEmbedder`` et par la recherche BM25 de ``rag.search``.
    """
    sans_accents = unicodedata.normalize("NFKD", texte.lower())
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", sans_accents)


def texte_a_encoder(chunk: Chunk) -> str:
    """Texte d'un chunk donné au modèle d'embeddings : titre puis contenu."""
    return f"{chunk.titre}\n{chunk.contenu}".strip()


def point_id(chunk_id: str) -> str:
    """Identifiant Qdrant stable (UUID) dérivé de l'id du chunk.

    Qdrant n'accepte que des entiers ou des UUID : on dérive un UUID fixe de
    ``<course_id>__sNNN``, si bien qu'indexer deux fois la même slide la remplace.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class Embedder(Protocol):
    """Interface commune des modèles d'embeddings."""

    dimension: int

    def encoder(self, textes: Sequence[str]) -> list[list[float]]:
        """Renvoyer un vecteur normalisé par texte."""
        ...


class BgeM3Embedder:
    """Embeddings denses bge-m3 via sentence-transformers.

    Le modèle (~2,3 Go) est téléchargé au premier appel de ``encoder`` puis mis en
    cache par Hugging Face. Les vecteurs sont normalisés : la similarité cosinus
    de Qdrant revient alors au produit scalaire.
    """

    dimension = 1024

    def __init__(
        self, nom_modele: str = MODELE_EMBEDDINGS, device: str | None = None, batch_size: int = 16
    ) -> None:
        self.nom_modele = nom_modele
        self.device = device
        self.batch_size = batch_size
        self._modele = None

    def _charger(self):
        if self._modele is None:
            from sentence_transformers import SentenceTransformer  # import lourd : à la demande

            self._modele = SentenceTransformer(self.nom_modele, device=self.device)
        return self._modele

    def encoder(self, textes: Sequence[str]) -> list[list[float]]:
        if not textes:
            return []
        vecteurs = self._charger().encode(
            list(textes), batch_size=self.batch_size, normalize_embeddings=True
        )
        return vecteurs.tolist()


class HashEmbedder:
    """Embedder déterministe sans modèle (sac de mots haché), pour les tests.

    Deux textes qui partagent des mots ont des vecteurs proches. Ce n'est pas un
    vrai modèle sémantique : ne pas l'utiliser pour évaluer la qualité du RAG.
    """

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def encoder(self, textes: Sequence[str]) -> list[list[float]]:
        vecteurs = []
        for texte in textes:
            vecteur = [0.0] * self.dimension
            for mot in tokeniser(texte):
                indice = int.from_bytes(hashlib.md5(mot.encode()).digest()[:4], "little")
                vecteur[indice % self.dimension] += 1.0
            norme = math.sqrt(sum(v * v for v in vecteur)) or 1.0
            vecteurs.append([v / norme for v in vecteur])
        return vecteurs


class VectorStore:
    """Collection Qdrant de chunks, avec recherche dense filtrable par cours."""

    def __init__(
        self,
        embedder: Embedder,
        chemin: str | None = None,
        url: str | None = None,
        collection: str = NOM_COLLECTION,
    ) -> None:
        self.embedder = embedder
        self.collection = collection
        if url:
            self.client = QdrantClient(url=url)
        elif chemin:
            self.client = QdrantClient(path=chemin)
        else:
            self.client = QdrantClient(":memory:")
        self._creer_collection()

    def _creer_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            taille = self.client.get_collection(self.collection).config.params.vectors.size
            if taille != self.embedder.dimension:
                raise ValueError(
                    f"La collection {self.collection!r} contient des vecteurs de taille {taille}, "
                    f"mais l'embedder produit {self.embedder.dimension} dimensions. "
                    "Supprime la collection ou utilise un autre nom."
                )
            return
        self.client.create_collection(
            self.collection,
            vectors_config=models.VectorParams(
                size=self.embedder.dimension, distance=models.Distance.COSINE
            ),
        )

    @staticmethod
    def _filtre(course_id: str | None) -> models.Filter | None:
        if course_id is None:
            return None
        return models.Filter(
            must=[models.FieldCondition(key="course_id", match=models.MatchValue(value=course_id))]
        )

    def ajouter(self, chunks: Sequence[Chunk], taille_lot: int = 64) -> int:
        """Encoder et indexer des chunks (remplace un chunk déjà indexé). Renvoie leur nombre."""
        for debut in range(0, len(chunks), taille_lot):
            lot = chunks[debut : debut + taille_lot]
            vecteurs = self.embedder.encoder([texte_a_encoder(c) for c in lot])
            self.client.upsert(
                self.collection,
                points=[
                    models.PointStruct(id=point_id(c.id), vector=v, payload=c.model_dump())
                    for c, v in zip(lot, vecteurs, strict=True)
                ],
            )
        return len(chunks)

    def rechercher(
        self, requete: str, k: int = 20, course_id: str | None = None
    ) -> list[tuple[Chunk, float]]:
        """Recherche dense : les ``k`` chunks les plus proches de la requête, avec leur score cosinus."""
        if not requete.strip():
            return []
        vecteur = self.embedder.encoder([requete])[0]
        points = self.client.query_points(
            self.collection,
            query=vecteur,
            limit=k,
            query_filter=self._filtre(course_id),
            with_payload=True,
        ).points
        return [(Chunk.model_validate(p.payload), float(p.score)) for p in points]

    def tous_les_chunks(self, course_id: str | None = None) -> list[Chunk]:
        """Tous les chunks indexés (pour construire l'index BM25), triés par id."""
        chunks: list[Chunk] = []
        decalage = None
        while True:
            points, decalage = self.client.scroll(
                self.collection,
                scroll_filter=self._filtre(course_id),
                limit=256,
                offset=decalage,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(Chunk.model_validate(p.payload) for p in points)
            if decalage is None:
                break
        return sorted(chunks, key=lambda c: c.id)

    def compter(self, course_id: str | None = None) -> int:
        """Nombre de chunks indexés, pour tous les cours ou un seul."""
        return self.client.count(self.collection, count_filter=self._filtre(course_id)).count

    def supprimer_cours(self, course_id: str) -> None:
        """Retirer tous les chunks d'un cours (avant une réindexation, par exemple)."""
        self.client.delete(
            self.collection, points_selector=models.FilterSelector(filter=self._filtre(course_id))
        )

    def fermer(self) -> None:
        """Libérer le client (nécessaire en mode disque avant de rouvrir le même dossier)."""
        self.client.close()


__all__ = [
    "BgeM3Embedder",
    "CHEMIN_PAR_DEFAUT",
    "Embedder",
    "HashEmbedder",
    "MODELE_EMBEDDINGS",
    "NOM_COLLECTION",
    "VectorStore",
    "point_id",
    "texte_a_encoder",
    "tokeniser",
]
