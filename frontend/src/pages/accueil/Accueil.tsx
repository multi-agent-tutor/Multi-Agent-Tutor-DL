// Page Accueil (landing, registre « vitrine » de DESIGN.md) : port React de docs/maquettes/accueil/.
// Styles : styles/accueil.css (classes v-*). Mouvement : transform et opacity seulement, tout reste à sa
// place finale sous prefers-reduced-motion (le dégradé WebGL devient une image fixe).
import { useEffect, useRef, useState, type ElementType, type ReactNode } from "react";
import { SelecteurLangue } from "../../components/Barre";
import { useLangue } from "../../i18n";
import { monterDegrade } from "./degrade";
import { mouvementReduit, Parcours, QcmPreuve, Riche, Routeur, Tuteur } from "./Demos";
import { TEXTES_ACCUEIL } from "./textes";

interface Props {
  /** Ouvrir le cours d'exemple, puis la page Cours ou Quiz. */
  surDemo: (page: "cours" | "quiz") => void;
}

const SECTIONS = ["essai", "agents", "parcours", "preuves"] as const;

function Degrade({ clair = 0, doux = false }: { clair?: number; doux?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => (ref.current ? monterDegrade(ref.current, clair) : undefined), [clair]);
  return <canvas ref={ref} className={doux ? "v-degrade v-degrade--doux" : "v-degrade"} aria-hidden="true" />;
}

/** Apparition au défilement, une seule fois ; un saut de défilement par-dessus l'élément le révèle aussi. */
function Revele({ as: Balise = "div", className = "", children, ...reste }: { as?: ElementType; className?: string; children: ReactNode; id?: string }) {
  const ref = useRef<HTMLElement>(null);
  const [vu, setVu] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || vu) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) setVu(true);
      },
      { threshold: 0.2, rootMargin: "0px 0px -8% 0px" },
    );
    const auDefilement = () => {
      if (el.getBoundingClientRect().bottom < 0) setVu(true);
    };
    obs.observe(el);
    addEventListener("scroll", auDefilement, { passive: true });
    return () => {
      obs.disconnect();
      removeEventListener("scroll", auDefilement);
    };
  }, [vu]);
  return (
    <Balise ref={ref} className={`${className} v-revele${vu ? " v-vu" : ""}`} {...reste}>
      {children}
    </Balise>
  );
}

/** Compteur qui monte jusqu'à sa valeur à l'arrivée à l'écran (1,4 s, ease-out quartique). */
function Compteur({ cible }: { cible: number }) {
  const ref = useRef<HTMLElement>(null);
  const [valeur, setValeur] = useState(cible);
  useEffect(() => {
    const el = ref.current;
    if (!el || cible === 0 || mouvementReduit()) return;
    let image = 0;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        obs.disconnect();
        const debut = performance.now();
        const pas = (maintenant: number) => {
          const x = Math.min(1, (maintenant - debut) / 1400);
          setValeur(Math.round(cible * (1 - Math.pow(1 - x, 4))));
          if (x < 1) image = requestAnimationFrame(pas);
        };
        setValeur(0);
        image = requestAnimationFrame(pas);
      },
      { threshold: 0.6 },
    );
    obs.observe(el);
    return () => {
      obs.disconnect();
      cancelAnimationFrame(image);
    };
  }, [cible]);
  return <b ref={ref}>{valeur}</b>;
}

function Surligne({ texte, fin = false }: { texte: string; fin?: boolean }) {
  return (
    <span className={fin ? "v-surligne v-surligne--fin" : "v-surligne"}>
      {texte}
      <svg viewBox="0 0 300 24" preserveAspectRatio="none" aria-hidden="true">
        <path d="M4 16 C 70 8, 150 20, 296 9" />
      </svg>
    </span>
  );
}

function IconeDepot() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 11V3M4.5 6.5 8 3l3.5 3.5M3 10.5v1.5a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1.5" />
    </svg>
  );
}

function Logo({ aria }: { aria: string }) {
  return (
    <a className="v-nav__logo" href="#haut" aria-label={aria}>
      <img src="/img/logo-icone.png" alt="" width={34} height={34} />
      <span>Multi-Agent Tutor</span>
    </a>
  );
}

export function PageAccueil({ surDemo }: Props) {
  const { langue } = useLangue();
  const T = TEXTES_ACCUEIL[langue];
  const racine = useRef<HTMLDivElement>(null);
  const [entree, setEntree] = useState(false);
  const [navCachee, setNavCachee] = useState(false);
  const [barreVisible, setBarreVisible] = useState(false);
  const [ici, setIci] = useState<string | null>(null);

  const demo = (page: "cours" | "quiz") => (e: { preventDefault: () => void }) => {
    e.preventDefault();
    surDemo(page);
  };

  // Page « vitrine » : défilement doux et titre propres à la landing.
  useEffect(() => {
    document.documentElement.classList.add("v-page");
    return () => document.documentElement.classList.remove("v-page");
  }, []);
  useEffect(() => {
    const avant = document.title;
    document.title = T.titrePage;
    return () => {
      document.title = avant;
    };
  }, [T.titrePage]);

  // Entrée du hero : une fois, dès que la première image est prête.
  useEffect(() => {
    let a = 0;
    let b = 0;
    a = requestAnimationFrame(() => (b = requestAnimationFrame(() => setEntree(true))));
    return () => {
      cancelAnimationFrame(a);
      cancelAnimationFrame(b);
    };
  }, []);

  // Navigation qui se cache en descendant, barre d'action mobile, section courante.
  useEffect(() => {
    let dernierY = scrollY;
    let ticket = 0;
    const auDefilement = () => {
      if (ticket) return;
      ticket = requestAnimationFrame(() => {
        ticket = 0;
        const y = scrollY;
        if (y > 240 && y > dernierY + 4) setNavCachee(true);
        if (y < dernierY - 4 || y < 240) setNavCachee(false);
        dernierY = y;
        setBarreVisible(y > innerHeight * 0.7);
      });
    };
    addEventListener("scroll", auDefilement, { passive: true });
    const obs = new IntersectionObserver(
      (entrees) => entrees.forEach((e) => e.isIntersecting && setIci(e.target.id)),
      { rootMargin: "-45% 0px -50% 0px" },
    );
    SECTIONS.forEach((id) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    });
    return () => {
      removeEventListener("scroll", auDefilement);
      cancelAnimationFrame(ticket);
      obs.disconnect();
    };
  }, []);

  // Pointeur fin seulement : boutons aimantés, parallaxe du hero, tache de lumière dans les cartes.
  useEffect(() => {
    const r = racine.current;
    if (!r || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const nettoyages: (() => void)[] = [];
    const ecouter = (el: Element, type: string, f: (e: PointerEvent) => void) => {
      el.addEventListener(type, f as EventListener);
      nettoyages.push(() => el.removeEventListener(type, f as EventListener));
    };
    if (!mouvementReduit()) {
      r.querySelectorAll<HTMLElement>(".v-aimant").forEach((b) => {
        ecouter(b, "pointermove", (e) => {
          const box = b.getBoundingClientRect();
          b.style.transform = `translate(${(e.clientX - box.left - box.width / 2) * 0.22}px, ${(e.clientY - box.top - box.height / 2) * 0.3}px)`;
        });
        ecouter(b, "pointerleave", () => (b.style.transform = ""));
      });
      const hero = r.querySelector<HTMLElement>(".v-hero");
      if (hero) {
        const couches = [...hero.querySelectorAll<HTMLElement>("[data-parallaxe]")].map((el) => ({ el, k: Number(el.dataset.parallaxe || 1) }));
        let image = 0;
        ecouter(hero, "pointermove", (e) => {
          if (image) return;
          image = requestAnimationFrame(() => {
            image = 0;
            const box = hero.getBoundingClientRect();
            const dx = (e.clientX - box.left) / box.width - 0.5;
            const dy = (e.clientY - box.top) / box.height - 0.5;
            couches.forEach(({ el, k }) => (el.style.transform = `translate(${dx * 18 * k}px, ${dy * 14 * k}px)`));
          });
        });
        ecouter(hero, "pointerleave", () => couches.forEach(({ el }) => (el.style.transform = "")));
        nettoyages.push(() => cancelAnimationFrame(image));
      }
    }
    r.querySelectorAll<HTMLElement>(".v-projecteur").forEach((carte) => {
      const spot = carte.querySelector<HTMLElement>(":scope > .v-spot");
      if (!spot) return;
      ecouter(carte, "pointermove", (e) => {
        const box = carte.getBoundingClientRect();
        spot.style.transform = `translate(${e.clientX - box.left}px, ${e.clientY - box.top}px)`;
      });
    });
    return () => nettoyages.forEach((f) => f());
  }, []);

  const classesRacine = ["v-racine", "v-js", entree && "v-entree"].filter(Boolean).join(" ");

  return (
    <div className={classesRacine} ref={racine}>
      <a className="v-evitement" href="#contenu">
        {T.evitement}
      </a>

      <header className={navCachee ? "v-nav v-cachee" : "v-nav"}>
        <div className="v-nav__pilule">
          <Logo aria={T.hautDePage} />
          <nav className="v-nav__liens" aria-label={T.navAria}>
            {SECTIONS.map((s) => (
              <a key={s} href={`#${s}`} className={ici === s ? "v-ici" : undefined}>
                {T.nav[s]}
              </a>
            ))}
          </nav>
          <SelecteurLangue />
          <a className="v-bouton v-bouton--petit" href="#depot">
            {T.deposerCours}
          </a>
        </div>
      </header>

      <main id="contenu">
        {/* 1. Hero : dégradé vivant, titre en trois temps, surligneur jaune */}
        <section className="v-hero" id="haut" aria-labelledby="v-hero-titre">
          <Degrade />
          <div className="v-hero__voile" aria-hidden="true" />
          <div className="v-conteneur v-hero__grille">
            <div className="v-hero__texte">
              <h1 id="v-hero-titre" className="v-hero__titre">
                {T.hero.lignes.map((l) => (
                  <span key={l} className="v-ligne">
                    <span>{l}</span>
                  </span>
                ))}
                <span className="v-ligne">
                  <Surligne texte={T.hero.surligne} />
                </span>
              </h1>
              <p className="v-hero__chapo">{T.hero.chapo}</p>
              <div className="v-hero__actions">
                <a className="v-bouton v-bouton--clair v-aimant" href="#depot">
                  <IconeDepot />
                  <span>{T.deposerMonCours}</span>
                </a>
                <a className="v-bouton v-bouton--contour" href="#cours" onClick={demo("cours")}>
                  {T.hero.demo}
                </a>
              </div>
              <p className="v-hero__local">
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M10 2.5l6 2.5v4.5c0 4-2.7 6.9-6 8-3.3-1.1-6-4-6-8V5z" />
                  <path d="M7.2 10l2 2 3.8-4" />
                </svg>
                {T.hero.local}
              </p>
            </div>
            <div className="v-hero__mascotte" aria-hidden="true">
              <div className="v-mascotte-badge" data-parallaxe="1">
                <img src="/img/logo-icone.png" alt="" width={512} height={512} fetchPriority="high" />
              </div>
              <span className="v-bulle v-bulle--1" data-parallaxe="0.6">
                <Riche texte={T.bulles[0]} />
              </span>
              <span className="v-bulle v-bulle--2" data-parallaxe="1.3">
                {T.bulles[1]} <b className="v-cite">Slide 7</b>
              </span>
              <span className="v-bulle v-bulle--3" data-parallaxe="0.9">
                <Riche texte={T.bulles[2]} />
              </span>
            </div>
          </div>
          <a className="v-hero__defiler" href="#essai" aria-label={T.hero.defiler}>
            <span />
          </a>
        </section>

        {/* 2. Bandeau des matières du corpus */}
        <div className="v-bandeau" aria-label={T.bandeauAria}>
          <div className="v-bandeau__piste">
            {[false, true].map((double) => (
              <ul key={String(double)} aria-hidden={double || undefined}>
                {T.matieres.map((m) => (
                  <li key={m} lang={m === "العربية" ? "ar" : undefined}>
                    {m}
                  </li>
                ))}
              </ul>
            ))}
          </div>
        </div>

        {/* 3. Le tuteur, jouable */}
        <section className="v-section" id="essai" aria-labelledby="v-essai-titre">
          <div className="v-conteneur">
            <Revele className="v-entete">
              <h2 id="v-essai-titre">
                {T.essai.titre} <span className="v-accent">{T.essai.accent}</span>
              </h2>
              <p>{T.essai.texte}</p>
            </Revele>
            <div className="v-scene-tuteur">
              <Tuteur surDemo={surDemo} />
            </div>
          </div>
        </section>

        {/* 4. Les chiffres, qui comptent à l'arrivée */}
        <section className="v-chiffres" aria-label={T.chiffresAria}>
          <div className="v-conteneur v-chiffres__ligne">
            {[47, 160, 6, 0].map((n, i) => (
              <p key={i}>
                <Compteur cible={n} />
                <span>{T.chiffres[i]}</span>
              </p>
            ))}
          </div>
        </section>

        {/* 5. Les agents (bande marine) */}
        <section className="v-section v-section--marine" id="agents" aria-labelledby="v-agents-titre">
          <Degrade doux />
          <div className="v-conteneur">
            <Revele className="v-entete">
              <h2 id="v-agents-titre">
                {T.agents.titre} <span className="v-accent">{T.agents.accent}</span>
              </h2>
              <p>{T.agents.texte}</p>
            </Revele>
            <Routeur />
          </div>
        </section>

        {/* 6. Le parcours */}
        <section className="v-section" id="parcours" aria-labelledby="v-parcours-titre">
          <div className="v-conteneur">
            <Revele className="v-entete">
              <h2 id="v-parcours-titre">
                {T.parcours.titre} <span className="v-accent">{T.parcours.accent}</span>
              </h2>
              <p>{T.parcours.texte}</p>
            </Revele>
            <Parcours />
          </div>
        </section>

        {/* 7. Preuves : une question du jeu d'évaluation, à jouer */}
        <section className="v-section v-section--ciel" id="preuves" aria-labelledby="v-preuves-titre">
          <div className="v-conteneur">
            <Revele className="v-entete">
              <h2 id="v-preuves-titre">
                {T.preuves.titre} <span className="v-accent">{T.preuves.accent}</span>
              </h2>
              <p>{T.preuves.texte}</p>
            </Revele>
            <QcmPreuve />
          </div>
        </section>

        {/* 8. Questions */}
        <section className="v-section" id="questions" aria-labelledby="v-questions-titre">
          <div className="v-conteneur v-faq-grille">
            <Revele className="v-entete">
              <h2 id="v-questions-titre">{T.faq.titre}</h2>
              <p>{T.faq.texte}</p>
            </Revele>
            <div className="v-faq">
              {T.faq.items.map(([q, r]) => (
                <details key={q}>
                  <summary>{q}</summary>
                  <p>{r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* 9. Fin : grand titre sur le dégradé */}
        <section className="v-fin" aria-labelledby="v-fin-titre">
          <Degrade clair={1} />
          <div className="v-conteneur v-fin__contenu">
            <Revele as="h2" id="v-fin-titre" className="v-fin__titre">
              {T.fin.titre} <Surligne texte={T.fin.surligne} fin />
            </Revele>
            <Revele as="p">{T.fin.texte}</Revele>
            <Revele className="v-fin__actions">
              <a className="v-bouton v-bouton--clair v-bouton--grand v-aimant" href="#depot">
                <IconeDepot />
                <span>{T.deposerMonCours}</span>
              </a>
              <a className="v-bouton v-bouton--contour v-bouton--grand" href="#cours" onClick={demo("cours")}>
                {T.fin.demo}
              </a>
            </Revele>
          </div>
        </section>
      </main>

      <footer className="v-pied">
        <div className="v-conteneur v-pied__grille">
          <Logo aria={T.hautDePage} />
          <nav aria-label={T.pied.aria}>
            <a href="#depot">{T.deposerCours}</a>
            {SECTIONS.map((s) => (
              <a key={s} href={`#${s}`}>
                {T.nav[s]}
              </a>
            ))}
            <a href="#quiz" onClick={demo("quiz")}>
              {T.pied.quiz}
            </a>
          </nav>
          <p>{T.pied.copyright}</p>
        </div>
      </footer>

      <nav className={barreVisible ? "v-barre-action v-visible" : "v-barre-action"} aria-label={T.actionAria}>
        <a className="v-bouton" href="#depot">
          {T.deposerMonCours}
        </a>
      </nav>
    </div>
  );
}
