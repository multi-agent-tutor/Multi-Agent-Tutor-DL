// Page Cours (maquette D2 cours.html) : slide à gauche, explication et questions à droite.
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type RefObject } from "react";
import { api, ErreurApi, estAnnulation, lireReponseAgent, urlImageSlide } from "../api";
import { Attente, Erreur } from "../components/Attente";
import { Icone } from "../components/Icones";
import { Mascotte, type EtatMascotte } from "../components/Mascotte";
import { Citation, Formule, TexteEnLigne, TexteRiche } from "../components/TexteRiche";
import { useLangue, type CleTexte } from "../i18n";
import { MAX_HISTORIQUE, type AgentResponse, type Course, type Message, type Niveau, type Ressource, type Slide, type Source } from "../types";
import type { Maitrise } from "../maitrise";

const NIVEAUX: Niveau[] = ["debutant", "intermediaire", "avance"];

interface Props {
  cours: Course;
  numero: number;
  surNumero: (n: number) => void;
  niveau: Niveau;
  surNiveau: (n: Niveau) => void;
  maitrise: Maitrise;
  surMaitrise: (n: number, etat: "vue" | "comprise" | "testee") => void;
  surTester: (n: number) => void;
}

export function PageCours({ cours, numero, surNumero, niveau, surNiveau, maitrise, surMaitrise, surTester }: Props) {
  const cadre = useRef<HTMLDivElement>(null);
  const total = cours.nombre_slides;
  const slide = cours.slides[numero - 1];

  const aller = (n: number, repere = false) => {
    const cible = Math.min(total, Math.max(1, n));
    surNumero(cible);
    if (repere && cadre.current) {
      // Une source cliquée amène à sa slide, qui s'éclaire brièvement en or.
      const c = cadre.current;
      c.classList.remove("repere");
      void c.offsetWidth;
      c.classList.add("repere");
      if (innerWidth <= 980) c.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };
  const allerSource = (n: number) => aller(n, true);

  useEffect(() => {
    surMaitrise(numero, "vue");
  }, [numero]); // eslint-disable-line react-hooks/exhaustive-deps

  // Flèches du clavier hors des champs : slide précédente / suivante (inversées en RTL).
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement;
      if (cible.closest("input, textarea, [contenteditable]") || e.altKey || e.ctrlKey || e.metaKey) return;
      const rtl = document.documentElement.dir === "rtl";
      if (e.key === "ArrowRight") aller(numero + (rtl ? -1 : 1));
      if (e.key === "ArrowLeft") aller(numero + (rtl ? 1 : -1));
    };
    addEventListener("keydown", touche);
    return () => removeEventListener("keydown", touche);
  });

  return (
    <>
      <main className="page-cours">
        <div className="colonne slide-fixe">
          <VueSlide slide={slide} total={total} cadre={cadre} surCitation={allerSource} />
          <Navigation numero={numero} total={total} aller={aller} maitrise={maitrise} />
        </div>
        <div className="colonne">
          <Explication
            cours={cours}
            slide={slide}
            niveau={niveau}
            surNiveau={surNiveau}
            surCitation={allerSource}
            surComprise={() => surMaitrise(numero, "comprise")}
            surTester={() => surTester(numero)}
          />
          <Questions cours={cours} slide={slide} niveau={niveau} surCitation={allerSource} />
        </div>
      </main>
      <BarreMobile surTester={() => surTester(numero)} />
    </>
  );
}

// ---------------------------------------------------------------- slide

/** Cours dont le rendu PNG n'a pas pu être chargé : on n'essaie plus pour les autres slides (session). */
const imagesIndisponibles = new Set<string>();

function VueSlide({
  slide,
  total,
  cadre,
  surCitation,
}: {
  slide: Slide;
  total: number;
  cadre: RefObject<HTMLDivElement | null>;
  surCitation: (n: number) => void;
}) {
  const { t } = useLangue();
  const titre = slide.titre || `${t("slide")} ${slide.numero}`;
  // Rendu PNG de la slide (ingestion H1) s'il existe et que l'API le sert ; sinon, affichage texte.
  const [imageEchouee, setImageEchouee] = useState(false);
  useEffect(() => setImageEchouee(false), [slide.id]);
  const image =
    slide.image_rendu && !imageEchouee && !imagesIndisponibles.has(slide.course_id)
      ? urlImageSlide(slide.course_id, slide.image_rendu)
      : null;

  const contenuTexte = (
    <>
      <h2>{titre}</h2>
      <TexteSlide texte={slide.texte} surCitation={surCitation} />
      {slide.formules_latex.map((f, i) => (
        <p key={i} className="formule-slide">
          <Formule latex={f} />
        </p>
      ))}
      {slide.description_figures.map((d, i) => (
        <p key={i} className="figure-slide">
          <b>{t("figure")} :</b> {d}
        </p>
      ))}
    </>
  );

  return (
    <>
      <div className="titre-slide">
        <h1 dir="auto">{titre}</h1>
        <span className="meta">
          {t("slide")} <b>{slide.numero}</b> / {total}
        </span>
      </div>
      <div className="cadre-slide" ref={cadre}>
        {image ? (
          <section key={`${slide.numero}-image`} className="slide slide-image" aria-live="polite" aria-label={`${t("slide")} ${slide.numero} : ${titre}`}>
            <img
              src={image}
              alt={t("image-slide", { n: slide.numero })}
              decoding="async"
              onError={() => {
                imagesIndisponibles.add(slide.course_id);
                setImageEchouee(true);
              }}
            />
            {/* Le texte reste lisible par les lecteurs d'écran et la recherche dans la page. */}
            <div className="sr-only" dir="auto">
              {contenuTexte}
            </div>
          </section>
        ) : (
          <section key={slide.numero} className="slide" dir="auto" aria-live="polite" aria-label={`${t("slide")} ${slide.numero} : ${titre}`}>
            {contenuTexte}
          </section>
        )}
      </div>
    </>
  );
}

/** Texte d'une slide : une ligne par paragraphe, les lignes à puce regroupées en liste. */
function TexteSlide({ texte, surCitation }: { texte: string; surCitation: (n: number) => void }) {
  const groupes: { puces: boolean; lignes: string[] }[] = [];
  for (const ligne of texte.split("\n").map((l) => l.trim()).filter(Boolean)) {
    const puce = /^[-•*▪◦]\s+/.test(ligne);
    const propre = ligne.replace(/^[-•*▪◦]\s+/, "");
    const dernier = groupes.at(-1);
    if (puce && dernier?.puces) dernier.lignes.push(propre);
    else groupes.push({ puces: puce, lignes: [propre] });
  }
  return (
    <>
      {groupes.map((g, i) =>
        g.puces ? (
          <ul key={i}>
            {g.lignes.map((l, j) => (
              <li key={j}>
                <TexteEnLigne texte={l} surCitation={surCitation} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <TexteEnLigne texte={g.lignes[0]} surCitation={surCitation} />
          </p>
        ),
      )}
    </>
  );
}

function Navigation({
  numero,
  total,
  aller,
  maitrise,
}: {
  numero: number;
  total: number;
  aller: (n: number) => void;
  maitrise: Maitrise;
}) {
  const { t } = useLangue();
  const bande = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const b = bande.current;
    const v = b?.children[numero - 1] as HTMLElement | undefined;
    if (b && v) b.scrollLeft = v.offsetLeft - b.offsetLeft - (b.clientWidth - v.offsetWidth) / 2;
  }, [numero]);
  return (
    <>
      <div className="navigation">
        <button type="button" className="bouton" disabled={numero === 1} onClick={() => aller(numero - 1)}>
          <Icone nom="gauche" miroir />
          <span>{t("prec")}</span>
        </button>
        <div className="position">
          <b>{numero}</b> / {total}
        </div>
        <button type="button" className="bouton" disabled={numero === total} onClick={() => aller(numero + 1)}>
          <span>{t("suiv")}</span>
          <Icone nom="droite" miroir />
        </button>
      </div>
      <div className="bande" ref={bande} aria-label={t("slide")}>
        {Array.from({ length: total }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            className="vignette"
            data-etat={maitrise[n] ?? ""}
            aria-current={n === numero}
            aria-label={`${t("slide")} ${n}`}
            onClick={() => aller(n)}
          >
            <span>{n}</span>
            <span className="point" />
          </button>
        ))}
      </div>
      <div className="legende" aria-hidden="true">
        <span>
          <i style={{ width: 7, height: 7, background: "var(--bleu-clair)" }} />
          {t("vue")}
        </span>
        <span>
          <i style={{ width: 9, height: 9, background: "var(--bleu)" }} />
          {t("comprise")}
        </span>
        <span>
          <i style={{ width: 11, height: 11, background: "var(--vert)" }} />
          {t("testee")}
        </span>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- explication

type EtatGeneration =
  | { statut: "attente"; texte: string }
  | { statut: "ecriture"; texte: string }
  | { statut: "pret"; texte: string; reponse: AgentResponse }
  | { statut: "erreur"; texte: string; erreur: string };

const RETENIR = /^\s*(?:À retenir|A retenir|Key takeaway|To remember|للتذكّر|للتذكر)\s*[:：]\s*/i;

/** Structurer le texte libre de l'Explainer : idée clé, détail, « à retenir ». */
function structurer(texte: string) {
  const paragraphes = texte.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const retenir = paragraphes.find((p) => RETENIR.test(p));
  const reste = paragraphes.filter((p) => p !== retenir);
  const premier = reste.shift() ?? "";
  // Première phrase (hors formules $…$) = idée clé ; la suite = « En détail ».
  let dansFormule = false;
  let coupe = -1;
  for (let i = 0; i < premier.length; i++) {
    if (premier[i] === "$") dansFormule = !dansFormule;
    if (!dansFormule && /[.!?؟]/.test(premier[i]) && /\s/.test(premier[i + 1] ?? "")) {
      coupe = i + 1;
      break;
    }
  }
  const idee = coupe > 0 ? premier.slice(0, coupe) : premier;
  const suite = coupe > 0 ? premier.slice(coupe).trim() : "";
  return {
    idee,
    detail: [suite, ...reste].filter(Boolean).join("\n\n"),
    retenir: retenir?.replace(RETENIR, "") ?? null,
  };
}

function Explication({
  cours,
  slide,
  niveau,
  surNiveau,
  surCitation,
  surComprise,
  surTester,
}: {
  cours: Course;
  slide: Slide;
  niveau: Niveau;
  surNiveau: (n: Niveau) => void;
  surCitation: (n: number) => void;
  surComprise: () => void;
  surTester: () => void;
}) {
  const { t, rtl } = useLangue();
  const cache = useRef(new Map<string, AgentResponse>());
  const annulation = useRef<AbortController | null>(null);
  const [etat, setEtat] = useState<EtatGeneration>({ statut: "attente", texte: "" });
  const [essai, setEssai] = useState(0);
  const [trace, setTrace] = useState(false);
  const [ressourcesOuvertes, setRessourcesOuvertes] = useState(false);
  const cle = `${cours.id}|${slide.numero}|${niveau}`;

  useEffect(() => {
    const enCache = cache.current.get(cle);
    if (enCache) {
      setEtat({ statut: "pret", texte: enCache.reponse, reponse: enCache });
      setTrace(false);
      return;
    }
    const ctrl = new AbortController();
    annulation.current = ctrl;
    setEtat((e) => ({ statut: "attente", texte: e.texte }));
    // Petit délai : une navigation rapide entre slides ne lance pas une génération par slide.
    const minuteur = setTimeout(async () => {
      try {
        const res = await api.expliquer(cours.id, slide.numero, niveau, ctrl.signal);
        const reponse = await lireReponseAgent(res, (texte) => setEtat({ statut: "ecriture", texte }), ctrl.signal);
        cache.current.set(cle, reponse);
        setEtat({ statut: "pret", texte: reponse.reponse, reponse });
        setTrace(true);
        surComprise();
      } catch (e) {
        if (estAnnulation(e)) return;
        setEtat({ statut: "erreur", texte: "", erreur: e instanceof ErreurApi ? e.message : String(e) });
      }
    }, 300);
    return () => {
      clearTimeout(minuteur);
      ctrl.abort();
    };
  }, [cle, essai]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => setRessourcesOuvertes(false), [slide.numero]);

  const annuler = () => {
    annulation.current?.abort();
    setEtat({ statut: "erreur", texte: "", erreur: t("annuler") });
  };

  const occupe = etat.statut === "attente" || etat.statut === "ecriture";
  const { idee, detail, retenir } = structurer(etat.texte);
  const formule = slide.formules_latex[0];
  const precedente = slide.numero > 1 ? cours.slides[slide.numero - 2] : null;
  const fidelite = etat.statut === "pret" ? etat.reponse.score_fidelite : null;
  const curseur = NIVEAUX.indexOf(niveau) * 100 * (rtl ? -1 : 1);
  const ecriture = etat.statut === "ecriture" ? " curseur-ecriture" : "";

  return (
    <section className="panneau explication" aria-labelledby="titre-explication" aria-busy={occupe}>
      <div className="tete-panneau">
        <Mascotte etat={occupe ? "reflechit" : etat.statut === "erreur" ? "oups" : ""} />
        <div>
          <h2 id="titre-explication">{t("expl")}</h2>
          <div className="sous">
            <span className="agent">
              <span className="disque">
                <Icone nom="livre" />
              </span>
              Explainer
            </span>
            {fidelite !== null && (
              <span className="verifie">
                <Icone nom="bouclier" />
                <span>
                  {t("verifie")} · {Math.round(fidelite * 100)} %
                </span>
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="niveaux" role="group" aria-label="Niveau">
        <span className="curseur" style={{ transform: `translateX(${curseur}%)` }} />
        {NIVEAUX.map((n) => (
          <button key={n} type="button" aria-pressed={n === niveau} onClick={() => surNiveau(n)}>
            {t(n)}
          </button>
        ))}
      </div>

      {etat.statut === "attente" && <Attente surAnnuler={annuler} />}
      {etat.statut === "erreur" && <Erreur message={etat.erreur} surReessayer={() => setEssai((x) => x + 1)} />}

      {etat.texte && (
        <div className={etat.statut === "attente" ? "contenu genere" : "contenu"} aria-live="polite">
          <p className={`idee${!detail ? ecriture : ""}`} dir="auto">
            <TexteEnLigne texte={idee} surCitation={surCitation} />
          </p>
          {formule && (
            <div>
              <span className={trace ? "formule trace" : "formule"}>
                <Formule latex={formule} />
                <svg viewBox="0 0 200 10" preserveAspectRatio="none" aria-hidden="true">
                  <path d="M3 6 C 50 2, 110 9, 197 4" />
                </svg>
              </span>
            </div>
          )}
          {detail && (
            <div className={`bloc${ecriture}`}>
              <h3>{t("h-expl")}</h3>
              <TexteRiche texte={detail} surCitation={surCitation} />
            </div>
          )}
          {precedente && etat.statut === "pret" && (
            <div className="bloc">
              <h3>{t("h-lien")}</h3>
              <p>
                {t("lien-prec", { titre: precedente.titre || `${t("slide")} ${precedente.numero}` })}{" "}
                <Citation numero={precedente.numero} surCitation={surCitation} />
              </p>
            </div>
          )}
          {retenir && (
            <div className="encadre">
              <span className="disque">
                <Icone nom="etoile" />
              </span>
              <div>
                <h3>{t("h-retenir")}</h3>
                <p>
                  <TexteEnLigne texte={retenir} surCitation={surCitation} />
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="actions">
        <button type="button" className="bouton principal" onClick={surTester}>
          <Icone nom="quiz" />
          <span>{t("tester")}</span>
        </button>
        <button type="button" className="bouton" disabled title={t("ecouter-bientot")}>
          <Icone nom="son" />
          <span>{t("ecouter")}</span>
        </button>
        <button
          type="button"
          className="bouton discret"
          aria-expanded={ressourcesOuvertes}
          aria-controls="ressources"
          onClick={() => setRessourcesOuvertes((o) => !o)}
        >
          <Icone nom="monde" />
          <span>{t("ress")}</span>
        </button>
      </div>
      {ressourcesOuvertes && <Ressources cours={cours} numero={slide.numero} niveau={niveau} />}
    </section>
  );
}

// ---------------------------------------------------------------- ressources (A4)

function Ressources({ cours, numero, niveau }: { cours: Course; numero: number; niveau: Niveau }) {
  const { t, langue } = useLangue();
  const [liste, setListe] = useState<Ressource[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setListe(null);
    setErreur(null);
    api
      .ressources(cours.id, numero, niveau, langue, ctrl.signal)
      .then(setListe)
      .catch((e) => !estAnnulation(e) && setErreur(e instanceof ErreurApi ? e.message : String(e)));
    return () => ctrl.abort();
  }, [cours.id, numero, niveau, langue, essai]);

  return (
    <div className="ressources" id="ressources">
      <h3>{t("ress-titre")}</h3>
      {erreur && <Erreur message={erreur} surReessayer={() => setEssai((x) => x + 1)} />}
      {!liste && !erreur && <Attente libelle={t("ress")} />}
      {liste?.length === 0 && <p className="vide">{t("ress-vide")}</p>}
      {liste && liste.length > 0 && (
        <ul>
          {liste.map((r) => (
            <li key={r.url} className="ressource">
              <div className="ressource-tete">
                <span className="type-ressource" data-type={r.type}>
                  {t(`type-${r.type}` as CleTexte)}
                </span>
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="ressource-titre">
                  {r.titre}
                  <Icone nom="lien" />
                  <span className="sr-only">({t("ress-ouvrir")})</span>
                </a>
              </div>
              {r.justification && <p className="justification">{r.justification}</p>}
              {r.description && r.description !== r.justification && <p className="description">{r.description}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- questions (Q&A)

interface Tour {
  id: number;
  role: "etudiant" | "tuteur";
  texte: string;
  statut: "attente" | "ecriture" | "pret" | "erreur";
  sources?: Source[];
}

/** Historique envoyé à /ask : tours terminés (sans erreurs ni bulles vides), les plus récents. */
function historiqueDe(tours: Tour[]): Message[] {
  return tours
    .filter((x) => x.statut === "pret" && x.texte.trim())
    .map((x): Message => ({ role: x.role === "etudiant" ? "utilisateur" : "tuteur", contenu: x.texte }))
    .slice(-MAX_HISTORIQUE);
}

function Questions({
  cours,
  slide,
  niveau,
  surCitation,
}: {
  cours: Course;
  slide: Slide;
  niveau: Niveau;
  surCitation: (n: number) => void;
}) {
  const { t, langue } = useLangue();
  const [tours, setTours] = useState<Tour[]>([]);
  const [question, setQuestion] = useState("");
  const fil = useRef<HTMLDivElement>(null);
  const annulation = useRef<AbortController | null>(null);
  const prochainId = useRef(1);
  const occupe = tours.some((x) => x.statut === "attente" || x.statut === "ecriture");

  useEffect(() => {
    setTours([]);
    return () => annulation.current?.abort();
  }, [cours.id]);
  useLayoutEffect(() => {
    if (fil.current) fil.current.scrollTop = fil.current.scrollHeight;
  }, [tours]);

  const majTuteur = (id: number, maj: Partial<Tour>) =>
    setTours((ts) => ts.map((x) => (x.id === id ? { ...x, ...maj } : x)));

  async function envoyer(texte: string) {
    if (!texte.trim() || occupe) return;
    const historique = historiqueDe(tours);
    const idEtudiant = prochainId.current++;
    const id = prochainId.current++;
    setTours((ts) => [
      ...ts,
      { id: idEtudiant, role: "etudiant", texte, statut: "pret" },
      { id, role: "tuteur", texte: "", statut: "attente" },
    ]);
    setQuestion("");
    const ctrl = new AbortController();
    annulation.current = ctrl;
    try {
      const res = await api.demander(
        { course_id: cours.id, slide_courante: slide.numero, question: texte, niveau, langue, historique },
        ctrl.signal,
      );
      const r = await lireReponseAgent(res, (partiel) => majTuteur(id, { texte: partiel, statut: "ecriture" }), ctrl.signal);
      majTuteur(id, { texte: r.reponse, statut: "pret", sources: r.sources });
    } catch (e) {
      const message = estAnnulation(e) ? t("annuler") : e instanceof ErreurApi ? e.message : String(e);
      majTuteur(id, { texte: message, statut: "erreur" });
    }
  }

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    envoyer(question);
  };

  const suggestions = [
    ...slide.concepts.slice(0, 1).map((c) => t("sugg-concept", { c })),
    t("sugg-resume"),
    t("sugg-exemple"),
  ];

  return (
    <section className="panneau questions" aria-labelledby="titre-questions">
      <div className="tete-panneau">
        <span className="disque clair" style={{ width: 40, height: 40 }}>
          <Icone nom="bulle" />
        </span>
        <div>
          <h2 id="titre-questions">{t("questions")}</h2>
          <div className="sous">{t("sous-questions")}</div>
        </div>
      </div>
      {tours.length > 0 && (
        <div className="fil" ref={fil} aria-live="polite">
          {tours.map((x) =>
            x.role === "etudiant" ? (
              <div key={x.id} className="tour etudiant entre">
                <div className="bulle" dir="auto">{x.texte}</div>
              </div>
            ) : (
              <TourTuteur key={x.id} tour={x} surCitation={surCitation} surAnnuler={() => annulation.current?.abort()} />
            ),
          )}
        </div>
      )}
      <div className="suggestions">
        {suggestions.map((s) => (
          <button key={s} type="button" disabled={occupe} onClick={() => envoyer(s)}>
            {s}
          </button>
        ))}
      </div>
      <form className="saisie" id="formulaire" onSubmit={soumettre}>
        <input
          type="text"
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("ph")}
          aria-label={t("ph")}
          autoComplete="off"
        />
        <button className="bouton principal" type="submit" disabled={occupe || !question.trim()}>
          <Icone nom="envoyer" miroir />
          <span>{t("envoyer")}</span>
        </button>
      </form>
    </section>
  );
}

function TourTuteur({ tour, surCitation, surAnnuler }: { tour: Tour; surCitation: (n: number) => void; surAnnuler: () => void }) {
  const { t } = useLangue();
  // Une réponse sans source est un refus honnête (« ce n'est pas dans le cours »).
  const refus = tour.statut === "pret" && (tour.sources?.length ?? 0) === 0;
  const [etatMascotte, setEtatMascotte] = useState<EtatMascotte>("reflechit");
  useEffect(() => {
    if (tour.statut === "attente" || tour.statut === "ecriture") return setEtatMascotte("reflechit");
    if (refus || tour.statut === "erreur") {
      setEtatMascotte("oups");
      const id = setTimeout(() => setEtatMascotte(""), 1600);
      return () => clearTimeout(id);
    }
    setEtatMascotte("");
  }, [tour.statut, refus]);

  // Sources renvoyées par l'agent mais non citées dans le texte : ajoutées en fin de bulle.
  const citees = new Set([...tour.texte.matchAll(/\[Slides?\s*(\d+)/gi)].map((m) => Number(m[1])));
  const enPlus = [...new Set((tour.sources ?? []).map((s) => s.numero))].filter((n) => !citees.has(n));

  const classe = ["bulle", tour.statut === "ecriture" && "curseur-ecriture", (refus || tour.statut === "erreur") && "refus"]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="tour tuteur entre">
      <Mascotte etat={etatMascotte} taille={34} />
      <div className={classe} title={refus ? t("refus") : undefined} dir="auto">
        {tour.statut === "attente" ? (
          <Attente surAnnuler={surAnnuler} />
        ) : tour.statut === "ecriture" ? (
          tour.texte
        ) : (
          <>
            <TexteRiche texte={tour.texte} surCitation={surCitation} classeParagraphe="paragraphe-bulle" />
            {enPlus.map((n) => (
              <Citation key={n} numero={n} surCitation={surCitation} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function BarreMobile({ surTester }: { surTester: () => void }) {
  const { t } = useLangue();
  return (
    <nav className="barre-mobile" aria-label="Actions">
      <button type="button" className="bouton principal" onClick={surTester}>
        <Icone nom="quiz" />
        <span>{t("tester-court")}</span>
      </button>
      <button
        type="button"
        className="bouton"
        onClick={() => {
          const champ = document.getElementById("question") as HTMLInputElement | null;
          champ?.scrollIntoView({ behavior: "smooth", block: "center" });
          champ?.focus({ preventScroll: true });
        }}
      >
        <Icone nom="bulle" />
        <span>{t("demander")}</span>
      </button>
    </nav>
  );
}
