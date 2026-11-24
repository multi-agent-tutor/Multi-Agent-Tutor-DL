"""H3 — Carte du cours : concepts par slide, graphe de prérequis et résumé global.

Points d'entrée (contrat T0, voir ``docs/schema.md``) :

- ``build_course_map(course) -> Course`` : remplit ``slide.concepts`` et ``course.resume``, et écrit
  ``data/processed/<course_id>/course_map.json`` ;
- ``get_prerequisites(slide_id) -> list[str]`` : ids des slides qui introduisent les concepts
  nécessaires pour comprendre la slide (utilisé par l'Explainer d'Ons, O2).

Le LLM est celui de l'équipe (``agents/llm.py``, A0, 100 % local). S'il est indisponible, un repli
heuristique (n-grammes pondérés TF-IDF) garantit que la carte est toujours produite.

Graphe :

- concept → slides où il apparaît (extrait par le LLM ou cité dans le texte) ;
- concept → slide d'introduction (première slide où il est un concept clé) ;
- concept C → prérequis D si D est introduit avant C et réapparaît là où C est introduit (ou sur
  plusieurs slides de C). Un prérequis est toujours introduit avant : le graphe est acyclique.

Usage : ``python -m ingestion.course_map <course_id> [...] [--sans-llm]``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from schemas import Course, Slide, slide_id as construire_slide_id

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_CACHE = RACINE / "data" / "cache" / "concepts"
VERSION_CARTE = "h3-v1"
MAX_CONCEPTS_SLIDE = 5
MAX_PREREQUIS_CONCEPT = 5
MAX_PREREQUIS_SLIDE = 5

_STOP = set("""
le la les un une des du de d l au aux et ou en dans sur sous par pour avec sans ce cet cette ces
son sa ses leur leurs nous vous ils elles il elle on qui que quoi dont est sont été être avoir a ont
plus moins très tout tous toute toutes pas ne se si comme mais donc car ainsi alors entre chaque
the a an of to in for on with by as at from and or is are be been was were this that these those it
its we you they their our can may will which what when where how why not no all any each more most
such than then there here into over under using use used also only other one two three via per
cours chapitre slide slides page exemple example exemples examples figure introduction conclusion
plan outline today question questions summary résumé rappel recap definition définition lecture
http https www org com html pdf arxiv abs fig etc vs ie eg
""".split())


class ConceptsSlide(BaseModel):
    """Sortie attendue du LLM pour une slide."""

    concepts: list[str] = Field(default_factory=list, max_length=8)


# --------------------------------------------------------------------------- normalisation


def cle_concept(nom: str) -> str:
    """Clé de comparaison : minuscules, sans accents, sans article, pluriel simple retiré."""
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9+#\- ]+", " ", s)
    s = re.sub(r"^(le|la|les|l|un|une|des|the|a|an)\s+", "", s.strip())
    mots = [m[:-1] if len(m) > 4 and m.endswith("s") and not m.endswith("ss") else m for m in s.split()]
    return " ".join(mots)


def _nettoyer_concept(nom: str) -> str:
    nom = re.sub(r"\s+", " ", nom).strip(" .,;:-–—•*\"'«»()[]")
    return nom[:80]


def _mots(texte: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9\-]+", texte)


# --------------------------------------------------------------------------- repli heuristique


def _candidats(texte: str) -> list[str]:
    """N-grammes (1 à 3 mots) qui ne commencent ni ne finissent par un mot vide."""
    texte = re.sub(r"(https?://|www\.)\S+|\S+\.(com|org|edu|fr|html?|pdf)\S*", " ", texte)
    mots = _mots(texte)
    candidats = []
    for n in (1, 2, 3):
        for i in range(len(mots) - n + 1):
            groupe = mots[i:i + n]
            if groupe[0].lower() in _STOP or groupe[-1].lower() in _STOP or len(groupe[0]) < 3:
                continue
            if any(len(m) < 2 for m in groupe):
                continue
            candidats.append(" ".join(groupe))
    return candidats


def concepts_heuristiques(course: Course) -> dict[int, list[str]]:
    """Concepts par slide sans LLM : n-grammes pondérés TF-IDF, bonus pour le titre."""
    docs: dict[int, Counter] = {}
    formes: dict[str, Counter] = defaultdict(Counter)
    for s in course.slides:
        compte: Counter = Counter()
        for source, poids in ((s.titre, 3.0), (s.texte, 1.0), (" ".join(s.description_figures), 0.5)):
            for c in _candidats(source):
                cle = cle_concept(c)
                if cle and cle not in _STOP:
                    compte[cle] += poids * (1 + 0.5 * (len(cle.split()) - 1))
                    formes[cle][c] += 1
        docs[s.numero] = compte
    df = Counter(cle for c in docs.values() for cle in c)
    n = max(len(docs), 1)
    resultat: dict[int, list[str]] = {}
    for numero, compte in docs.items():
        scores = {cle: tf * math.log(1 + n / df[cle]) for cle, tf in compte.items()
                  if df[cle] < max(3, n * 0.6)}  # présent partout = bruit (nom du cours, auteur…)
        meilleurs = sorted(scores, key=lambda k: (-scores[k], k))
        choisis: list[str] = []
        for cle in meilleurs:
            if any(cle in autre or autre in cle for autre in choisis):
                continue  # éviter « gradient » et « descente de gradient » sur la même slide
            choisis.append(cle)
            if len(choisis) == MAX_CONCEPTS_SLIDE - 1:
                break
        resultat[numero] = [formes[c].most_common(1)[0][0] for c in choisis]
    return resultat


# --------------------------------------------------------------------------- LLM (A0)


def _llm():
    from agents import llm

    return llm


def _cle_cache(slide: Slide, modele: str) -> str:
    contenu = json.dumps([slide.titre, slide.texte, slide.notes, slide.description_figures,
                          slide.formules_latex, modele, VERSION_CARTE], ensure_ascii=False)
    return hashlib.sha256(contenu.encode()).hexdigest()


def _prompt_concepts(slide: Slide, titre_cours: str, langue: str) -> tuple[str, str]:
    contenu = "\n".join(x for x in (
        f"Titre : {slide.titre}" if slide.titre else "",
        slide.texte[:1500],
        f"Notes : {slide.notes[:400]}" if slide.notes else "",
        "Figures : " + " ".join(slide.description_figures)[:600] if slide.description_figures else "",
        "Formules : " + " ; ".join(slide.formules_latex)[:300] if slide.formules_latex else "",
    ) if x)
    if langue == "en":
        system = "You extract the key concepts of a course slide. Answer only with JSON."
        prompt = (f"Course: {titre_cours}\nSlide {slide.numero}:\n{contenu}\n\n"
                  f'Return {{"concepts": [...]}} with the 1 to {MAX_CONCEPTS_SLIDE} key technical concepts '
                  "taught on this slide, as short noun phrases (1-4 words) in English, most important first. "
                  "No generic words (introduction, example, summary), no author or university names. "
                  "Empty list if the slide teaches nothing (title page, outline, references).")
    else:
        system = "Tu extrais les concepts clés d'une slide de cours. Tu réponds uniquement en JSON."
        prompt = (f"Cours : {titre_cours}\nSlide {slide.numero} :\n{contenu}\n\n"
                  f'Renvoie {{"concepts": [...]}} avec les 1 à {MAX_CONCEPTS_SLIDE} concepts techniques clés '
                  "enseignés sur cette slide, en groupes nominaux courts (1 à 4 mots) dans la langue du cours, "
                  "du plus important au moins important. Pas de mots génériques (introduction, exemple, "
                  "résumé), pas de noms d'auteurs ni d'universités. Liste vide si la slide n'enseigne rien "
                  "(page de titre, plan, références).")
    return system, prompt


def concepts_llm(course: Course, cache: Path | None = None) -> dict[int, list[str]]:
    """Concepts par slide via le LLM local, avec cache ; lève ``LLMIndisponible`` si le LLM ne répond pas."""
    llm = _llm()
    cache = Path(cache) if cache else DOSSIER_CACHE
    utiliser_cache = llm.backend() != "fake"
    langue = "en" if course.langue == "en" else "fr"
    resultat: dict[int, list[str]] = {}
    echecs = reussites = 0
    for slide in course.slides:
        if not (slide.titre or slide.texte or slide.description_figures):
            resultat[slide.numero] = []
            continue
        fichier = cache / f"{_cle_cache(slide, llm.modele())}.json"
        if utiliser_cache and fichier.is_file():
            try:
                resultat[slide.numero] = ConceptsSlide.model_validate_json(fichier.read_text(encoding="utf-8")).concepts
                continue
            except ValidationError:
                pass
        system, prompt = _prompt_concepts(slide, course.titre, langue)
        try:
            sortie = llm.generer_structure(system, prompt, ConceptsSlide, max_tokens=200)
        except llm.LLMIndisponible as e:
            echecs += 1
            log.warning("LLM en échec sur %s : %s", slide.id, e)
            if echecs >= 3 and not reussites:
                raise  # le LLM ne répond pas du tout : repli global
            continue
        resultat[slide.numero] = sortie.concepts
        reussites += 1
        if utiliser_cache:
            cache.mkdir(parents=True, exist_ok=True)
            fichier.write_text(sortie.model_dump_json(), encoding="utf-8")
    return resultat


def _resume_llm(course: Course, concepts: dict[int, list[str]]) -> str:
    llm = _llm()
    plan = "\n".join(
        f"- Slide {s.numero} : {s.titre or '(sans titre)'}"
        + (f" — {', '.join(concepts.get(s.numero, [])[:4])}" if concepts.get(s.numero) else "")
        for s in course.slides
    )[:3000]
    if course.langue == "en":
        system = "You write concise, faithful course summaries for students."
        prompt = (f"Course: {course.titre}\nOutline:\n{plan}\n\nWrite a 4 to 7 sentence summary of this "
                  "course in English: goal, main notions in order, and what the student will be able to do. "
                  "Use only the outline above.")
    else:
        system = "Tu rédiges des résumés de cours concis et fidèles pour des étudiants."
        prompt = (f"Cours : {course.titre}\nPlan :\n{plan}\n\nRédige en français un résumé de 4 à 7 phrases : "
                  "objectif, notions principales dans l'ordre, et ce que l'étudiant saura faire. "
                  "N'utilise que le plan ci-dessus.")
    return llm.generer_texte(system, prompt, max_tokens=400).strip()


def _resume_extractif(course: Course, carte: dict) -> str:
    principaux = sorted(carte["concepts"].values(), key=lambda c: (-len(c["slides"]), c["introduit_slide"]))
    noms = [c["nom"] for c in principaux[:8]]
    titres = list(dict.fromkeys(s.titre for s in course.slides if s.titre))[:8]
    if course.langue == "en":
        return (f"This {course.nombre_slides}-slide course, « {course.titre} », covers: {', '.join(noms)}. "
                f"Outline: {' ; '.join(titres)}.")
    return (f"Ce cours de {course.nombre_slides} slides, « {course.titre} », aborde : {', '.join(noms)}. "
            f"Plan : {' ; '.join(titres)}.")


# --------------------------------------------------------------------------- graphe


def _texte_normalise(slide: Slide) -> str:
    brut = " ".join((slide.titre, slide.texte, slide.notes, " ".join(slide.description_figures)))
    return " " + cle_concept(brut) + " "


def construire_graphe(course: Course, concepts_par_slide: dict[int, list[str]]) -> dict:
    """Construire la carte (dict sérialisable) à partir des concepts extraits par slide."""
    noms: dict[str, Counter] = defaultdict(Counter)
    extraits: dict[str, set[int]] = defaultdict(set)
    par_slide: dict[int, list[str]] = {}
    for numero, liste in concepts_par_slide.items():
        cles: list[str] = []
        for brut in liste:
            nom = _nettoyer_concept(brut)
            cle = cle_concept(nom)
            if len(cle) < 2 or cle in _STOP or cle in cles:
                continue
            cles.append(cle)
            noms[cle][nom] += 1
            extraits[cle].add(numero)
        par_slide[numero] = cles[:MAX_CONCEPTS_SLIDE]

    # Mentions : un concept cité dans le texte d'une slide y « apparaît » aussi.
    textes = {s.numero: _texte_normalise(s) for s in course.slides}
    apparitions: dict[str, set[int]] = {}
    for cle, nums in extraits.items():
        cites = {n for n, t in textes.items() if len(cle) >= 4 and f" {cle} " in t}
        apparitions[cle] = nums | cites
    introduction = {cle: min(nums) for cle, nums in extraits.items()}

    prerequis: dict[str, list[str]] = {}
    for cle, intro in introduction.items():
        scores: Counter = Counter()
        for autre, intro_autre in introduction.items():
            if autre == cle or intro_autre >= intro:
                continue
            communs = apparitions[autre] & apparitions[cle]
            if intro in apparitions[autre] or len(communs) >= 2:
                scores[autre] = len(communs) + (2 if intro in apparitions[autre] else 0)
        prerequis[cle] = [a for a, _ in sorted(scores.items(),
                                               key=lambda kv: (-kv[1], intro - introduction[kv[0]], kv[0]))
                          ][:MAX_PREREQUIS_CONCEPT]

    slides: dict[str, dict] = {}
    for s in course.slides:
        cles = par_slide.get(s.numero, [])
        besoins: Counter = Counter()
        for cle in cles:
            if introduction[cle] < s.numero:  # concept déjà vu : sa slide d'introduction est un prérequis
                besoins[cle] += 2
            for p in prerequis[cle]:
                besoins[p] += 1
        sources: Counter = Counter()
        for cle, poids in besoins.items():
            if introduction[cle] < s.numero:
                sources[introduction[cle]] += poids
        meilleures = sorted(sources, key=lambda n: (-sources[n], s.numero - n))[:MAX_PREREQUIS_SLIDE]
        slides[s.id] = {
            "numero": s.numero,
            "concepts": cles,
            "prerequis": [construire_slide_id(course.id, n) for n in sorted(meilleures)],
        }

    return {
        "version": VERSION_CARTE,
        "course_id": course.id,
        "concepts": {
            cle: {
                "nom": noms[cle].most_common(1)[0][0],
                "introduit_slide": introduction[cle],
                "slides": sorted(apparitions[cle]),
                "prerequis": prerequis[cle],
            }
            for cle in sorted(introduction, key=lambda c: (introduction[c], c))
        },
        "slides": slides,
    }


def exporter_mermaid(carte: dict, max_concepts: int = 40) -> str:
    """Graphe des prérequis au format Mermaid (pour la doc ou le frontend)."""
    concepts = carte["concepts"]
    retenus = sorted(concepts, key=lambda c: (-len(concepts[c]["slides"]), concepts[c]["introduit_slide"]))[:max_concepts]
    ids = {cle: f"c{i}" for i, cle in enumerate(retenus)}
    lignes = ["graph LR"]
    for cle in retenus:
        nom = concepts[cle]["nom"].replace('"', "'")
        lignes.append(f'  {ids[cle]}["{nom} (s{concepts[cle]["introduit_slide"]})"]')
    for cle in retenus:
        for p in concepts[cle]["prerequis"]:
            if p in ids:
                lignes.append(f"  {ids[p]} --> {ids[cle]}")
    return "\n".join(lignes) + "\n"


# --------------------------------------------------------------------------- points d'entrée


def build_course_map(course: Course, *, dossier: Path | None = None, utiliser_llm: bool | None = None,
                     cache: Path | None = None, sauvegarder: bool = True) -> Course:
    """Renvoyer une copie du cours avec ``concepts`` et ``resume`` remplis, et écrire la carte.

    ``utiliser_llm`` : ``None`` = LLM si configuré (``agents.llm.est_configure()``), sinon heuristique.
    """
    dossier = Path(dossier) if dossier else DOSSIER_PROCESSED / course.id
    if utiliser_llm is None:
        try:
            utiliser_llm = _llm().est_configure()
        except Exception:  # noqa: BLE001 - agents/llm.py absent ou dépendance manquante
            utiliser_llm = False

    methode = "heuristique"
    concepts = concepts_heuristiques(course)
    if utiliser_llm:
        try:
            par_llm = concepts_llm(course, cache)
            # Slide où le LLM a échoué : on garde l'heuristique.
            concepts = {n: par_llm.get(n, concepts[n]) for n in concepts}
            methode = f"llm:{_llm().modele()}"
        except Exception as e:  # noqa: BLE001
            log.warning("LLM indisponible pour H3 (%s) : repli heuristique", e)

    carte = construire_graphe(course, concepts)
    resume = ""
    if utiliser_llm and methode.startswith("llm"):
        try:
            resume = _resume_llm(course, concepts)
        except Exception as e:  # noqa: BLE001
            log.warning("résumé LLM impossible (%s) : résumé extractif", e)
    resume = resume or _resume_extractif(course, carte)
    carte["methode"] = methode
    carte["resume"] = resume

    noms = {cle: c["nom"] for cle, c in carte["concepts"].items()}
    slides = [s.model_copy(update={"concepts": [noms[c] for c in carte["slides"][s.id]["concepts"]]})
              for s in course.slides]
    resultat = Course.model_validate(course.model_copy(update={"slides": slides, "resume": resume}).model_dump())
    if sauvegarder:
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "course_map.json").write_text(json.dumps(carte, ensure_ascii=False, indent=2), encoding="utf-8")
        (dossier / "course.json").write_text(resultat.model_dump_json(indent=2), encoding="utf-8")
        _charger_carte.cache_clear()
    return resultat


@lru_cache(maxsize=32)
def _charger_carte(chemin: str, mtime: float) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def charger_carte(course_id: str, dossier: Path | None = None) -> dict:
    """Lire ``course_map.json`` (mis en cache tant que le fichier ne change pas)."""
    chemin = (Path(dossier) if dossier else DOSSIER_PROCESSED / course_id) / "course_map.json"
    if not chemin.is_file():
        raise FileNotFoundError(f"carte absente : {chemin} (lancer build_course_map)")
    return _charger_carte(str(chemin), chemin.stat().st_mtime)


def get_prerequisites(slide_id: str, dossier: Path | None = None) -> list[str]:
    """Ids des slides (antérieures) à connaître pour comprendre ``slide_id``, dans l'ordre du cours.

    Renvoie ``[]`` si la carte du cours n'existe pas encore ou si la slide est inconnue.
    """
    m = re.fullmatch(r"(.+)__s\d{3,}", slide_id)
    if not m:
        raise ValueError(f"slide_id invalide : {slide_id!r}")
    try:
        carte = charger_carte(m.group(1), dossier)
    except FileNotFoundError as e:
        log.warning("%s", e)
        return []
    return list(carte["slides"].get(slide_id, {}).get("prerequis", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H3 — carte du cours (concepts, prérequis, résumé)")
    parser.add_argument("course_ids", nargs="+")
    parser.add_argument("--sans-llm", action="store_true", help="repli heuristique uniquement")
    parser.add_argument("--mermaid", action="store_true", help="écrire aussi course_map.mmd")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for cid in args.course_ids:
        dossier = DOSSIER_PROCESSED / cid
        course = Course.model_validate_json((dossier / "course.json").read_text(encoding="utf-8"))
        course = build_course_map(course, utiliser_llm=False if args.sans_llm else None)
        carte = charger_carte(cid)
        if args.mermaid:
            (dossier / "course_map.mmd").write_text(exporter_mermaid(carte), encoding="utf-8")
        n_prereq = sum(len(c["prerequis"]) for c in carte["concepts"].values())
        print(f"{cid}: {len(carte['concepts'])} concepts, {n_prereq} liens de prérequis ({carte['methode']})")
        print(f"  résumé : {course.resume[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
