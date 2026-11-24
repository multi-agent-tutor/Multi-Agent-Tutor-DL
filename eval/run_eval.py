"""B4 — Benchmark « avant / après » de l'agent Q&R sur le jeu d'évaluation C2.

- **avant** : RAG simple — recherche dense seule (bge-m3), sans reranker, sans Critic.
- **après** : recherche hybride (bge-m3 + BM25, RRF) + reranker (bge-reranker-v2-m3)
  + agent Q&R (B3) + boucle de correction du Critic (O3).

Pour chaque question : réponse, slides retrouvées, latence, puis les métriques de
``eval/metriques.py`` (context precision, faithfulness, answer relevancy, refus).
Sorties : ``eval/results.md`` (tableaux + graphique), ``eval/results.svg`` (graphique)
et ``eval/results_details.jsonl`` (une ligne par question et par version).

Prérequis : les cours du jeu d'évaluation ingérés par H1 dans ``data/processed/<id>/course.json``.

    python -m eval.run_eval --limite 24             # premier essai (~quelques minutes par question sur CPU)
    python -m eval.run_eval                         # les 160 questions
    python -m eval.run_eval --juge lexical          # faithfulness sans LLM (plus rapide, approximative)
    python -m eval.run_eval --factice --limite 8    # test de bout en bout sans aucun modèle
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from agents.qa import AgentQA, est_refus
from eval.metriques import (
    Encodeur,
    Juge,
    centile,
    fidelite,
    juge_critic,
    juge_lexical,
    moyenne,
    pertinence,
    precision_contexte,
    questions_depuis_reponse,
)
from eval.schema import QuestionEval, charger
from rag.index import charger_cours, indexer_cours
from rag.rerank import RechercheReranked, Reranker
from rag.search import RechercheHybride
from rag.store import Embedder, VectorStore
from schemas.models import SearchHit

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
DATASET = RACINE / "eval" / "dataset.json"
DOSSIER_COURS = RACINE / "data" / "processed"
SORTIE_MD = RACINE / "eval" / "results.md"
K_PASSAGES = 5


# --------------------------------------------------------------------------- systèmes comparés


class Enregistreur:
    """Enveloppe une recherche et garde les derniers passages retrouvés (pour les métriques)."""

    def __init__(self, recherche) -> None:
        self.recherche = recherche
        self.derniers: list[SearchHit] = []

    def rechercher(self, requete: str, course_id: str | None = None, k: int | None = None) -> list[SearchHit]:
        self.derniers = list(self.recherche.rechercher(requete, course_id=course_id, k=k))
        return self.derniers


class RechercheDense:
    """Version « avant » : recherche dense seule (scores cosinus de bge-m3)."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store

    def rechercher(self, requete: str, course_id: str | None = None, k: int | None = None) -> list[SearchHit]:
        return [SearchHit(chunk=c, score=max(s, 0.0)) for c, s in self.store.rechercher(requete, k or K_PASSAGES, course_id)]


@dataclass
class Sortie:
    """Ce qu'un système renvoie pour une question."""

    reponse: str
    sources: list[int]
    passages: list[SearchHit]
    latence: float
    score_critic: float | None = None


class Systeme(Protocol):
    nom: str

    def repondre(self, q: QuestionEval) -> Sortie:
        ...


class SystemeAvant:
    """RAG simple : dense seul, sans reranker ni Critic. Le seuil est désactivé (0)."""

    nom = "avant"

    def __init__(self, store: VectorStore, generer: Callable[..., str] | None = None) -> None:
        self.recherche = Enregistreur(RechercheDense(store))
        self.agent = AgentQA(self.recherche, seuil=0.0, k=K_PASSAGES, generer=generer)

    def repondre(self, q: QuestionEval) -> Sortie:
        debut = time.perf_counter()
        r = self.agent.repondre(q.question, q.course_id, q.langue)
        return Sortie(r.reponse, [s.numero for s in r.sources], self.recherche.derniers, time.perf_counter() - debut)


class SystemeApres:
    """Hybride + reranker + agent Q&R, dans le graphe avec la boucle du Critic (O3)."""

    nom = "apres"

    def __init__(self, store: VectorStore, reranker: Reranker, generer: Callable[..., str] | None = None,
                 critic: Callable | None = None) -> None:
        from agents.graph import construire_graphe

        self.recherche = Enregistreur(RechercheReranked(RechercheHybride(store), reranker))
        agent = AgentQA(self.recherche, k=K_PASSAGES, generer=generer)
        if critic is None:
            from agents.critic import critic_agent  # O3 (Ons)

            critic = critic_agent
        self.graphe = construire_graphe({"question": agent}, critic=critic)

    def repondre(self, q: QuestionEval) -> Sortie:
        from agents.graph import executer
        from schemas.models import TutorState

        debut = time.perf_counter()
        etat = TutorState(course_id=q.course_id, slide_courante=1, question=q.question,
                          langue_reponse=q.langue, intention="question")
        final = executer(etat, self.graphe)
        return Sortie(final.reponse, [s.numero for s in final.sources], self.recherche.derniers,
                      time.perf_counter() - debut, getattr(final, "score_fidelite", None))


# --------------------------------------------------------------------------- évaluation


@dataclass
class Resultat:
    """Une question évaluée par une version."""

    version: str
    id: str
    course_id: str
    type: str
    question: str
    reponse: str
    sources: list[int]
    recuperees: list[int]
    latence: float
    precision_contexte: float | None
    fidelite: float | None
    pertinence: float | None
    refus: bool
    score_critic: float | None = None
    erreur: str = ""


def evaluer_question(systeme: Systeme, q: QuestionEval, juge: Juge, encoder: Encodeur,
                     generer_questions: Callable[[str], list[str]] | None) -> Resultat:
    """Faire répondre un système, puis calculer les métriques de la question."""
    try:
        s = systeme.repondre(q)
    except Exception as e:  # une question en échec ne doit pas arrêter tout le benchmark
        log.exception("échec sur %s (%s)", q.id, systeme.nom)
        return Resultat(systeme.nom, q.id, q.course_id, q.type, q.question, "", [], [], 0.0,
                        None, None, None, False, erreur=f"{type(e).__name__}: {e}")
    recuperees = [h.chunk.numero for h in s.passages]
    textes = {h.chunk.numero: h.chunk.contenu for h in s.passages}
    return Resultat(
        version=systeme.nom, id=q.id, course_id=q.course_id, type=q.type, question=q.question,
        reponse=s.reponse, sources=s.sources, recuperees=recuperees, latence=round(s.latence, 3),
        precision_contexte=precision_contexte(recuperees, set(q.slides)),
        fidelite=fidelite(s.reponse, textes, juge),
        pertinence=pertinence(q.question, s.reponse, encoder, generer_questions),
        refus=est_refus(s.reponse), score_critic=s.score_critic,
    )


def selectionner(questions: Sequence[QuestionEval], limite: int | None) -> list[QuestionEval]:
    """Échantillon varié de ``limite`` questions : on alterne les types, et les cours dans chaque type."""
    if not limite or limite >= len(questions):
        return list(questions)
    par_type: dict[str, list[QuestionEval]] = {}
    for q in questions:
        par_type.setdefault(q.type, []).append(q)
    cours = sorted({q.course_id for q in questions})
    files = []
    for decalage, qs in enumerate(par_type.values()):
        rang: dict[str, int] = {}
        ordonnees = []
        for q in qs:  # rang de la question dans son cours, pour alterner les cours
            rang[q.course_id] = rang.get(q.course_id, -1) + 1
            ordonnees.append((rang[q.course_id], q.course_id, q))
        # chaque type commence par un cours différent : l'échantillon couvre plus de cours
        tour = {c: (i - 4 * decalage) % len(cours) for i, c in enumerate(cours)}
        files.append([q for _, _, q in sorted(ordonnees, key=lambda x: (x[0], tour[x[1]]))])
    choix: list[QuestionEval] = []
    i = 0
    while len(choix) < limite and any(i < len(f) for f in files):
        choix += [f[i] for f in files if i < len(f)][: limite - len(choix)]
        i += 1
    return choix


def indexer_corpus(store: VectorStore, course_ids: set[str], dossier: Path = DOSSIER_COURS) -> set[str]:
    """Indexer les cours disponibles dans ``dossier`` ; renvoie les ids indexés."""
    indexes = set()
    for cid in sorted(course_ids):
        chemin = dossier / cid / "course.json"
        if chemin.is_file():
            indexer_cours(store, charger_cours(chemin))
            indexes.add(cid)
        else:
            log.warning("cours %s absent de %s : ses questions sont ignorées (lancer H1)", cid, dossier)
    return indexes


def executer_benchmark(questions: Sequence[QuestionEval], systemes: Sequence[Systeme], juge: Juge,
                       encoder: Encodeur, generer_questions: Callable[[str], list[str]] | None = None,
                       progression: Callable[[str], None] = print) -> list[Resultat]:
    """Évaluer chaque question avec chaque système."""
    resultats = []
    total = len(questions) * len(systemes)
    for i, q in enumerate(questions):
        for j, systeme in enumerate(systemes):
            r = evaluer_question(systeme, q, juge, encoder, generer_questions)
            resultats.append(r)
            progression(f"[{i * len(systemes) + j + 1}/{total}] {systeme.nom:5} {q.id} "
                        f"{'refus' if r.refus else 'réponse'} {r.latence:.1f} s")
    return resultats


# --------------------------------------------------------------------------- agrégation et rapport


METRIQUES = [
    ("precision_contexte", "Context precision"),
    ("fidelite", "Faithfulness"),
    ("pertinence", "Answer relevancy"),
]


@dataclass
class Synthese:
    version: str
    n: int
    precision_contexte: float | None
    fidelite: float | None
    pertinence: float | None
    refus_correct: float | None
    faux_refus: float | None
    latence_moyenne: float | None
    latence_p95: float | None
    erreurs: int = 0
    par_type: dict[str, dict[str, float | None]] = field(default_factory=dict)


def synthese(resultats: Sequence[Resultat], version: str) -> Synthese:
    rs = [r for r in resultats if r.version == version and not r.erreur]
    hors = [r for r in rs if r.type == "hors_cours"]
    dans = [r for r in rs if r.type != "hors_cours"]
    latences = [r.latence for r in rs]
    par_type = {}
    for t in ("factuelle", "comprehension", "figure", "hors_cours"):
        sous = [r for r in rs if r.type == t]
        if sous:
            par_type[t] = {
                "n": len(sous),
                "precision_contexte": moyenne([r.precision_contexte for r in sous]),
                "fidelite": moyenne([r.fidelite for r in sous]),
                "refus": sum(r.refus for r in sous) / len(sous),
            }
    return Synthese(
        version=version, n=len(rs),
        precision_contexte=moyenne([r.precision_contexte for r in rs]),
        fidelite=moyenne([r.fidelite for r in rs]),
        pertinence=moyenne([r.pertinence for r in rs]),
        refus_correct=(sum(r.refus for r in hors) / len(hors)) if hors else None,
        faux_refus=(sum(r.refus for r in dans) / len(dans)) if dans else None,
        latence_moyenne=moyenne(latences), latence_p95=centile(latences, 0.95),
        erreurs=sum(1 for r in resultats if r.version == version and r.erreur),
        par_type=par_type,
    )


def _f(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.0f} %" if pct else f"{v:.2f}"


def _ecart(a: float | None, b: float | None, plus_bas_mieux: bool = False, pct: bool = False) -> str:
    if a is None or b is None:
        return "—"
    d = b - a
    meilleur = (d < 0) if plus_bas_mieux else (d > 0)
    signe = "+" if d >= 0 else "−"
    valeur = f"{abs(d) * 100:.0f} pts" if pct else f"{abs(d):.2f}"
    return f"{signe}{valeur} {'✅' if meilleur else ('=' if d == 0 else '⚠')}"


def graphique_svg(avant: Synthese, apres: Synthese) -> str:
    """Barres groupées avant / après pour les scores entre 0 et 1 (SVG autonome, sans dépendance)."""
    series = [(l, getattr(avant, k), getattr(apres, k)) for k, l in METRIQUES]
    series.append(("Refus correct", avant.refus_correct, apres.refus_correct))
    largeur, hauteur, gauche, bas, haut = 720, 340, 60, 280, 40
    groupe = (largeur - gauche - 20) / len(series)
    barre = groupe / 3
    echelle = lambda v: bas - (bas - haut) * (v or 0)  # noqa: E731
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="12">',
             f'<text x="{gauche}" y="22" font-size="15" font-weight="600" fill="#0B1A45">Agent Q&amp;R : avant / après (n = {apres.n} questions)</text>']
    for i in range(6):
        v = i / 5
        y = echelle(v)
        parts.append(f'<line x1="{gauche}" x2="{largeur - 20}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E2E8F0"/>')
        parts.append(f'<text x="{gauche - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#475569">{v:.1f}</text>')
    for i, (label, a, b) in enumerate(series):
        x0 = gauche + i * groupe + barre / 2
        for j, (v, couleur) in enumerate([(a, "#4C8AFD"), (b, "#1D4ED8")]):
            if v is None:
                continue
            x = x0 + j * barre
            parts.append(f'<rect x="{x:.1f}" y="{echelle(v):.1f}" width="{barre - 4:.1f}" height="{bas - echelle(v):.1f}" rx="3" fill="{couleur}"/>')
            parts.append(f'<text x="{x + (barre - 4) / 2:.1f}" y="{echelle(v) - 5:.1f}" text-anchor="middle" fill="#0B1A45">{v:.2f}</text>')
        parts.append(f'<text x="{x0 + barre - 2:.1f}" y="{bas + 18}" text-anchor="middle" fill="#0B1A45">{label}</text>')
    parts.append(f'<rect x="{largeur - 270}" y="{hauteur - 26}" width="12" height="12" rx="2" fill="#4C8AFD"/><text x="{largeur - 252}" y="{hauteur - 16}" fill="#475569">avant (dense seul)</text>')
    parts.append(f'<rect x="{largeur - 120}" y="{hauteur - 26}" width="12" height="12" rx="2" fill="#1D4ED8"/><text x="{largeur - 102}" y="{hauteur - 16}" fill="#475569">après (complet)</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def rapport_markdown(avant: Synthese, apres: Synthese, config: dict[str, str]) -> str:
    lignes = [
        "# B4 — Benchmark de l'agent Q&R : avant / après",
        "",
        f"Jeu d'évaluation C2 : **{apres.n} questions** évaluées par version. "
        f"Configuration : {', '.join(f'{k} = {v}' for k, v in config.items())}.",
        "",
        "- **Avant** : recherche dense seule (bge-m3), sans reranker, sans Critic.",
        "- **Après** : recherche hybride (bge-m3 + BM25, fusion RRF) + reranker bge-reranker-v2-m3 + agent Q&R (B3) + Critic (O3).",
        "",
        "## Résultats",
        "",
        "| Métrique | Avant | Après | Écart |",
        "| --- | --- | --- | --- |",
    ]
    for k, label in METRIQUES:
        lignes.append(f"| {label} | {_f(getattr(avant, k))} | {_f(getattr(apres, k))} | {_ecart(getattr(avant, k), getattr(apres, k))} |")
    lignes += [
        f"| Refus correct (hors cours) | {_f(avant.refus_correct, True)} | {_f(apres.refus_correct, True)} | {_ecart(avant.refus_correct, apres.refus_correct, pct=True)} |",
        f"| Faux refus (réponse dans le cours) | {_f(avant.faux_refus, True)} | {_f(apres.faux_refus, True)} | {_ecart(avant.faux_refus, apres.faux_refus, True, True)} |",
        f"| Latence moyenne (s) | {_f(avant.latence_moyenne)} | {_f(apres.latence_moyenne)} | {_ecart(avant.latence_moyenne, apres.latence_moyenne, True)} |",
        f"| Latence p95 (s) | {_f(avant.latence_p95)} | {_f(apres.latence_p95)} | {_ecart(avant.latence_p95, apres.latence_p95, True)} |",
        "",
        "![Avant / après](results.svg)",
        "",
        "## Par type de question (version après)",
        "",
        "| Type | Questions | Context precision | Faithfulness | Taux de refus |",
        "| --- | --- | --- | --- | --- |",
    ]
    for t, v in apres.par_type.items():
        lignes.append(f"| {t} | {v['n']} | {_f(v['precision_contexte'])} | {_f(v['fidelite'])} | {_f(v['refus'], True)} |")
    lignes += [
        "",
        "## Méthode",
        "",
        "- **Context precision** (définition RAGAS avec référence) : moyenne des précisions@k aux rangs où une slide de référence de C2 apparaît parmi les 5 passages retrouvés. Calcul exact, sans LLM.",
        "- **Faithfulness** (définition RAGAS) : part des affirmations de la réponse appuyées par les passages retrouvés, jugée par le LLM local (procédure du Critic O3). Non calculée pour un refus.",
        "- **Answer relevancy** (définition RAGAS) : cosinus moyen (bge-m3) entre la question et 3 questions générées par le LLM local à partir de la réponse. Non calculée pour un refus.",
        "- **Refus correct / faux refus** : réponse « L'information n'est pas dans le cours. » sur les questions hors cours / sur les questions dont la réponse est dans le cours.",
        "- Règle v2 : la bibliothèque RAGAS appelle une API par défaut ; les métriques sont donc recalculées en local avec les mêmes définitions, le LLM de l'équipe (Qwen2.5-3B) et bge-m3.",
        "- Limite : le juge de faithfulness est le même LLM que celui du Critic ; la version « après » est donc jugée avec la procédure qu'elle optimise. La context precision, elle, ne dépend d'aucun LLM.",
    ]
    if avant.erreurs or apres.erreurs:
        lignes += ["", f"Questions en erreur (exclues) : avant {avant.erreurs}, après {apres.erreurs}. Détail dans `results_details.jsonl`."]
    return "\n".join(lignes) + "\n"


def ecrire_sorties(resultats: Sequence[Resultat], config: dict[str, str], sortie_md: Path = SORTIE_MD) -> tuple[Synthese, Synthese]:
    avant, apres = synthese(resultats, "avant"), synthese(resultats, "apres")
    sortie_md.parent.mkdir(parents=True, exist_ok=True)
    sortie_md.write_text(rapport_markdown(avant, apres, config), encoding="utf-8")
    sortie_md.with_suffix(".svg").write_text(graphique_svg(avant, apres), encoding="utf-8")
    details = sortie_md.with_name("results_details.jsonl")
    details.write_text("\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in resultats) + "\n", encoding="utf-8")
    return avant, apres


# --------------------------------------------------------------------------- ligne de commande


def main(arguments: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark avant / après de l'agent Q&R (B4).")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--cours", type=Path, default=DOSSIER_COURS, help="dossier data/processed")
    parser.add_argument("--limite", type=int, default=None, help="nombre de questions (échantillon varié)")
    parser.add_argument("--juge", choices=["llm", "lexical"], default="llm", help="juge de faithfulness")
    parser.add_argument("--sans-questions-generees", action="store_true",
                        help="answer relevancy = cosinus question/réponse, sans LLM (plus rapide)")
    parser.add_argument("--qdrant", default=None, help="dossier Qdrant (défaut : en mémoire)")
    parser.add_argument("--sortie", type=Path, default=SORTIE_MD)
    parser.add_argument("--factice", action="store_true", help="modèles factices (test sans téléchargement)")
    args = parser.parse_args(arguments)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    if args.factice:
        import os

        from rag.rerank import MotsCommunsReranker
        from rag.store import HashEmbedder

        os.environ["LLM_BACKEND"] = "fake"
        embedder: Embedder = HashEmbedder()
        reranker: Reranker = MotsCommunsReranker()
    else:
        from rag.rerank import BgeReranker
        from rag.store import BgeM3Embedder

        embedder, reranker = BgeM3Embedder(), BgeReranker()

    jeu = charger(args.dataset)
    store = VectorStore(embedder, chemin=args.qdrant, collection="eval_hash" if args.factice else "eval")
    disponibles = indexer_corpus(store, {q.course_id for q in jeu.questions}, args.cours)
    questions = selectionner([q for q in jeu.questions if q.course_id in disponibles], args.limite)
    if not questions:
        print(f"Aucune question évaluable : aucun cours du jeu C2 dans {args.cours}/<course_id>/course.json (lancer H1).")
        return
    print(f"{len(questions)} questions, {len(disponibles)} cours indexés ({store.compter()} chunks).")

    systemes = [SystemeAvant(store), SystemeApres(store, reranker)]
    juge = juge_critic if args.juge == "llm" else juge_lexical
    generer_q = None if (args.sans_questions_generees or args.factice) else questions_depuis_reponse
    resultats = executer_benchmark(questions, systemes, juge, embedder.encoder, generer_q)
    config = {"questions": str(len(questions)), "juge": args.juge,
              "answer relevancy": "cosinus" if generer_q is None else "questions générées",
              "modèles": "factices" if args.factice else "bge-m3, bge-reranker-v2-m3, Qwen2.5-3B (local)"}
    avant, apres = ecrire_sorties(resultats, config, args.sortie)
    print(f"\nRésultats écrits dans {args.sortie} (+ .svg et results_details.jsonl)")
    for s in (avant, apres):
        print(f"  {s.version:5}  CP={_f(s.precision_contexte)}  F={_f(s.fidelite)}  AR={_f(s.pertinence)}  "
              f"refus OK={_f(s.refus_correct, True)}  faux refus={_f(s.faux_refus, True)}  latence={_f(s.latence_moyenne)} s")
    store.fermer()


if __name__ == "__main__":
    main()
