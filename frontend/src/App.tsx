// Application : Accueil (landing) → Dépôt → Cours → Quiz / Flashcards, routage par le hash de l'URL.
// #accueil (ou vide, ou une ancre de la landing comme #essai) · #depot · #cours · #quiz · #flashcards
import { useEffect, useRef, useState } from "react";
import { api, ErreurApi, utilisateur } from "./api";
import { Attente, Erreur } from "./components/Attente";
import { Barre, type Page, type PageOutil } from "./components/Barre";
import { Icone, SpriteIcones } from "./components/Icones";
import { Mascotte } from "./components/Mascotte";
import { useLangue } from "./i18n";
import { useMaitrise } from "./maitrise";
import { PageAccueil } from "./pages/accueil/Accueil";
import { PageCours } from "./pages/Cours";
import { PageDepot } from "./pages/Depot";
import { PageQuiz, type ModeQuiz } from "./pages/Quiz";
import { ajouterRecent } from "./recents";
import type { Course, Niveau } from "./types";

const COURS_PAR_DEFAUT = import.meta.env.VITE_COURS_PAR_DEFAUT || "ml_regression_lineaire_fr";

function routeDuHash(): { page: Page; flashcards: boolean } {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h === "depot" || h === "cours" || h === "quiz") return { page: h, flashcards: false };
  if (h === "flashcards") return { page: "quiz", flashcards: true };
  return { page: "accueil", flashcards: false }; // vide, #accueil, ou une ancre de la landing
}

const messageErreur = (e: unknown) => (e instanceof ErreurApi ? e.message : String(e));

export default function App() {
  const { t } = useLangue();
  const [cours, setCours] = useState<Course | null>(null);
  const [chargement, setChargement] = useState(true);
  const [page, setPage] = useState<Page>(() => routeDuHash().page);
  const [numero, setNumero] = useState(1);
  const [niveau, setNiveau] = useState<Niveau>(() => (localStorage.getItem("mat-niveau") as Niveau) || "intermediaire");
  const [portee, setPortee] = useState<number | null>(null);
  const [modeQuiz, setModeQuiz] = useState<ModeQuiz>(() => (routeDuHash().flashcards ? "flashcards" : "qcm"));
  const [erreur, setErreur] = useState<string | null>(null);
  const { maitrise, marquer } = useMaitrise(cours?.id ?? null);
  const user = utilisateur();
  const pageRef = useRef(page);
  pageRef.current = page;

  // Cours ouvert au démarrage : le dernier ouvert, sinon celui de VITE_COURS_PAR_DEFAUT.
  useEffect(() => {
    const id = localStorage.getItem("mat-cours") || COURS_PAR_DEFAUT;
    api
      .cours(id)
      .then(ouvrir)
      .catch((e) => {
        if (!(e instanceof ErreurApi && e.statut === 404)) setErreur(messageErreur(e));
        localStorage.removeItem("mat-cours");
      })
      .finally(() => setChargement(false));
  }, []);

  // Précédent / suivant du navigateur, liens #depot, #cours… de la landing.
  useEffect(() => {
    const surHash = () => {
      const r = routeDuHash();
      if (pageRef.current !== r.page) scrollTo({ top: 0 }); // une ancre de la landing garde son défilement
      setPage(r.page);
      if (r.page === "quiz") setModeQuiz(r.flashcards ? "flashcards" : "qcm");
    };
    addEventListener("hashchange", surHash);
    return () => removeEventListener("hashchange", surHash);
  }, []);

  function ouvrir(c: Course) {
    setCours(c);
    setErreur(null);
    localStorage.setItem("mat-cours", c.id);
    ajouterRecent(c);
    const n = Number(localStorage.getItem(`mat-slide-${c.id}`)) || 1;
    setNumero(Math.min(Math.max(1, n), c.nombre_slides));
    setPortee(null);
  }

  /** Changer de page : une entrée d'historique par page (le bouton Précédent du navigateur fonctionne). */
  function allerPage(p: Page, mode: ModeQuiz = "qcm") {
    if (p === "quiz") setModeQuiz(mode);
    const hash = p === "quiz" && mode === "flashcards" ? "#flashcards" : `#${p}`;
    if (location.hash !== hash) history.pushState(null, "", hash);
    if (p !== page) scrollTo({ top: 0 });
    setPage(p);
  }

  /** Ouvrir le cours d'exemple de l'API (boutons « Essayer la démo » de la landing). */
  async function ouvrirDemo(p: "cours" | "quiz") {
    if (cours?.id !== COURS_PAR_DEFAUT) {
      try {
        ouvrir(await api.cours(COURS_PAR_DEFAUT));
      } catch (e) {
        setErreur(messageErreur(e));
      }
    }
    if (p === "quiz") setPortee(null);
    allerPage(p);
  }

  const changerNumero = (n: number) => {
    setNumero(n);
    if (cours) localStorage.setItem(`mat-slide-${cours.id}`, String(n));
  };
  const changerNiveau = (n: Niveau) => {
    setNiveau(n);
    localStorage.setItem("mat-niveau", n);
  };
  const allerSlide = (n: number) => {
    changerNumero(n);
    allerPage("cours");
  };

  if (page === "accueil")
    return (
      <>
        <SpriteIcones />
        <PageAccueil surDemo={ouvrirDemo} />
      </>
    );

  const sansCours = (
    <main className="sans-cours">
      <Mascotte etat={erreur ? "oups" : ""} />
      <h1>{t("sans-cours-titre")}</h1>
      <p>{t("sans-cours-texte")}</p>
      <div className="actions">
        <a className="bouton principal" href="#depot">
          <Icone nom="depot" />
          <span>{t("depot")}</span>
        </a>
        <button type="button" className="bouton" onClick={() => ouvrirDemo(page === "quiz" ? "quiz" : "cours")}>
          <Icone nom="livre" />
          <span>{t("cours-exemple")}</span>
        </button>
      </div>
    </main>
  );

  let contenu;
  if (page === "depot")
    contenu = (
      <PageDepot
        niveau={niveau}
        surNiveau={changerNiveau}
        surCours={ouvrir}
        surPage={(p) => {
          if (p === "quiz") setPortee(null);
          allerPage(p);
        }}
      />
    );
  else if (chargement)
    contenu = (
      <main className="sans-cours">
        <Attente />
      </main>
    );
  else if (!cours) contenu = sansCours;
  else if (page === "cours")
    contenu = (
      <PageCours
        cours={cours}
        numero={numero}
        surNumero={changerNumero}
        niveau={niveau}
        surNiveau={changerNiveau}
        maitrise={maitrise}
        surMaitrise={marquer}
        surTester={(n) => {
          setPortee(n);
          allerPage("quiz");
        }}
      />
    );
  else
    contenu = (
      <PageQuiz
        cours={cours}
        portee={portee}
        surPortee={setPortee}
        mode={modeQuiz}
        surMode={(m) => {
          setModeQuiz(m);
          history.replaceState(null, "", m === "flashcards" ? "#flashcards" : "#quiz");
        }}
        user={user}
        surAllerSlide={allerSlide}
        surTestee={(n) => marquer(n, "testee")}
      />
    );

  return (
    <>
      <SpriteIcones />
      <Barre
        cours={cours}
        page={page as PageOutil}
        surPage={(p) => {
          if (p === "quiz") setPortee(null);
          allerPage(p);
        }}
      />
      {erreur && (
        <div className="bandeau-erreur">
          <Erreur message={erreur} />
          <button type="button" className="bouton discret" onClick={() => setErreur(null)} aria-label={t("annuler")}>
            ×
          </button>
        </div>
      )}
      {contenu}
    </>
  );
}
