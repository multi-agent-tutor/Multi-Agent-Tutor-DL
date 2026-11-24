// Démos jouables de la landing (port de docs/maquettes/accueil/accueil.js) : fenêtre du tuteur, routeur
// d'agents, parcours en quatre étapes, QCM du jeu d'évaluation. Contenus figés (textes.ts), sans appel à l'API.
import { Fragment, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Mascotte, type EtatMascotte } from "../../components/Mascotte";
import { TexteEnLigne } from "../../components/TexteRiche";
import { useLangue } from "../../i18n";
import type { Niveau } from "../../types";
import { TEXTES_ACCUEIL, type NumeroDemo, type Route } from "./textes";

export const mouvementReduit = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const attendre = (ms: number) => new Promise((r) => setTimeout(r, mouvementReduit() ? 0 : ms));
const imageSuivante = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

/** Texte de démo : **gras** et formules $…$ (KaTeX). */
export function Riche({ texte }: { texte: string }) {
  return (
    <>
      {texte.split("**").map((morceau, i) =>
        i % 2 ? (
          <b key={i}>
            <TexteEnLigne texte={morceau} />
          </b>
        ) : (
          <TexteEnLigne key={i} texte={morceau} />
        ),
      )}
    </>
  );
}

export function Cites({ numeros, entre = false }: { numeros: number[]; entre?: boolean }) {
  return (
    <>
      {numeros.map((n) => (
        <span key={n} className={entre ? "v-cite v-entre" : "v-cite"}>
          Slide {n}
        </span>
      ))}
    </>
  );
}

/** Déclencher une fois quand l'élément arrive à l'écran. */
export function useUneFoisVisible<T extends Element>(seuil: number, rappel: () => void) {
  const ref = useRef<T>(null);
  const rappelRef = useRef(rappel);
  rappelRef.current = rappel;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entrees) => {
        if (entrees.some((e) => e.isIntersecting)) {
          obs.disconnect();
          rappelRef.current();
        }
      },
      { threshold: seuil },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [seuil]);
  return ref;
}

/** Mascotte qui revient au repos après `duree` ms. */
function useMascotte(): [EtatMascotte, (e: EtatMascotte, duree?: number) => void] {
  const [etat, setEtat] = useState<EtatMascotte>("");
  const minuteur = useRef(0);
  useEffect(() => () => clearTimeout(minuteur.current), []);
  const changer = (e: EtatMascotte, duree?: number) => {
    clearTimeout(minuteur.current);
    setEtat(e);
    if (duree) minuteur.current = window.setTimeout(() => setEtat(""), duree);
  };
  return [etat, changer];
}

// ------------------------------------------------------------------ sélecteur de niveau (curseur glissant)

function Niveaux({ niveau, surNiveau, idLibelle }: { niveau: Niveau; surNiveau: (n: Niveau) => void; idLibelle: string }) {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue];
  const groupe = useRef<HTMLDivElement>(null);
  const curseur = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const placer = () => {
      const actif = groupe.current?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]');
      if (!actif || !curseur.current) return;
      curseur.current.style.width = `${actif.offsetWidth}px`;
      curseur.current.style.transform = `translateX(${actif.offsetLeft}px)`;
    };
    placer();
    addEventListener("resize", placer);
    document.fonts?.ready.then(placer);
    return () => removeEventListener("resize", placer);
  }, [niveau, langue]);
  return (
    <div className="v-niveaux" role="group" aria-labelledby={idLibelle} ref={groupe}>
      <span className="v-curseur" aria-hidden="true" ref={curseur} />
      {(["debutant", "intermediaire", "avance"] as Niveau[]).map((n) => (
        <button key={n} type="button" aria-pressed={n === niveau} onClick={() => surNiveau(n)}>
          {T.niveaux[n]}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 1. fenêtre du tuteur

export function Tuteur({ surDemo }: { surDemo: (page: "cours" | "quiz") => void }) {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue];
  const [slide, setSlide] = useState<NumeroDemo>(7);
  const [niveau, setNiveau] = useState<Niveau>("intermediaire");
  const [texte, setTexte] = useState("");
  const [sources, setSources] = useState<number[]>([]);
  const [outil, setOutil] = useState(false);
  const [ecriture, setEcriture] = useState(false);
  const [mascotte, setMascotte] = useMascotte();
  const tour = useRef(0);
  const { question, reponses } = T.slides[slide];

  useEffect(() => {
    const moi = ++tour.current;
    const [phrase, numeros] = reponses[niveau];
    (async () => {
      setSources([]);
      setTexte("");
      setOutil(true);
      setMascotte("reflechit");
      await attendre(650);
      if (moi !== tour.current) return;
      setOutil(false);
      if (mouvementReduit()) setTexte(phrase);
      else {
        setEcriture(true);
        // Les formules $…$ sont des morceaux insécables : elles apparaissent entières.
        const morceaux = phrase.split(/(\$[^$]+\$|\s+)/).filter(Boolean);
        for (let i = 1; i <= morceaux.length; i++) {
          if (moi !== tour.current) return;
          if (/^\s+$/.test(morceaux[i - 1])) continue;
          setTexte(morceaux.slice(0, i).join(""));
          await attendre(28);
        }
      }
      if (moi !== tour.current) return;
      setEcriture(false);
      setSources(numeros);
      setMascotte("contente", 1400);
    })();
    return () => {
      tour.current++;
    };
  }, [slide, niveau, langue]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="v-tw">
      <div className="v-tw__bar">
        <span className="v-tw__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>
          <b>{T.essai.cours}</b> · {T.essai.chapitre}
        </span>
        <span className="v-sp" />
        <span>{T.essai.meta}</span>
      </div>
      <div className="v-tw__body">
        <div className="v-tw__slides" role="group" aria-label={T.essai.choisir}>
          <p>{T.essai.choisir}</p>
          {([5, 7, 23] as NumeroDemo[]).map((n) => (
            <button key={n} className="v-tw__slide" type="button" aria-pressed={n === slide} onClick={() => setSlide(n)}>
              <b>{n}</b>
              <span>{T.slides[n].titre}</span>
            </button>
          ))}
        </div>
        <div className="v-tw__chat">
          <div className="v-tw__outils">
            <span id="v-niveau-l">{T.essai.niveau}</span>
            <Niveaux niveau={niveau} surNiveau={setNiveau} idLibelle="v-niveau-l" />
          </div>
          <div className="v-msg v-msg--moi">{question}</div>
          <div className="v-outil" hidden={!outil}>
            {T.essai.recherche}
          </div>
          <div className="v-msg v-msg--tuteur" aria-live="polite">
            <Mascotte etat={mascotte} />
            <div>
              <span className={ecriture ? "v-ecrit v-en-cours" : "v-ecrit"}>
                <TexteEnLigne texte={texte} />
              </span>
              <span className="v-sources">
                <Cites numeros={sources} entre />
              </span>
            </div>
          </div>
          <div className="v-acts">
            <a
              href="#quiz"
              onClick={(e) => {
                e.preventDefault();
                surDemo("quiz");
              }}
            >
              {T.essai.tester}
            </a>
            <a className="v-acts__second" href="#depot">
              {T.essai.essayer}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 2. routeur d'agents

const AGENTS: Exclude<Route, "refus">[] = ["explainer", "qa", "quiz", "resources"];

function IconeLivre() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 7v14m-9-3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4a4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3a3 3 0 0 0-3-3z" />
    </svg>
  );
}
export function IconeBulleRonde() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092a10 10 0 1 0-4.777-4.719" />
    </svg>
  );
}
function IconeListe() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M13 5h8m-8 7h8m-8 7h8M3 17l2 2l4-4M3 7l2 2l4-4" />
    </svg>
  );
}
function IconeBulleCarree() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z" />
    </svg>
  );
}
function IconeLien() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
    </svg>
  );
}
export function IconeFichier() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
      <path d="M14 2v5a1 1 0 0 0 1 1h5m-8 4v6m3-3l-3-3l-3 3" />
    </svg>
  );
}
const ICONES: Record<Route, () => ReactNode> = {
  explainer: IconeLivre,
  qa: IconeBulleRonde,
  quiz: IconeListe,
  resources: IconeLien,
  refus: IconeBulleCarree,
};

export function Routeur() {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue].agents;
  const [route, setRoute] = useState<Route | null>(null);
  const [liens, setLiens] = useState([false, false, false]);
  const [routerActif, setRouterActif] = useState(false);
  const [agent, setAgent] = useState<Route | null>(null);
  const [critic, setCritic] = useState<"" | "actif" | "valide">("");
  const [sortie, setSortie] = useState(false);
  const [mascotte, setMascotte] = useMascotte();
  const tour = useRef(0);
  useEffect(
    () => () => {
      tour.current++;
    },
    [],
  );

  async function router(cle: Route) {
    const moi = ++tour.current;
    const encore = () => moi === tour.current;
    setRoute(cle);
    setRouterActif(false);
    setAgent(null);
    setCritic("");
    setSortie(false);
    setLiens([false, false, false]);
    setMascotte("");
    await imageSuivante(); // la classe v-passe est retirée avant d'être remise : l'impulsion rejoue
    const pulser = async (i: number) => {
      setLiens((l) => l.map((x, k) => (k === i ? true : x)));
      await attendre(380);
    };
    if (!encore()) return;
    await pulser(0);
    if (!encore()) return;
    setRouterActif(true);
    setMascotte("reflechit");
    await attendre(420);
    if (!encore()) return;
    setMascotte("");
    await pulser(1);
    if (!encore()) return;
    setAgent(cle === "refus" ? "qa" : cle);
    await attendre(360);
    if (!encore()) return;
    await pulser(2);
    if (!encore()) return;
    setCritic(T.routes[cle].valide ? "valide" : "actif");
    await attendre(320);
    if (!encore()) return;
    setSortie(true);
    setMascotte("contente", 1200);
  }

  const zone = useUneFoisVisible<HTMLDivElement>(0.4, () => router("explainer"));
  const r = route ? T.routes[route] : null;

  return (
    <div className="v-routeur" ref={zone}>
      <div className="v-demandes" role="group" aria-label={T.demandesAria}>
        <p>{T.demandesTitre}</p>
        {(Object.keys(T.demandes) as Route[]).map((cle) => {
          const Icone = ICONES[cle];
          return (
            <button key={cle} className="v-demande" type="button" aria-pressed={route === cle} onClick={() => router(cle)}>
              <Icone />
              {T.demandes[cle]}
            </button>
          );
        })}
      </div>
      <div className="v-flux" aria-live="polite">
        <div className={liens[0] ? "v-lien v-passe" : "v-lien"} aria-hidden="true">
          <i />
        </div>
        <div className={routerActif ? "v-noeud v-noeud--router v-actif" : "v-noeud v-noeud--router"}>
          <Mascotte etat={mascotte} />
          Router <small>{T.router}</small>
        </div>
        <div className={liens[1] ? "v-lien v-passe" : "v-lien"} aria-hidden="true">
          <i />
        </div>
        <div className={agent ? "v-agents4 v-choisi" : "v-agents4"}>
          {AGENTS.map((a) => {
            const Icone = ICONES[a];
            return (
              <div key={a} className={agent === a ? "v-noeud v-actif" : "v-noeud"}>
                <Icone />
                {a === "qa" ? "Q&A" : a[0].toUpperCase() + a.slice(1)}
                <small>{T.sous[a]}</small>
              </div>
            );
          })}
        </div>
        <div className={liens[2] ? "v-lien v-passe" : "v-lien"} aria-hidden="true">
          <i />
        </div>
        <div className={["v-critic", critic && "v-actif", critic === "valide" && "v-valide"].filter(Boolean).join(" ")}>
          {critic && r ? (
            <>
              <svg className="v-ok" viewBox="0 0 20 20" aria-hidden="true">
                <path d="M4.5 10.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>
                <Riche texte={r.critic} />
              </span>
            </>
          ) : (
            <span>
              <Riche texte={T.criticRepos} />
            </span>
          )}
        </div>
        <div className={sortie ? "v-sortie" : "v-sortie v-cache"}>
          {sortie && r && (
            <>
              <small>{r.titre}</small>
              <Riche texte={r.texte} />
              <Cites numeros={r.sources} entre />
            </>
          )}
        </div>
        <p className="v-local">{T.local}</p>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 3. parcours en quatre étapes

const VUES = ["v-depot", "v-expl", "v-qa", "v-quiz"];

export function Parcours() {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue].parcours;
  const [actif, setActif] = useState(0);
  const [vu, setVu] = useState(false);
  const [retournee, setRetournee] = useState(false);
  const onglets = useRef<(HTMLButtonElement | null)[]>([]);
  const liste = useUneFoisVisible<HTMLDivElement>(0.35, () => setVu(true));

  const choisir = (i: number, focus = false) => {
    setActif(i);
    if (focus) onglets.current[i]?.focus();
  };
  const touche = (e: KeyboardEvent, i: number) => {
    const pas = ({ ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 } as Record<string, number>)[e.key];
    const n = T.etapes.length;
    if (pas) {
      e.preventDefault();
      choisir((i + pas + n) % n, true);
    }
    if (e.key === "Home") {
      e.preventDefault();
      choisir(0, true);
    }
    if (e.key === "End") {
      e.preventDefault();
      choisir(n - 1, true);
    }
  };

  const vue = (i: number, contenu: ReactNode) => (
    <div
      key={`${i}-${vu}`}
      className={vu && actif === i ? "v-scene__vue v-entre" : "v-scene__vue"}
      id={VUES[i]}
      role="tabpanel"
      aria-labelledby={`t-${VUES[i]}`}
      hidden={actif !== i}
    >
      {contenu}
    </div>
  );

  return (
    <div className="v-parcours">
      <div className="v-etapes" role="tablist" aria-label={T.aria} aria-orientation="vertical" ref={liste}>
        {T.etapes.map(([titre, detail], i) => (
          <button
            key={i}
            ref={(b) => {
              onglets.current[i] = b;
            }}
            className="v-etape v-projecteur"
            type="button"
            role="tab"
            id={`t-${VUES[i]}`}
            aria-controls={VUES[i]}
            aria-selected={actif === i}
            tabIndex={actif === i ? 0 : -1}
            onClick={() => choisir(i)}
            onKeyDown={(e) => touche(e, i)}
          >
            <span className="v-spot" aria-hidden="true" />
            <span className="v-num">{i + 1}</span>
            <span>
              <strong className="v-t">{titre}</strong>
              <span className="v-d">{detail}</span>
            </span>
          </button>
        ))}
      </div>
      <div className="v-scene">
        {vue(
          0,
          <>
            <div className="v-fichier">
              <IconeFichier />
              <span>
                {T.fichier}
                <small>{T.fichierMeta}</small>
              </span>
            </div>
            <div className="v-barre" aria-hidden="true">
              <i />
            </div>
            <div className="v-lu">
              {T.lu.map(([n, l]) => (
                <div key={l}>
                  <b>{n}</b>
                  {l}
                </div>
              ))}
            </div>
            <div className="v-agents-cites">
              <span>Ingestion</span>
              <span>OCR</span>
              <span>VLM</span>
            </div>
          </>,
        )}
        {vue(
          1,
          <>
            <dl className="v-rubriques">
              {T.rubriques.map((r) => (
                <div key={r.dt} className="v-rubrique">
                  <dt>{r.dt}</dt>
                  <dd>
                    {r.retenir ? (
                      <span className="v-retenir">
                        <Riche texte={r.dd} />
                      </span>
                    ) : (
                      <Riche texte={r.dd} />
                    )}
                    {r.source && <Cites numeros={[r.source]} />}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="v-agents-cites">
              <span>Explainer</span>
              <span>Critic</span>
            </div>
          </>,
        )}
        {vue(
          2,
          <>
            <div className="v-msg v-msg--moi">{T.qa.q1}</div>
            <div className="v-msg v-msg--tuteur">
              <Mascotte />
              <div>
                <Riche texte={T.qa.r1} />
                <Cites numeros={T.qa.s1} />
              </div>
            </div>
            <div className="v-msg v-msg--moi">{T.qa.q2}</div>
            <div className="v-refus">
              <IconeBulleRonde />
              {T.qa.refus}
            </div>
            <div className="v-agents-cites">
              <span>Q&amp;A</span>
              <span>Critic</span>
            </div>
          </>,
        )}
        {vue(
          3,
          <>
            <button className="v-flashcard" type="button" aria-pressed={retournee} aria-label={T.carte.aria} onClick={() => setRetournee((x) => !x)}>
              <span className="v-flashcard__in">
                <span className="v-flashcard__face v-flashcard__face--recto">
                  <small>{T.carte.recto}</small>
                  <Riche texte={T.carte.rectoTexte} />
                </span>
                <span className="v-flashcard__face v-flashcard__face--dos">
                  <small>{T.carte.verso}</small>
                  <Riche texte={T.carte.versoTexte} />
                </span>
              </span>
            </button>
            <p className="v-indice">{T.carte.indice}</p>
            <div className="v-agents-cites">
              <span>Quiz</span>
              <span>Resources</span>
            </div>
          </>,
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 4. QCM du jeu d'évaluation

const JUSTE = 1;

export function QcmPreuve() {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue].preuves;
  const [choisi, setChoisi] = useState<number | null>(null);
  const [mascotte, setMascotte] = useMascotte();
  const rejouer = useRef<HTMLButtonElement>(null);
  const premier = useRef<HTMLButtonElement>(null);
  const [corpusVu, setCorpusVu] = useState(false);
  const corpus = useUneFoisVisible<HTMLDivElement>(0.5, () => setCorpusVu(true));
  const repondu = choisi !== null;
  const juste = choisi === JUSTE;

  useEffect(() => {
    if (repondu) rejouer.current?.focus({ preventScroll: true });
  }, [repondu]);

  return (
    <div className="v-preuves">
      <article className="v-carte v-qcm v-projecteur">
        <span className="v-spot" aria-hidden="true" />
        <h3>{T.qcmTitre}</h3>
        <p className="v-q" id="v-qcm-q">
          {T.question}
        </p>
        <div className="v-qcm__choix" role="group" aria-labelledby="v-qcm-q">
          {T.choix.map((texte, i) => {
            const classe = repondu && i === JUSTE ? "v-choix v-juste" : repondu && i === choisi ? "v-choix v-faux" : "v-choix";
            return (
              <button
                key={i}
                ref={i === 0 ? premier : undefined}
                className={classe}
                type="button"
                disabled={repondu}
                onClick={() => {
                  setChoisi(i);
                  setMascotte(i === JUSTE ? "contente" : "oups", i === JUSTE ? 1600 : 0);
                }}
              >
                <span className="v-lettre">{"ABCD"[i]}</span>
                {texte}
                <svg className="v-verdict v-verdict--non" viewBox="0 0 20 20" role="img" aria-label={T.verdictFaux}>
                  <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" />
                </svg>
                <svg className="v-verdict v-verdict--ok" viewBox="0 0 20 20" role="img" aria-label={T.verdictJuste}>
                  <path d="M4.5 10.5l3.5 3.5 7.5-8" />
                </svg>
              </button>
            );
          })}
        </div>
        <div className="v-retour" role="status" hidden={!repondu}>
          <Mascotte etat={mascotte} />
          <p>
            {repondu && (
              <Fragment>
                {juste ? T.juste : T.faux}
                <Cites numeros={[7, 23]} />
              </Fragment>
            )}
          </p>
        </div>
        <button
          ref={rejouer}
          className="v-rejouer"
          type="button"
          hidden={!repondu}
          onClick={() => {
            setChoisi(null);
            setMascotte("");
            requestAnimationFrame(() => premier.current?.focus());
          }}
        >
          {T.reessayer}
        </button>
      </article>
      <article className="v-carte v-projecteur">
        <span className="v-spot" aria-hidden="true" />
        <h3>{T.corpusTitre}</h3>
        <div className={corpusVu ? "v-corpus" : "v-corpus v-attend"} ref={corpus}>
          {T.corpus.map(([domaine, n, part]) => (
            <div key={domaine} className="v-corpus__ligne" style={{ ["--part" as string]: part }}>
              <div>
                <span>{domaine}</span>
                <b>{n}</b>
              </div>
              <div className="v-corpus__barre" aria-hidden="true">
                <i />
              </div>
            </div>
          ))}
          <p className="v-corpus__note">{T.note}</p>
        </div>
      </article>
    </div>
  );
}
