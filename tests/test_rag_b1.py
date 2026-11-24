"""Tests B1 : stockage Qdrant, BM25, fusion RRF et recherche hybride.

Ils utilisent Qdrant en mémoire et ``HashEmbedder`` : aucun modèle n'est téléchargé.
"""

import pytest

from rag.search import BM25, K_RRF, RechercheHybride, fusion_rrf
from rag.store import HashEmbedder, VectorStore, point_id, tokeniser
from schemas.models import Chunk, SearchHit


def _chunk(course_id: str, numero: int, titre: str, contenu: str, langue: str = "fr") -> Chunk:
    return Chunk(
        id=f"{course_id}__s{numero:03d}",
        course_id=course_id,
        numero=numero,
        titre=titre,
        contenu=contenu,
        langue=langue,
    )


CHUNKS = [
    _chunk("bd_test_fr", 1, "Clé primaire", "La clé primaire identifie chaque n-uplet de la relation."),
    _chunk("bd_test_fr", 2, "Jointure naturelle", "La jointure naturelle combine deux relations sur les attributs communs."),
    _chunk("bd_test_fr", 3, "SGBD", "Un SGBD est un logiciel qui gère une base de données partagée."),
    _chunk("cloud_test_en", 1, "Hypervisor", "A hypervisor runs several virtual machines on one physical server.", "en"),
    _chunk("cloud_test_en", 2, "Live migration", "Live migration moves a running virtual machine to another host.", "en"),
    _chunk("cloud_test_en", 3, "Elasticity", "Rapid elasticity lets resources scale with demand.", "en"),
]


@pytest.fixture
def store():
    s = VectorStore(HashEmbedder())
    s.ajouter(CHUNKS)
    yield s
    s.fermer()


def test_tokeniser_enleve_accents_et_ponctuation():
    assert tokeniser("Réseaux TCP/IP : clé élève") == ["reseaux", "tcp", "ip", "cle", "eleve"]


def test_point_id_stable():
    assert point_id("bd_test_fr__s001") == point_id("bd_test_fr__s001")
    assert point_id("bd_test_fr__s001") != point_id("bd_test_fr__s002")


def test_ajout_compte_et_reindexation_sans_doublon(store):
    assert store.compter() == 6
    assert store.compter("bd_test_fr") == 3
    store.ajouter(CHUNKS[:2])  # même ids : remplacement, pas de doublon
    assert store.compter() == 6


def test_tous_les_chunks_restitue_les_chunks(store):
    assert store.tous_les_chunks() == sorted(CHUNKS, key=lambda c: c.id)
    assert [c.numero for c in store.tous_les_chunks("cloud_test_en")] == [1, 2, 3]


def test_recherche_dense_et_filtre_par_cours(store):
    resultats = store.rechercher("hypervisor virtual machines", k=3)
    assert resultats[0][0].id == "cloud_test_en__s001"
    filtres = store.rechercher("hypervisor virtual machines", k=3, course_id="bd_test_fr")
    assert filtres and all(c.course_id == "bd_test_fr" for c, _ in filtres)
    assert store.rechercher("   ") == []


def test_supprimer_cours(store):
    store.supprimer_cours("bd_test_fr")
    assert store.compter() == 3
    assert store.compter("bd_test_fr") == 0


def test_persistance_sur_disque(tmp_path):
    chemin = str(tmp_path / "qdrant")
    s = VectorStore(HashEmbedder(), chemin=chemin)
    s.ajouter(CHUNKS)
    s.fermer()
    rouvert = VectorStore(HashEmbedder(), chemin=chemin)
    assert rouvert.compter() == 6
    rouvert.fermer()


def test_dimension_incompatible_refusee(tmp_path):
    chemin = str(tmp_path / "qdrant")
    VectorStore(HashEmbedder(dimension=64), chemin=chemin).fermer()
    with pytest.raises(ValueError, match="dimensions"):
        VectorStore(HashEmbedder(dimension=128), chemin=chemin)


def test_bm25_terme_exact_et_requete_vide():
    bm25 = BM25(CHUNKS)
    resultats = bm25.rechercher("SGBD")
    assert resultats[0][0].id == "bd_test_fr__s003"
    assert len(resultats) == 1  # seuls les chunks contenant le mot ont un score > 0
    assert bm25.rechercher("?!") == []
    assert bm25.rechercher("relation", course_id="cloud_test_en") == []


def test_bm25_insensible_aux_accents():
    assert BM25(CHUNKS).rechercher("cle primaire")[0][0].id == "bd_test_fr__s001"


def test_fusion_rrf_calcul():
    a, b, c = CHUNKS[:3]
    fusion = fusion_rrf([[a, b], [b, c]])
    scores = {chunk.id: s for chunk, s in fusion}
    assert fusion[0][0].id == b.id  # présent dans les deux classements
    assert scores[b.id] == pytest.approx(1 / (K_RRF + 2) + 1 / (K_RRF + 1))
    assert scores[a.id] == pytest.approx(1 / (K_RRF + 1))
    assert scores[c.id] == pytest.approx(1 / (K_RRF + 2))
    assert fusion_rrf([]) == []


def test_recherche_hybride(store):
    recherche = RechercheHybride(store)
    hits = recherche.rechercher("Qu'est-ce qu'une clé primaire ?", k=3)
    assert all(isinstance(h, SearchHit) for h in hits)
    assert len(hits) <= 3
    assert hits[0].chunk.id == "bd_test_fr__s001"
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_recherche_hybride_filtre_et_rafraichissement(store):
    recherche = RechercheHybride(store)
    hits = recherche.rechercher("migration", k=5, course_id="cloud_test_en")
    assert hits and all(h.chunk.course_id == "cloud_test_en" for h in hits)
    nouveau = _chunk("cloud_test_en", 4, "Containers", "Containers share the host kernel.", "en")
    store.ajouter([nouveau])
    recherche.rafraichir()
    assert recherche.lexicale("kernel")[0].chunk.id == nouveau.id


def test_dense_et_lexicale_renvoient_des_searchhit(store):
    recherche = RechercheHybride(store)
    assert all(isinstance(h, SearchHit) for h in recherche.dense("elasticity", k=2))
    assert recherche.lexicale("elasticity", k=2)[0].chunk.id == "cloud_test_en__s003"
