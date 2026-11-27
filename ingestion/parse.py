"""H1 — Parsers PDF/PPTX, rendu des slides en PNG et OCR.

Point d'entrée : ``parse_course(path) -> Course`` (contrat T0, voir ``docs/schema.md``).

Pour chaque slide (ou page PDF) :

1. texte visible, titre, notes du présentateur (PPTX) et tableaux ;
2. images extraites, dédupliquées, sans les logos répétés sur tout le cours ;
3. rendu PNG à 150 dpi (PPTX : conversion en PDF par LibreOffice, ou PowerPoint sous Windows) ;
4. OCR si la slide n'a pas de texte (RapidOCR, ou Tesseract s'il est installé).

Sorties dans ``data/processed/<course_id>/`` : ``course.json``, ``slides/sNNN.png``, ``images/``.

Usage : ``python -m ingestion.parse <fichier|dossier> [--sans-rendu] [--sans-ocr]``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pymupdf

from schemas import Course, Slide, est_course_id_valide, slide_id

log = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_CACHE = RACINE / "data" / "cache"

DPI = 150
MIN_MOTS = 3                 # en dessous, la slide est considérée « sans texte » → OCR
IMAGE_MIN_COTE = 48          # px : en dessous, icône ou puce décorative ignorée
IMAGE_MIN_OCTETS = 1024
SEUIL_REPETITION = 0.5       # image/ligne présente sur ≥ 50 % des slides = logo / pied de page
MIN_SLIDES_REPETITION = 4
FORMATS_IMAGE = {"png", "jpg", "jpeg"}

_MOTS_FR = {"le", "la", "les", "des", "est", "et", "une", "dans", "pour", "que", "qui", "sur",
            "du", "par", "avec", "ce", "sont", "pas", "au", "aux", "nous", "on", "ou"}
_MOTS_EN = {"the", "is", "and", "of", "to", "in", "for", "that", "with", "are", "this", "on",
            "by", "as", "we", "be", "it", "an", "can", "from", "which", "or"}


# --------------------------------------------------------------------------- structures internes


@dataclass
class _SlideBrute:
    """Contenu d'une slide avant validation par le modèle ``Slide``."""

    titre: str = ""
    lignes: list[str] = field(default_factory=list)
    notes: str = ""
    images: list[str] = field(default_factory=list)
    image_rendu: str | None = None
    ocr: bool = False


# --------------------------------------------------------------------------- identifiants et métadonnées


def course_id_depuis_fichier(path: Path) -> str:
    """Nom du fichier sans extension, ramené à ``[a-z0-9_]`` (règle T0)."""
    ascii_ = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode()
    cid = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")
    if not cid:
        raise ValueError(f"impossible de dériver un course_id de {path.name!r}")
    return cid


def _normaliser_langue(valeur: str) -> str | None:
    v = valeur.strip().lower()
    table = {"fr": "fr", "francais": "fr", "français": "fr", "french": "fr",
             "en": "en", "anglais": "en", "english": "en",
             "ar": "ar", "arabe": "ar", "arabic": "ar", "mixte": "mixte", "mixed": "mixte"}
    return table.get(v)


@lru_cache(maxsize=1)
def _inventaires() -> dict[str, dict[str, str]]:
    """Lignes des inventaires C1/G2 indexées par nom de fichier."""
    lignes: dict[str, dict[str, str]] = {}
    fichiers = sorted((RACINE / "data" / "corpus").glob("inventaire_*.csv"))
    fichiers += sorted((RACINE / "data" / "corpus_extra").glob("inventaire*.csv"))
    for inv in fichiers:
        try:
            with open(inv, encoding="utf-8-sig", newline="") as f:
                for ligne in csv.DictReader(f):
                    nom = Path(ligne.get("fichier", "")).name
                    if nom:
                        lignes[nom] = ligne
        except (OSError, csv.Error) as e:
            log.warning("inventaire illisible %s : %s", inv, e)
    return lignes


def detecter_langue(texte: str) -> str | None:
    """Heuristique par mots-outils FR / EN ; ``None`` si le texte est trop court."""
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ]+", texte.lower())
    fr = sum(m in _MOTS_FR for m in mots)
    en = sum(m in _MOTS_EN for m in mots)
    if fr + en < 10:
        return None
    if min(fr, en) >= 20 and max(fr, en) / min(fr, en) < 1.5:
        return "mixte"
    return "fr" if fr > en else "en"


def _langue(path: Path, inventaire: dict[str, str], texte: str) -> str:
    if (valeur := _normaliser_langue(inventaire.get("langue", ""))) is not None:
        return valeur
    if m := re.search(r"_(fr|en|ar)$", path.stem.lower()):
        return m.group(1)
    return detecter_langue(texte) or "fr"


def _chemin_relatif(path: Path) -> str:
    try:
        return path.resolve().relative_to(RACINE).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _titre_metadonnees(titre: str | None) -> str:
    """Nettoyer un titre de métadonnées (« Microsoft PowerPoint - x.pptx » → « x »)."""
    t = (titre or "").strip()
    t = re.sub(r"^Microsoft (PowerPoint|Word) - ", "", t)
    t = re.sub(r"\.(pptx?|pdf|docx?)$", "", t, flags=re.I)
    return "" if t.lower() in {"", "untitled", "présentation powerpoint", "powerpoint presentation"} else t


# --------------------------------------------------------------------------- nettoyage du texte


_PUCES = set("•◦▪▫‣·∙○●■□-–—*>。、.,;:")


def _ligne_porteuse(ligne: str) -> bool:
    """Vraie si la ligne contient une lettre, un chiffre ou un symbole mathématique."""
    return any(c.isalnum() or (unicodedata.category(c) == "Sm" and c not in _PUCES) for c in ligne)


def _nettoyer_lignes(texte: str) -> list[str]:
    lignes = []
    for brute in texte.splitlines():
        ligne = re.sub(r"\s+", " ", brute).strip()
        if not _ligne_porteuse(ligne) or re.fullmatch(r"\d{1,3}(\s*/\s*\d{1,3})?", ligne):
            continue  # puces isolées, artefacts OCR, numéros de page
        lignes.append(ligne)
    return lignes


def _texte_incomplet(texte_brut: str) -> bool:
    """Couche texte absente ou trouée (puces vides : texte dessiné en vectoriel, p. ex. decktape)."""
    puces_vides = sum(1 for l in texte_brut.splitlines() if l.strip() and l.strip() in _PUCES)
    return _nb_mots(texte_brut) < MIN_MOTS or puces_vides >= 2


def _retirer_lignes_repetees(slides: list[_SlideBrute]) -> None:
    """Retirer en-têtes et pieds de page présents sur la majorité des slides."""
    if len(slides) < MIN_SLIDES_REPETITION:
        return
    compte = Counter(l for s in slides for l in set(s.lignes) if len(l) <= 80)
    repetees = {l for l, n in compte.items() if n / len(slides) >= SEUIL_REPETITION}
    titres = {s.titre for s in slides}
    repetees -= titres  # un titre de section répété reste utile
    if repetees:
        log.debug("lignes répétées retirées : %s", sorted(repetees))
        for s in slides:
            s.lignes = [l for l in s.lignes if l not in repetees]


def _nb_mots(texte: str) -> int:
    return len(re.findall(r"\w{2,}", texte))


# --------------------------------------------------------------------------- OCR


def _tesseract() -> str | None:
    for candidat in (shutil.which("tesseract"), r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
        if candidat and Path(candidat).is_file():
            return candidat
    return None


def backend_ocr() -> str:
    """``OCR_BACKEND`` : ``auto`` (défaut) | ``tesseract`` | ``rapidocr`` | ``aucun``."""
    choix = os.getenv("OCR_BACKEND", "auto").strip().lower()
    if choix != "auto":
        return choix
    return "tesseract" if _tesseract() else "rapidocr"


@lru_cache(maxsize=1)
def _moteur_rapidocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_rapidocr(pix: pymupdf.Pixmap) -> str:
    import numpy as np

    if pix.alpha or pix.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix, 0)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
    resultats, _ = _moteur_rapidocr()(image)
    if not resultats:
        return ""
    # Regrouper les boîtes en lignes (même bande verticale), puis lire de gauche à droite.
    boites = []
    for boite, texte, _score in resultats:
        ys = [p[1] for p in boite]
        boites.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(p[0] for p in boite), texte))
    boites.sort()
    lignes: list[list[tuple[float, str]]] = []
    y_courant, hauteur = None, 0.0
    for y, h, x, texte in boites:
        if y_courant is None or abs(y - y_courant) > max(hauteur, h) * 0.6:
            lignes.append([])
            y_courant, hauteur = y, h
        lignes[-1].append((x, texte))
    return "\n".join(" ".join(t for _, t in sorted(ligne)) for ligne in lignes)


def _ocr_tesseract(page: pymupdf.Page, langue: str) -> str:
    exe = _tesseract()
    if exe and "TESSDATA_PREFIX" not in os.environ:
        os.environ["TESSDATA_PREFIX"] = str(Path(exe).parent / "tessdata")
    langues = {"fr": "fra+eng", "en": "eng", "ar": "ara+eng"}.get(langue, "fra+eng")
    tp = page.get_textpage_ocr(language=langues, dpi=300, full=True)
    return page.get_text("text", textpage=tp)


def ocr_page(page: pymupdf.Page, langue: str = "fr") -> str:
    """Texte OCR d'une page PyMuPDF ; chaîne vide si l'OCR est désactivé ou échoue."""
    backend = backend_ocr()
    try:
        if backend == "tesseract":
            return _ocr_tesseract(page, langue)
        if backend == "rapidocr":
            return _ocr_rapidocr(page.get_pixmap(dpi=200))
    except Exception as e:  # noqa: BLE001 - l'OCR ne doit jamais bloquer l'ingestion
        log.warning("OCR %s en échec sur la page %d : %s", backend, page.number + 1, e)
    return ""


# --------------------------------------------------------------------------- images


def _sauver_image(donnees: bytes, ext: str, dossier: Path, nom: str) -> str | None:
    """Écrire une image en PNG/JPEG ; renvoyer le chemin relatif ``images/<nom>.<ext>``."""
    ext = ext.lower()
    if ext not in FORMATS_IMAGE:
        try:
            pix = pymupdf.Pixmap(donnees)
            if pix.n - pix.alpha >= 4:  # CMYK
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            donnees, ext = pix.tobytes("png"), "png"
        except Exception:  # noqa: BLE001 - format exotique (EMF, WMF…) : on renonce à cette image
            return None
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{nom}.{ext}"
    if not fichier.exists():
        fichier.write_bytes(donnees)
    return f"images/{fichier.name}"


def _image_utile(largeur: int, hauteur: int, taille: int) -> bool:
    return largeur >= IMAGE_MIN_COTE and hauteur >= IMAGE_MIN_COTE and taille >= IMAGE_MIN_OCTETS


# --------------------------------------------------------------------------- PDF


def _titre_pdf(page: pymupdf.Page) -> str:
    """Ligne écrite dans la plus grande police, dans le tiers haut de la page."""
    try:
        blocs = page.get_text("dict")["blocks"]
    except Exception:  # noqa: BLE001
        return ""
    limite = page.rect.y0 + page.rect.height * 0.35
    candidats: list[tuple[float, float, str]] = []
    tailles: list[float] = []
    for bloc in blocs:
        for ligne in bloc.get("lines", []):
            spans = [s for s in ligne["spans"] if s["text"].strip()]
            if not spans:
                continue
            taille = max(s["size"] for s in spans)
            tailles.extend(s["size"] for s in spans)
            texte = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
            if ligne["bbox"][1] <= limite and len(texte) >= 2:
                candidats.append((taille, -ligne["bbox"][1], texte))
    if not candidats:
        return ""
    taille_max = max(c[0] for c in candidats)
    mediane = sorted(tailles)[len(tailles) // 2]
    if taille_max < mediane * 1.1 and len(tailles) > 3:
        return ""  # pas de ligne qui se distingue : pas de titre
    # Les lignes de la plus grande taille, de haut en bas (titres sur deux lignes).
    morceaux = [t for s, _, t in sorted(candidats, key=lambda c: -c[1]) if s >= taille_max - 0.5]
    return " ".join(morceaux)[:200]


def _parser_pdf(doc: pymupdf.Document, dossier: Path, *, rendu: bool, ocr: bool,
                langue_ocr: str, numeros_pages: list[int | None] | None = None,
                extraire_images: bool = True) -> list[_SlideBrute]:
    """Lire chaque page ; ``numeros_pages`` associe une slide à une page (PPTX converti)."""
    pages = numeros_pages if numeros_pages is not None else list(range(len(doc)))
    # Logos : xref présent sur la majorité des pages.
    occurrences = Counter()
    for p in pages:
        if p is not None:
            occurrences.update({img[0] for img in doc[p].get_images(full=True)})
    seuil_logo = max(2, int(len(pages) * SEUIL_REPETITION)) if len(pages) >= MIN_SLIDES_REPETITION else None

    slides: list[_SlideBrute] = []
    for numero, p in enumerate(pages, start=1):
        brute = _SlideBrute()
        slides.append(brute)
        if p is None:
            continue
        page = doc[p]
        if rendu:
            dossier_slides = dossier / "slides"
            dossier_slides.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(dpi=DPI).save(dossier_slides / f"s{numero:03d}.png")
            brute.image_rendu = f"slides/s{numero:03d}.png"
        if numeros_pages is not None:
            continue  # PPTX : texte et images viennent de python-pptx
        brute.titre = _titre_pdf(page)
        texte_brut = page.get_text("text", sort=True)
        brute.lignes = _nettoyer_lignes(texte_brut)
        if extraire_images:
            for xref in dict.fromkeys(img[0] for img in page.get_images(full=True)):
                if seuil_logo and occurrences[xref] >= seuil_logo:
                    continue
                try:
                    info = doc.extract_image(xref)
                except Exception:  # noqa: BLE001
                    continue
                if not info or not _image_utile(info["width"], info["height"], len(info["image"])):
                    continue
                if chemin := _sauver_image(info["image"], info["ext"], dossier / "images", f"x{xref}"):
                    brute.images.append(chemin)
        if ocr and _texte_incomplet(texte_brut):
            _appliquer_ocr(brute, page, langue_ocr)
    return slides


def _appliquer_ocr(brute: _SlideBrute, page: pymupdf.Page, langue: str) -> None:
    """Remplacer le texte de la slide par l'OCR s'il apporte nettement plus de mots."""
    actuel = _nb_mots("\n".join(brute.lignes))
    lignes = _nettoyer_lignes(ocr_page(page, langue))
    trouve = _nb_mots("\n".join(lignes))
    if trouve >= MIN_MOTS and trouve > actuel * 1.3:
        brute.lignes = lignes
        brute.ocr = True
        if not brute.titre:
            brute.titre = next((l for l in lignes[:2] if len(l) <= 80 and _nb_mots(l) >= 1), "")


# --------------------------------------------------------------------------- PPTX


def _soffice() -> str | None:
    for candidat in (shutil.which("soffice"), shutil.which("libreoffice"),
                     r"C:\Program Files\LibreOffice\program\soffice.exe",
                     "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if candidat and Path(candidat).is_file():
            return candidat
    return None


_SCRIPT_POWERPOINT = r"""
$ErrorActionPreference = 'Stop'
$pp = New-Object -ComObject PowerPoint.Application
try {
  $p = $pp.Presentations.Open($env:PPTX_ENTREE, -1, 0, 0)
  try { $p.ExportAsFixedFormat($env:PDF_SORTIE, 2, 1, 0, 1, 1, -1) }
  catch { $p.SaveAs($env:PDF_SORTIE, 32) }
  $p.Close()
} finally { $pp.Quit() }
"""


def convertir_pptx_en_pdf(path: Path, cache: Path | None = None) -> Path | None:
    """Convertir un PPTX en PDF (LibreOffice, sinon PowerPoint sous Windows), avec cache.

    Renvoie ``None`` si aucun convertisseur n'est disponible.
    """
    cache = cache or DOSSIER_CACHE / "pptx_pdf"
    cache.mkdir(parents=True, exist_ok=True)
    empreinte = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    cible = cache / f"{course_id_depuis_fichier(path)}_{empreinte}.pdf"
    if cible.is_file():
        return cible

    if soffice := _soffice():
        with_tmp = cache / f"tmp_{empreinte}"
        with_tmp.mkdir(exist_ok=True)
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(with_tmp),
                            str(path.resolve())], check=True, capture_output=True, timeout=300)
            produit = with_tmp / f"{path.stem}.pdf"
            if produit.is_file():
                produit.replace(cible)
                return cible
        except (subprocess.SubprocessError, OSError) as e:
            log.warning("LibreOffice en échec sur %s : %s", path.name, e)
        finally:
            shutil.rmtree(with_tmp, ignore_errors=True)

    if sys.platform == "win32":
        env = {**os.environ, "PPTX_ENTREE": str(path.resolve()), "PDF_SORTIE": str(cible.resolve())}
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT_POWERPOINT],
                           check=True, capture_output=True, timeout=300, env=env)
            if cible.is_file():
                return cible
        except (subprocess.SubprocessError, OSError) as e:
            log.warning("PowerPoint en échec sur %s : %s", path.name, e)

    log.warning("aucun convertisseur PPTX→PDF (LibreOffice ou PowerPoint) : pas de rendu pour %s", path.name)
    return None


def _formes(formes, profondeur: int = 0):
    """Parcourir les formes, groupes compris, dans l'ordre de lecture (haut → bas, gauche → droite)."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    triees = sorted(formes, key=lambda f: ((f.top or 0) // 100000, f.left or 0))
    for forme in triees:
        if forme.shape_type == MSO_SHAPE_TYPE.GROUP and profondeur < 5:
            yield from _formes(forme.shapes, profondeur + 1)
        else:
            yield forme


def _texte_forme(forme) -> list[str]:
    lignes: list[str] = []
    if getattr(forme, "has_text_frame", False) and forme.has_text_frame:
        lignes += [p.text for p in forme.text_frame.paragraphs]
    if getattr(forme, "has_table", False) and forme.has_table:
        for rangee in forme.table.rows:
            cellules = [re.sub(r"\s+", " ", c.text).strip() for c in rangee.cells]
            if any(cellules):
                lignes.append(" | ".join(cellules))
    if getattr(forme, "has_chart", False) and forme.has_chart:
        graphique = forme.chart
        titre = graphique.chart_title.text_frame.text if graphique.has_title else ""
        series = ", ".join(s.name for s in graphique.plots[0].series) if graphique.plots else ""
        lignes.append(f"[Graphique] {titre} {('— séries : ' + series) if series else ''}".strip())
    return lignes


def _image_forme(forme):
    try:
        return forme.image  # Picture, ou placeholder contenant une image
    except (AttributeError, ValueError):
        return None


def _parser_pptx(path: Path, dossier: Path, *, rendu: bool, ocr: bool, langue_ocr: str,
                 extraire_images: bool = True) -> tuple[list[_SlideBrute], str]:
    from pptx import Presentation
    from PIL import Image

    prs = Presentation(str(path))
    slides_pptx = list(prs.slides)
    titre_doc = _titre_metadonnees(prs.core_properties.title)

    # Logos : même image (empreinte) sur la majorité des slides.
    empreintes: list[set[str]] = []
    for s in slides_pptx:
        vues = set()
        for f in _formes(s.shapes):
            if (img := _image_forme(f)) is not None:
                vues.add(img.sha1)
        empreintes.append(vues)
    compte = Counter(h for vues in empreintes for h in vues)
    n = len(slides_pptx)
    logos = {h for h, c in compte.items() if n >= MIN_SLIDES_REPETITION and c / n >= SEUIL_REPETITION}

    slides: list[_SlideBrute] = []
    for s in slides_pptx:
        brute = _SlideBrute()
        titre_forme = s.shapes.title
        brute.titre = re.sub(r"\s+", " ", titre_forme.text).strip() if titre_forme is not None else ""
        lignes: list[str] = []
        for forme in _formes(s.shapes):
            lignes += _texte_forme(forme)
            img = _image_forme(forme) if extraire_images else None
            if img is None or img.sha1 in logos:
                continue
            try:
                largeur, hauteur = Image.open(io.BytesIO(img.blob)).size
            except Exception:  # noqa: BLE001 - EMF/WMF illisibles par Pillow
                continue
            if _image_utile(largeur, hauteur, len(img.blob)):
                chemin = _sauver_image(img.blob, img.ext, dossier / "images", img.sha1[:16])
                if chemin and chemin not in brute.images:
                    brute.images.append(chemin)
        brute.lignes = _nettoyer_lignes("\n".join(lignes))
        if not brute.titre and brute.lignes and len(brute.lignes[0]) <= 100:
            brute.titre = brute.lignes[0]
        if s.has_notes_slide and s.notes_slide.notes_text_frame is not None:
            brute.notes = "\n".join(_nettoyer_lignes(s.notes_slide.notes_text_frame.text))
        slides.append(brute)

    if rendu or ocr:
        pdf = convertir_pptx_en_pdf(path)
        if pdf is not None:
            with pymupdf.open(pdf) as doc:
                caches = [s._element.get("show") == "0" for s in slides_pptx]
                if len(doc) == n:
                    pages: list[int | None] = list(range(n))
                elif len(doc) == n - sum(caches):  # slides masquées absentes du PDF
                    it = iter(range(len(doc)))
                    pages = [None if c else next(it) for c in caches]
                else:
                    log.warning("%s : %d pages PDF pour %d slides, rendus ignorés", path.name, len(doc), n)
                    pages = [None] * n
                rendus = _parser_pdf(doc, dossier, rendu=rendu, ocr=False, langue_ocr=langue_ocr,
                                     numeros_pages=pages)
                for brute, r, p in zip(slides, rendus, pages):
                    brute.image_rendu = r.image_rendu
                    # Slide sans texte (capture d'écran, scan) : OCR sur le rendu.
                    if ocr and p is not None and _nb_mots("\n".join(brute.lignes)) < MIN_MOTS:
                        _appliquer_ocr(brute, doc[p], langue_ocr)
    return slides, titre_doc


# --------------------------------------------------------------------------- point d'entrée


def parse_course(path: Path | str, course_id: str | None = None, *,
                 dossier_sortie: Path | None = None, rendu: bool = True, ocr: bool = True,
                 extraire_images: bool = True, sauvegarder: bool = True) -> Course:
    """Lire un cours PDF ou PPTX et renvoyer un ``Course`` au format T0 (champs H1 remplis).

    - ``rendu`` : produire ``slides/sNNN.png`` (150 dpi) ;
    - ``ocr`` : OCR des slides sans texte ;
    - ``rendu=False, ocr=False, extraire_images=False`` : version « texte brut » rapide ;
    - ``sauvegarder`` : écrire ``course.json`` dans le dossier de sortie.

    Le dossier de sortie par défaut est ``data/processed/<course_id>/``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    format_ = path.suffix.lower().lstrip(".")
    if format_ not in ("pdf", "pptx"):
        raise ValueError(f"format non pris en charge : {path.suffix} (attendu .pdf ou .pptx)")
    course_id = course_id or course_id_depuis_fichier(path)
    if not est_course_id_valide(course_id):
        raise ValueError(f"course_id invalide : {course_id!r} (attendu [a-z0-9_])")
    dossier = Path(dossier_sortie) if dossier_sortie else DOSSIER_PROCESSED / course_id
    dossier.mkdir(parents=True, exist_ok=True)

    inventaire = _inventaires().get(path.name, {})
    langue_ocr = _normaliser_langue(inventaire.get("langue", "")) or (
        m.group(1) if (m := re.search(r"_(fr|en|ar)$", path.stem.lower())) else "fr")

    if format_ == "pdf":
        with pymupdf.open(path) as doc:
            if doc.needs_pass and not doc.authenticate(""):
                raise ValueError(f"PDF protégé par mot de passe : {path.name}")
            titre_doc = _titre_metadonnees(doc.metadata.get("title") if doc.metadata else "")
            brutes = _parser_pdf(doc, dossier, rendu=rendu, ocr=ocr, langue_ocr=langue_ocr,
                                 extraire_images=extraire_images)
    else:
        brutes, titre_doc = _parser_pptx(path, dossier, rendu=rendu, ocr=ocr, langue_ocr=langue_ocr,
                                         extraire_images=extraire_images)
    if not brutes:
        raise ValueError(f"{path.name} ne contient aucune slide")

    _retirer_lignes_repetees(brutes)
    texte_total = "\n".join(l for b in brutes for l in b.lignes)
    titre = (inventaire.get("titre") or titre_doc or next((b.titre for b in brutes if b.titre), "")
             or course_id).strip()
    source_url = inventaire.get("source", "").strip()

    slides = [
        Slide(
            id=slide_id(course_id, numero),
            course_id=course_id,
            numero=numero,
            titre=b.titre,
            texte="\n".join(b.lignes),
            notes=b.notes,
            image_rendu=b.image_rendu,
            images=b.images,
            ocr=b.ocr,
        )
        for numero, b in enumerate(brutes, start=1)
    ]
    course = Course(
        id=course_id,
        titre=titre,
        fichier_source=_chemin_relatif(path),
        format=format_,
        langue=_langue(path, inventaire, texte_total),
        source_url=source_url if source_url.startswith("http") else None,
        nombre_slides=len(slides),
        slides=slides,
    )
    if sauvegarder:
        sauvegarder_course(course, dossier)
    return course


def sauvegarder_course(course: Course, dossier: Path | None = None) -> Path:
    """Écrire ``course.json`` (par défaut dans ``data/processed/<course_id>/``)."""
    dossier = Path(dossier) if dossier else DOSSIER_PROCESSED / course.id
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "course.json"
    cible.write_text(course.model_dump_json(indent=2), encoding="utf-8")
    return cible


def charger_course(course_id: str, dossier: Path | None = None) -> Course:
    """Relire ``course.json`` produit par l'ingestion."""
    dossier = Path(dossier) if dossier else DOSSIER_PROCESSED / course_id
    return Course.model_validate_json((dossier / "course.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- CLI


def _fichiers(cibles: list[Path]) -> list[Path]:
    trouves: list[Path] = []
    for cible in cibles:
        if cible.is_dir():
            trouves += sorted(p for p in cible.rglob("*") if p.suffix.lower() in (".pdf", ".pptx")
                              and "_local" not in p.parts)
        else:
            trouves.append(cible)
    return trouves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H1 — ingestion PDF/PPTX au format T0")
    parser.add_argument("cibles", nargs="+", type=Path, help="fichiers .pdf/.pptx ou dossiers")
    parser.add_argument("--sans-rendu", action="store_true", help="ne pas produire les PNG")
    parser.add_argument("--sans-ocr", action="store_true", help="désactiver l'OCR")
    parser.add_argument("--texte-brut", action="store_true",
                        help="version rapide : texte seul (ni rendu, ni OCR, ni images)")
    parser.add_argument("--sortie", type=Path, help="dossier racine de sortie (défaut data/processed)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    erreurs = 0
    for fichier in _fichiers(args.cibles):
        debut = time.perf_counter()
        try:
            course = parse_course(
                fichier,
                dossier_sortie=(args.sortie / course_id_depuis_fichier(fichier)) if args.sortie else None,
                rendu=not (args.sans_rendu or args.texte_brut),
                ocr=not (args.sans_ocr or args.texte_brut),
                extraire_images=not args.texte_brut,
            )
        except Exception as e:  # noqa: BLE001 - continuer sur les autres fichiers
            erreurs += 1
            print(f"ÉCHEC {fichier} : {e}")
            continue
        n_ocr = sum(s.ocr for s in course.slides)
        n_img = sum(len(s.images) for s in course.slides)
        vides = sum(not s.texte for s in course.slides)
        print(f"{course.id:<50} {course.format:4} {course.langue:5} {course.nombre_slides:3} slides  "
              f"{n_img:3} images  {n_ocr:2} OCR  {vides:2} vides  {time.perf_counter() - debut:5.1f}s")
    return 1 if erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main())
