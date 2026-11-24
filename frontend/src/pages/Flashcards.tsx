// Mode flashcards : recto / verso au clic, auto-évaluation SM-2 de 0 à 5 (A6).
// Les cartes à réviser viennent de GET /flashcards/due ; s'il n'y en a pas, l'agent Quiz (A2)
// en génère (GET /flashcards) et elles sont enregistrées (POST /flashcards/save) pour l'utilisateur.
import { useEffect, useState } from "react";
import { api, ErreurApi, estAnnulation } from "../api";
import { Attente, Erreur } from "../components/Attente";
import { Icone } from "../components/Icones";
import type { EtatMascotte } from "../components/Mascotte";
import { Citation, TexteEnLigne } from "../components/TexteRiche";
import { formaterDate, useLangue, type CleTexte } from "../i18n";
import type { CarteSRS, Course, EtatSM2 } from "../types";
import { exporterAnki } from "./Quiz";

/** Intervalle (jours) que SM-2 donnera pour la note `q` : même règle qu'agents/srs.py. */
export function intervallePrevu(etat: EtatSM2, q: number): number {
  if (q < 3 || etat.repetitions === 0) return 1;
  if (etat.repetitions === 1) return 6;
  return Math.max(1, Math.floor(Math.round(etat.intervalle * etat.facilite * 1e6) / 1e6 + 0.5));
}

const aujourdhui = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function Flashcards({
  cours,
  portee,
  user,
  surHumeur,
  surAllerSlide,
}: {
  cours: Course;
  portee: number | null;
  user: string;
  surHumeur: (e: EtatMascotte) => void;
  surAllerSlide: (n: number) => void;
}) {
  const { t, langue } = useLangue();
  const [file, setFile] = useState<CarteSRS[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [retournee, setRetournee] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [derniere, setDerniere] = useState<CarteSRS | null>(null);
  const [revues, setRevues] = useState(0);
  const [essai, setEssai] = useState(0);
  const [nouvelles, setNouvelles] = useState(false);
  const [exportEtat, setExportEtat] = useState<string>("");

  const dansPortee = (c: CarteSRS) => portee === null || c.source.numero === portee;

  useEffect(() => {
    let annule = false;
    const ctrl = new AbortController();
    setFile(null);
    setErreur(null);
    surHumeur("reflechit");
    (async () => {
      let dues = nouvelles ? [] : (await api.cartesDues(user, cours.id)).filter(dansPortee);
      if (!dues.length) {
        const generees = await api.flashcards(cours.id, portee, langue, 5, ctrl.signal);
        const enregistrees = generees.length ? await api.sauverFlashcards(user, generees) : [];
        const jour = aujourdhui();
        dues = enregistrees.filter((c) => c.etat.prochaine_revision <= jour && dansPortee(c));
      }
      if (annule) return;
      setFile(dues);
      setRetournee(false);
      surHumeur("");
    })().catch((e) => {
      if (annule || estAnnulation(e)) return;
      setErreur(e instanceof ErreurApi ? e.message : String(e));
      surHumeur("oups");
    });
    return () => {
      annule = true;
      ctrl.abort();
    };
  }, [cours.id, portee, user, langue, essai, nouvelles]); // eslint-disable-line react-hooks/exhaustive-deps

  const carte = file?.[0];

  async function noter(q: number) {
    if (!carte || !retournee || envoi) return;
    setEnvoi(true);
    try {
      const revue = await api.reviser(user, carte.id, q);
      setDerniere(revue);
      setRevues((n) => n + 1);
      surHumeur(q >= 3 ? "contente" : "oups");
      setRetournee(false);
      setFile((f) => (f ?? []).slice(1));
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  }

  // Espace : retourner la carte ; 0 à 5 : noter (une fois la réponse vue).
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement;
      if (cible.closest("input, textarea")) return;
      if (e.key === " " && !cible.closest("button")) {
        e.preventDefault();
        setRetournee((r) => !r);
      } else if (/^[0-5]$/.test(e.key)) noter(Number(e.key));
    };
    addEventListener("keydown", touche);
    return () => removeEventListener("keydown", touche);
  });

  async function exporter() {
    setExportEtat("encours");
    try {
      await exporterAnki(user, cours, portee, langue);
      setExportEtat("ok");
    } catch (e) {
      setExportEtat(e instanceof ErreurApi ? e.message : String(e));
    }
  }

  if (erreur) return <Erreur message={erreur} surReessayer={() => { setErreur(null); setEssai((x) => x + 1); }} />;
  if (!file) return <Attente libelle={t("generation-cartes")} />;

  const outils = (
    <div className="actions" style={{ justifyContent: "center", border: 0, padding: 0 }}>
      <button type="button" className="bouton" onClick={() => { setNouvelles(true); setEssai((x) => x + 1); }}>
        <Icone nom="cartes" />
        <span>{t("nouvelles-cartes")}</span>
      </button>
      <button type="button" className="bouton principal" disabled={exportEtat === "encours"} onClick={exporter}>
        <Icone nom="export" />
        <span>{t("anki")}</span>
      </button>
    </div>
  );
  const retourExport =
    exportEtat === "ok" ? <p className="note-ok">{t("anki-ok")}</p> : exportEtat && exportEtat !== "encours" ? <Erreur message={exportEtat} /> : null;
  const prochaine = derniere && (
    <p className="compte">{t("prochaine", { d: formaterDate(derniere.etat.prochaine_revision, langue) })}</p>
  );

  if (!carte)
    return (
      <section className="panneau score" style={{ display: "flex" }}>
        <h2>{t("cartes-finies")}</h2>
        {prochaine}
        {outils}
        {retourExport}
      </section>
    );

  return (
    <section className="flashcards" style={{ display: "flex" }}>
      <p className="compte">{t("cartes-a-reviser", { n: file.length })}</p>
      <div className="scene">
        <button
          type="button"
          className="flashcard"
          aria-pressed={retournee}
          aria-label={t("retourner")}
          onClick={() => setRetournee((r) => !r)}
        >
          <span className="face recto" aria-hidden={retournee}>
            <span className="cote">{t("question")}</span>
            <span className="contenu">
              <TexteEnLigne texte={carte.recto} />
            </span>
            <span className="indice">{t("indice")}</span>
          </span>
          <span className="face verso" aria-hidden={!retournee}>
            <span className="cote">{t("reponse")}</span>
            <span className="contenu">
              <TexteEnLigne texte={carte.verso} />
            </span>
          </span>
        </button>
      </div>
      <div className="evaluation evaluation-sm2" role="group" aria-label={t("noter-aide")}>
        {[0, 1, 2, 3, 4, 5].map((q) => {
          const jours = intervallePrevu(carte.etat, q);
          return (
            <button
              key={q}
              type="button"
              className={q === 5 ? "bouton principal" : "bouton"}
              disabled={!retournee || envoi}
              onClick={() => noter(q)}
            >
              <span>
                <b className="note">{q}</b> {t(`q${q}` as CleTexte)}
              </span>
              <small>{jours === 1 ? t("demain") : t("dans-j", { n: jours })}</small>
            </button>
          );
        })}
      </div>
      <p className="compte">
        {t("noter-aide")} · {t("source")} : <Citation numero={carte.source.numero} surCitation={surAllerSlide} />
        {revues > 0 && <> · {revues} ✓</>}
      </p>
      {prochaine}
      {outils}
      {retourExport}
    </section>
  );
}
