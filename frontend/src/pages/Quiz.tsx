// Page Quiz (maquette D2 quiz.html) : QCM une question à la fois, score final, mode flashcards.
import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi, estAnnulation, telecharger } from "../api";
import { Attente, Erreur } from "../components/Attente";
import { Icone } from "../components/Icones";
import { Mascotte, type EtatMascotte } from "../components/Mascotte";
import { Citation, TexteEnLigne } from "../components/TexteRiche";
import { useLangue } from "../i18n";
import type { Course, LangueUI, QCM } from "../types";
import { Flashcards } from "./Flashcards";

export type ModeQuiz = "qcm" | "flashcards";

interface Props {
  cours: Course;
  portee: number | null; // slide ciblée, ou tout le cours
  surPortee: (n: number | null) => void;
  mode: ModeQuiz;
  surMode: (m: ModeQuiz) => void;
  user: string;
  surAllerSlide: (n: number) => void;
  surTestee: (n: number) => void;
}

/** Exporter le deck Anki ; si aucune carte n'est encore enregistrée, en générer d'abord. */
export async function exporterAnki(user: string, cours: Course, portee: number | null, langue: LangueUI) {
  try {
    telecharger(await api.exporterAnki(user, cours.id), `${cours.id}.apkg`);
  } catch (e) {
    if (!(e instanceof ErreurApi) || e.statut !== 404) throw e;
    const cartes = await api.flashcards(cours.id, portee, langue);
    if (cartes.length) await api.sauverFlashcards(user, cartes);
    telecharger(await api.exporterAnki(user, cours.id), `${cours.id}.apkg`);
  }
}

export function PageQuiz({ cours, portee, surPortee, mode, surMode, user, surAllerSlide, surTestee }: Props) {
  const { t } = useLangue();
  const [humeur, setHumeur] = useState<EtatMascotte>("");

  return (
    <main className="page-quiz">
      <div className="entete-quiz">
        <div className="titre-quiz">
          <Mascotte etat={humeur} />
          <div>
            <h1>{t("titre")}</h1>
            <p>
              {portee ? t("sous-titre-slide", { n: portee }) : t("sous-titre-cours", { cours: cours.titre })}
              {portee && (
                <>
                  {" · "}
                  <button type="button" className="lien-discret" onClick={() => surPortee(null)}>
                    {t("tout-le-cours")}
                  </button>
                </>
              )}
            </p>
          </div>
        </div>
        <div className="modes" role="group" aria-label="Mode">
          {(["qcm", "flashcards"] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => surMode(m)}>
              {t(m === "qcm" ? "qcm" : "flash")}
            </button>
          ))}
        </div>
      </div>
      {mode === "qcm" ? (
        <Qcm
          key={`${cours.id}|${portee}`}
          cours={cours}
          portee={portee}
          user={user}
          surHumeur={setHumeur}
          surAllerSlide={surAllerSlide}
          surTestee={surTestee}
          versCartes={() => surMode("flashcards")}
        />
      ) : (
        <Flashcards key={`${cours.id}|${portee}`} cours={cours} portee={portee} user={user} surHumeur={setHumeur} surAllerSlide={surAllerSlide} />
      )}
    </main>
  );
}

function Qcm({
  cours,
  portee,
  user,
  surHumeur,
  surAllerSlide,
  surTestee,
  versCartes,
}: {
  cours: Course;
  portee: number | null;
  user: string;
  surHumeur: (e: EtatMascotte) => void;
  surAllerSlide: (n: number) => void;
  surTestee: (n: number) => void;
  versCartes: () => void;
}) {
  const { t, langue } = useLangue();
  const [questions, setQuestions] = useState<QCM[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);
  const [i, setI] = useState(0);
  const [reponses, setReponses] = useState<number[]>([]);
  const [fini, setFini] = useState(false);
  const [ctrl, setCtrl] = useState<AbortController | null>(null);

  useEffect(() => {
    const c = new AbortController();
    setCtrl(c);
    setQuestions(null);
    setErreur(null);
    setMessage(null);
    surHumeur("reflechit");
    api
      .quiz(cours.id, portee, langue, portee ? 3 : 5, c.signal)
      .then(({ qcm, message }) => {
        setQuestions(qcm);
        setMessage(message);
        setI(0);
        setReponses([]);
        setFini(false);
        surHumeur(qcm.length ? "" : "oups");
      })
      .catch((e) => {
        if (estAnnulation(e)) return;
        setErreur(e instanceof ErreurApi ? e.message : String(e));
        surHumeur("oups");
      });
    return () => c.abort();
  }, [cours.id, portee, langue, essai]); // eslint-disable-line react-hooks/exhaustive-deps

  const repondre = useCallback(
    (n: number) => {
      if (!questions || reponses.length > i) return;
      const q = questions[i];
      const juste = n === q.bonne_reponse;
      setReponses((r) => [...r, n]);
      surTestee(q.source.numero);
      surHumeur(juste ? "contente" : "oups");
    },
    [questions, reponses.length, i, surHumeur, surTestee],
  );

  // Touches 1 à 4 (ou A à D) pour répondre, Entrée pour passer à la suite.
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea") || fini || !questions?.length) return;
      const k = "1234".indexOf(e.key) >= 0 ? "1234".indexOf(e.key) : "abcd".indexOf(e.key.toLowerCase());
      if (k >= 0 && e.key.length === 1) repondre(k);
    };
    addEventListener("keydown", touche);
    return () => removeEventListener("keydown", touche);
  }, [repondre, fini, questions]);

  const recommencer = () => {
    setI(0);
    setReponses([]);
    setFini(false);
    surHumeur("");
  };

  if (erreur) return <Erreur message={erreur} surReessayer={() => setEssai((x) => x + 1)} />;
  if (!questions)
    return (
      <section className="panneau carte-question">
        <Attente libelle={t("generation-quiz")} surAnnuler={() => { ctrl?.abort(); setErreur(t("annuler")); }} />
      </section>
    );
  if (!questions.length)
    return (
      <section className="panneau carte-question">
        <Erreur message={message ?? t("quiz-vide")} surReessayer={() => setEssai((x) => x + 1)} />
      </section>
    );

  const total = questions.length;
  const resultats = reponses.map((r, k) => r === questions[k].bonne_reponse);

  if (fini) {
    const bonnes = resultats.filter(Boolean).length;
    const fausses = questions.filter((_, k) => !resultats[k]);
    return (
      <Score
        bonnes={bonnes}
        total={total}
        resultats={resultats}
        fausses={fausses}
        surAllerSlide={surAllerSlide}
        recommencer={recommencer}
        versCartes={versCartes}
        exporter={() => exporterAnki(user, cours, portee, langue)}
      />
    );
  }

  const q = questions[i];
  const repondue = reponses.length > i;
  const choisie = reponses[i];
  const juste = choisie === q.bonne_reponse;
  const derniere = i === total - 1;

  return (
    <>
      <div className="progression-quiz">
        <div className="etapes" aria-hidden="true" style={{ ["--n" as string]: total }}>
          {questions.map((_, n) => (
            <span key={n} className={n < resultats.length ? (resultats[n] ? "juste" : "fausse") : n === i ? "courante" : ""} />
          ))}
        </div>
        <span className="compteur">
          {i + 1} / {total}
        </span>
      </div>

      <section className="panneau carte-question" aria-live="polite">
        <h2>
          <TexteEnLigne texte={q.question} />
        </h2>
        <div className="choix">
          {q.choix.map((texte, n) => {
            const bonne = repondue && n === q.bonne_reponse;
            const mauvaise = repondue && n === choisie && !juste;
            return (
              <button
                key={n}
                type="button"
                className={bonne ? "bonne" : mauvaise ? "mauvaise" : undefined}
                disabled={repondue}
                onClick={() => repondre(n)}
              >
                <span className="lettre">
                  {bonne ? (
                    <Icone nom="ok" label={t("bonne-reponse")} />
                  ) : mauvaise ? (
                    <Icone nom="ko" label={t("mauvaise-reponse")} />
                  ) : (
                    "ABCD"[n]
                  )}
                </span>
                <span>
                  <TexteEnLigne texte={texte} />
                </span>
              </button>
            );
          })}
        </div>
        {repondue && (
          <div className={`retour visible ${juste ? "ok" : "ko"}`}>
            <Mascotte etat={juste ? "contente" : "oups"} />
            <p>
              <strong>{t(juste ? "exact" : "presque")}</strong>{" "}
              <TexteEnLigne texte={q.explication} surCitation={surAllerSlide} />
            </p>
          </div>
        )}
        <div className="pied">
          <div className="infos">
            <span>
              {t("source")} : <Citation numero={q.source.numero} surCitation={surAllerSlide} />
            </span>
            <span className="bloom">
              <Icone nom="niveau" />
              <span>{t(q.niveau_bloom)}</span>
            </span>
          </div>
          <button
            type="button"
            className="bouton principal"
            disabled={!repondue}
            ref={(b) => {
              if (b && repondue) b.focus();
            }}
            onClick={() => (derniere ? setFini(true) : setI(i + 1))}
          >
            <span>{t(derniere ? "voir-score" : "suivante")}</span>
            <Icone nom="droite" miroir />
          </button>
        </div>
      </section>
    </>
  );
}

function Score({
  bonnes,
  total,
  resultats,
  fausses,
  surAllerSlide,
  recommencer,
  versCartes,
  exporter,
}: {
  bonnes: number;
  total: number;
  resultats: boolean[];
  fausses: QCM[];
  surAllerSlide: (n: number) => void;
  recommencer: () => void;
  versCartes: () => void;
  exporter: () => Promise<void>;
}) {
  const { t } = useLangue();
  const [export_, setExport] = useState<"" | "encours" | "ok" | string>("");
  const message = bonnes === total ? t("tout-acquis") : bonnes === 0 ? t("rien-acquis") : t("a-revoir", { n: total - bonnes });

  async function lancerExport() {
    setExport("encours");
    try {
      await exporter();
      setExport("ok");
    } catch (e) {
      setExport(e instanceof ErreurApi ? e.message : String(e));
    }
  }

  return (
    <section className="panneau score" style={{ display: "flex" }} aria-live="polite">
      <Mascotte etat={bonnes ? "contente" : ""} />
      <div className="resultat">
        {bonnes}
        <small> / {total}</small>
      </div>
      <div className="pastilles" aria-hidden="true">
        {resultats.map((ok, k) => (
          <span
            key={k}
            className={ok ? "disque vert" : "disque"}
            style={{ background: ok ? undefined : "var(--rouge)", animationDelay: `${80 + k * 70}ms` }}
          >
            <Icone nom={ok ? "ok" : "ko"} />
          </span>
        ))}
      </div>
      <h2>{message}</h2>
      {fausses.length > 0 && (
        <div className="revoir">
          {fausses.map((q, k) => (
            <div key={k}>
              <span>
                <TexteEnLigne texte={q.question} />
              </span>
              <Citation numero={q.source.numero} surCitation={surAllerSlide} />
            </div>
          ))}
        </div>
      )}
      <div className="actions" style={{ justifyContent: "center", border: 0, padding: 0 }}>
        <button type="button" className="bouton" onClick={recommencer}>
          <Icone nom="recommencer" />
          <span>{t("recommencer")}</span>
        </button>
        <button type="button" className="bouton" onClick={versCartes}>
          <Icone nom="cartes" />
          <span>{t("reviser")}</span>
        </button>
        <button type="button" className="bouton principal" disabled={export_ === "encours"} onClick={lancerExport}>
          <Icone nom="export" />
          <span>{t("anki")}</span>
        </button>
      </div>
      {export_ === "ok" && <p className="note-ok">{t("anki-ok")}</p>}
      {export_ && export_ !== "ok" && export_ !== "encours" && <Erreur message={export_} />}
    </section>
  );
}
