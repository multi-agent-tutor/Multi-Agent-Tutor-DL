// Landing — interactions : fenêtre du tuteur, parcours, routeur d'agents, QCM du jeu d'évaluation.
// Dépend de ../maquettes.js (MASCOTTE_SVG, dessinerMascottes, etatMascotte, reduireMouvement).

const attendre = ms => new Promise(r => setTimeout(r, reduireMouvement() ? 0 : ms));
const cites = numeros => numeros.map(n => `<span class="cite">Slide ${n}</span>`).join("");

/* ------------------------------------------------------------------ sélecteur de niveau */
function placerCurseur(groupe) {
  const actif = groupe.querySelector('button[aria-pressed="true"]');
  const curseur = groupe.querySelector(".curseur");
  if (!actif || !curseur) return;
  curseur.style.width = `${actif.offsetWidth}px`;
  curseur.style.transform = `translateX(${actif.offsetLeft}px)`;
}

/* ------------------------------------------------------------------ 1. fenêtre du tuteur */
const SLIDES = {
  5: { titre: "Un petit gradient", question: "C'est quoi un gradient stochastique ?", reponses: {
    debutant: ["Au lieu de calculer la pente sur toutes les données, on la calcule sur un seul exemple tiré au hasard : c'est bien plus rapide, mais un peu bruité.", [5]],
    intermediaire: ["On remplace le gradient de la perte totale par celui d'un exemple i tiré au hasard : ∇fᵢ(x) est un estimateur sans biais de ∇f(x), bien moins coûteux à calculer.", [5, 3]],
    avance: ["Avec i uniforme, ∇fᵢ(x) estime ∇f(x) sans biais pour un coût en O(1) au lieu de O(n), au prix d'une variance qui ne s'annule pas au minimiseur.", [5, 7]],
  } },
  7: { titre: "Pourquoi ça marche ?", question: "Pourquoi la méthode oscille autour du minimum ?", reponses: {
    debutant: ["Au fond de la vallée, la pente moyenne est nulle, mais chaque exemple tire encore dans sa propre direction : avec des pas de taille fixe, on continue de bouger un peu.", [7]],
    intermediaire: ["Au minimiseur X*, le gradient total est nul mais pas les gradients locaux : à pas constant, chaque pas déplace encore le point.", [7, 23]],
    avance: ["En X*, ∇f(X*) = 0 mais la variance des ∇fᵢ(X*) reste positive : à pas constant α, l'itéré ne converge que vers un voisinage de X* de taille proportionnelle à α.", [7, 23]],
  } },
  23: { titre: "Pas décroissant", question: "Pourquoi faire décroître le pas ?", reponses: {
    debutant: ["Des pas de plus en plus petits calment les oscillations : on avance vite au début, puis on se pose doucement sur le minimum.", [23]],
    intermediaire: ["Avec un pas αₖ qui décroît, par exemple en 1/k, le bruit des gradients locaux s'atténue et l'itéré converge vers X*.", [23, 7]],
    avance: ["Il faut Σαₖ = ∞ pour atteindre X* et Σαₖ² < ∞ pour contrôler la variance : αₖ = 1/k vérifie les deux conditions.", [23]],
  } },
};

function brancherTuteur() {
  const fenetre = document.querySelector("[data-tuteur]");
  if (!fenetre) return;
  const question = fenetre.querySelector(".msg--moi");
  const outil = fenetre.querySelector(".outil");
  const texte = fenetre.querySelector(".ecrit");
  const sources = fenetre.querySelector(".sources");
  const mascotte = fenetre.querySelector(".msg--tuteur");
  const niveaux = fenetre.querySelector(".niveaux");
  let slide = 7, niveau = "intermediaire", tour = 0;

  async function repondre() {
    const moi = ++tour;
    const { question: q, reponses } = SLIDES[slide];
    const [phrase, numeros] = reponses[niveau];
    question.textContent = q;
    sources.innerHTML = "";
    texte.textContent = "";
    outil.hidden = false;
    etatMascotte(mascotte, "reflechit");
    await attendre(650);
    if (moi !== tour) return;
    outil.hidden = true;
    texte.classList.add("en-cours");
    const mots = phrase.split(" ");
    for (let i = 0; i < mots.length; i++) {
      if (moi !== tour) return;
      texte.textContent = mots.slice(0, i + 1).join(" ");
      if (!reduireMouvement()) await attendre(28);
    }
    if (reduireMouvement()) texte.textContent = phrase;
    texte.classList.remove("en-cours");
    sources.innerHTML = cites(numeros);
    sources.querySelectorAll(".cite").forEach(c => c.classList.add("entre"));
    etatMascotte(mascotte, "contente", 1400);
  }

  fenetre.querySelectorAll(".tw__slide").forEach(b => b.addEventListener("click", () => {
    slide = Number(b.dataset.slide);
    fenetre.querySelectorAll(".tw__slide").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    repondre();
  }));
  niveaux.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    niveau = b.dataset.niveau;
    niveaux.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    placerCurseur(niveaux);
    repondre();
  }));
  placerCurseur(niveaux);
  addEventListener("resize", () => placerCurseur(niveaux));
  repondre();
}

/* ------------------------------------------------------------------ 2. parcours en quatre étapes */
function brancherParcours() {
  const liste = document.querySelector("[data-parcours]");
  if (!liste) return;
  const onglets = [...liste.querySelectorAll('[role="tab"]')];
  function choisir(onglet, focus = false) {
    onglets.forEach(o => {
      const actif = o === onglet;
      o.setAttribute("aria-selected", String(actif));
      o.tabIndex = actif ? 0 : -1;
      const vue = document.getElementById(o.getAttribute("aria-controls"));
      vue.hidden = !actif;
      vue.classList.remove("entre");
      if (actif) { void vue.offsetWidth; vue.classList.add("entre"); }
    });
    if (focus) onglet.focus();
  }
  onglets.forEach((o, i) => {
    o.addEventListener("click", () => choisir(o));
    o.addEventListener("keydown", e => {
      const pas = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (pas) { e.preventDefault(); choisir(onglets[(i + pas + onglets.length) % onglets.length], true); }
      if (e.key === "Home") { e.preventDefault(); choisir(onglets[0], true); }
      if (e.key === "End") { e.preventDefault(); choisir(onglets.at(-1), true); }
    });
  });
  document.querySelectorAll(".flashcard").forEach(c => c.addEventListener("click", () =>
    c.setAttribute("aria-pressed", String(c.getAttribute("aria-pressed") !== "true"))));
  // La première scène joue quand la section arrive à l'écran.
  new IntersectionObserver((entrees, obs) => {
    if (entrees.some(e => e.isIntersecting)) { choisir(onglets.find(o => o.getAttribute("aria-selected") === "true")); obs.disconnect(); }
  }, { threshold: 0.35 }).observe(liste);
}

/* ------------------------------------------------------------------ 3. routeur d'agents */
const ROUTES = {
  explainer: { agent: "explainer", critic: "Critic : <b>4 affirmations sur 4</b> appuyées par le cours", valide: true,
    titre: "Explainer · niveau intermédiaire", texte: `Idée clé : à pas constant, la descente stochastique oscille autour du minimum, car les gradients locaux n'y sont pas nuls.${cites([7])}` },
  qa: { agent: "qa", critic: "Critic : <b>3 affirmations sur 3</b> appuyées par le cours", valide: true,
    titre: "Q&A · réponse sourcée", texte: `Pour que le bruit des gradients locaux s'éteigne : avec un pas décroissant, l'itéré converge vers X*.${cites([23, 7])}` },
  refus: { agent: "qa", critic: "Critic : refus, <b>rien à vérifier</b>", valide: true,
    titre: "Q&A · hors du cours", texte: "L'information n'est pas dans le cours. Je peux t'expliquer la descente de gradient stochastique, le sujet de ce chapitre." },
  quiz: { agent: "quiz", critic: "Critic : <b>3 QCM sur 3</b> validés, une seule bonne réponse chacun", valide: true,
    titre: "Quiz · 3 QCM", texte: `1. Que vaut le gradient total au minimiseur X* ?${cites([7])}` },
  resources: { agent: "resources", critic: "Pas de Critic : ressources tirées du catalogue local", valide: false,
    titre: "Resources · catalogue local", texte: "Deux ressources sur « descente de gradient stochastique » : un chapitre de cours et une vidéo, classés par niveau." },
};

function brancherRouteur() {
  const zone = document.querySelector("[data-routeur]");
  if (!zone) return;
  const boutons = [...zone.querySelectorAll(".demande")];
  const router = zone.querySelector(".noeud--router");
  const agents = zone.querySelector(".agents4");
  const critic = zone.querySelector(".critic");
  const sortie = zone.querySelector(".sortie");
  const liens = [...zone.querySelectorAll(".lien")];
  let tour = 0;

  async function router_(cle) {
    const moi = ++tour;
    const route = ROUTES[cle];
    boutons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.route === cle)));
    zone.querySelectorAll(".actif, .valide").forEach(n => n.classList.remove("actif", "valide"));
    agents.classList.remove("choisi");
    liens.forEach(l => l.classList.remove("passe"));
    sortie.classList.add("cache");
    critic.innerHTML = critic.dataset.repos;

    const pulser = async lien => { void lien.offsetWidth; lien.classList.add("passe"); await attendre(380); };
    await pulser(liens[0]);
    if (moi !== tour) return;
    router.classList.add("actif");
    etatMascotte(router, "reflechit");
    await attendre(420);
    if (moi !== tour) return;
    etatMascotte(router, "");
    await pulser(liens[1]);
    if (moi !== tour) return;
    agents.classList.add("choisi");
    agents.querySelector(`[data-agent="${route.agent}"]`).classList.add("actif");
    await attendre(360);
    await pulser(liens[2]);
    if (moi !== tour) return;
    critic.innerHTML = `<svg class="ok" viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span>${route.critic}</span>`;
    critic.classList.add("actif");
    if (route.valide) critic.classList.add("valide");
    await attendre(320);
    if (moi !== tour) return;
    sortie.innerHTML = `<small>${route.titre}</small>${route.texte}`;
    sortie.classList.remove("cache");
    sortie.querySelectorAll(".cite").forEach(c => c.classList.add("entre"));
    etatMascotte(router, "contente", 1200);
  }

  critic.dataset.repos = critic.innerHTML;
  boutons.forEach(b => b.addEventListener("click", () => router_(b.dataset.route)));
  new IntersectionObserver((entrees, obs) => {
    if (entrees.some(e => e.isIntersecting)) { router_("explainer"); obs.disconnect(); }
  }, { threshold: 0.4 }).observe(zone);
}

/* ------------------------------------------------------------------ 4. QCM du jeu d'évaluation */
function brancherQCM() {
  const qcm = document.querySelector("[data-qcm]");
  if (!qcm) return;
  const choix = [...qcm.querySelectorAll(".choix")];
  const retour = qcm.querySelector(".retour");
  const rejouer = qcm.querySelector(".rejouer");
  const message = retour.querySelector("p");
  choix.forEach(c => c.addEventListener("click", () => {
    const juste = c.dataset.juste === "true";
    choix.forEach(x => {
      x.disabled = true;
      if (x === c) x.classList.add(juste ? "juste" : "faux");
      if (x.dataset.juste === "true") x.classList.add("juste");
    });
    message.innerHTML = juste
      ? `Exact : au minimiseur, le gradient total est nul, mais pas les gradients locaux.${cites([7, 23])}`
      : `Pas tout à fait : au minimiseur, le gradient total est nul, mais les gradients locaux ne le sont pas. C'est ce qui fait osciller la méthode.${cites([7, 23])}`;
    retour.hidden = false;
    rejouer.hidden = false;
    etatMascotte(retour, juste ? "contente" : "oups", juste ? 1600 : 0);
    rejouer.focus({ preventScroll: true });
  }));
  rejouer.addEventListener("click", () => {
    choix.forEach(x => { x.disabled = false; x.classList.remove("juste", "faux"); });
    retour.hidden = true;
    rejouer.hidden = true;
    etatMascotte(retour, "");
    choix[0].focus();
  });

  const corpus = document.querySelector(".corpus");
  if (corpus) {
    corpus.classList.add("attend");
    new IntersectionObserver((entrees, obs) => {
      if (entrees.some(e => e.isIntersecting)) { corpus.classList.remove("attend"); obs.disconnect(); }
    }, { threshold: 0.5 }).observe(corpus);
  }
}

dessinerMascottes();
brancherTuteur();
brancherParcours();
brancherRouteur();
brancherQCM();

/* ================================================================== couche « agence créative » */
const pointeurFin = matchMedia("(hover: hover) and (pointer: fine)");

// Entrée du hero : une fois, dès que la première image est prête.
requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.add("entree")));

// Apparition au défilement (une seule fois par élément).
const observateurRevele = new IntersectionObserver((entrees, obs) => {
  entrees.forEach(e => { if (e.isIntersecting) { e.target.classList.add("vu"); obs.unobserve(e.target); } });
}, { threshold: 0.2, rootMargin: "0px 0px -8% 0px" });
document.querySelectorAll(".revele").forEach(el => observateurRevele.observe(el));

// Compteurs : comptent jusqu'à leur valeur à l'arrivée à l'écran (texte final déjà dans le HTML).
function compter(el) {
  const cible = Number(el.dataset.compte);
  if (reduireMouvement() || cible === 0) { el.textContent = String(cible); return; }
  const debut = performance.now(), duree = 1400;
  const pas = maintenant => {
    const x = Math.min(1, (maintenant - debut) / duree);
    el.textContent = String(Math.round(cible * (1 - Math.pow(1 - x, 4))));
    if (x < 1) requestAnimationFrame(pas);
  };
  el.textContent = "0";
  requestAnimationFrame(pas);
}
const observateurCompte = new IntersectionObserver((entrees, obs) => {
  entrees.forEach(e => { if (e.isIntersecting) { compter(e.target); obs.unobserve(e.target); } });
}, { threshold: 0.6 });
document.querySelectorAll("[data-compte]").forEach(el => observateurCompte.observe(el));

// Bouton aimanté : suit légèrement le curseur, revient en place en douceur.
if (pointeurFin.matches && !reduireMouvement()) {
  document.querySelectorAll(".aimant").forEach(b => {
    b.addEventListener("pointermove", e => {
      const r = b.getBoundingClientRect();
      const x = (e.clientX - r.left - r.width / 2) * 0.22, y = (e.clientY - r.top - r.height / 2) * 0.3;
      b.style.transform = `translate(${x}px, ${y}px)`;
    });
    b.addEventListener("pointerleave", () => { b.style.transform = ""; });
  });
}

// Parallaxe du hero : la mascotte et ses bulles suivent le curseur à des profondeurs différentes.
const hero = document.querySelector(".hero");
if (hero && pointeurFin.matches && !reduireMouvement()) {
  const couches = [...hero.querySelectorAll("[data-parallaxe]")].map(el => ({ el, k: Number(el.dataset.parallaxe || 1) }));
  let image = 0;
  hero.addEventListener("pointermove", e => {
    if (image) return;
    image = requestAnimationFrame(() => {
      image = 0;
      const r = hero.getBoundingClientRect();
      const dx = (e.clientX - r.left) / r.width - 0.5, dy = (e.clientY - r.top) / r.height - 0.5;
      couches.forEach(({ el, k }) => { el.style.transform = `translate(${dx * 18 * k}px, ${dy * 14 * k}px)`; });
    });
  });
  hero.addEventListener("pointerleave", () => couches.forEach(({ el }) => { el.style.transform = ""; }));
}

// Projecteur : une tache de lumière suit le curseur dans les cartes (transform sur un enfant, pas de variable héritée).
if (pointeurFin.matches) {
  document.querySelectorAll(".projecteur").forEach(carte => {
    const spot = document.createElement("span");
    spot.className = "spot";
    spot.setAttribute("aria-hidden", "true");
    carte.prepend(spot);
    carte.addEventListener("pointermove", e => {
      const r = carte.getBoundingClientRect();
      spot.style.transform = `translate(${e.clientX - r.left}px, ${e.clientY - r.top}px)`;
    });
  });
}

// Navigation : se cache en descendant, revient en remontant ; lien de la section courante marqué.
const nav = document.querySelector("[data-nav]");
const barre = document.querySelector(".barre-action");
let dernierY = scrollY, ticket = 0;
addEventListener("scroll", () => {
  if (ticket) return;
  ticket = requestAnimationFrame(() => {
    ticket = 0;
    const y = scrollY;
    nav.classList.toggle("cachee", y > 240 && y > dernierY + 4);
    if (y < dernierY - 4 || y < 240) nav.classList.remove("cachee");
    dernierY = y;
    if (barre) barre.classList.toggle("visible", y > innerHeight * 0.7);
    // Un saut de défilement (lien d'ancre, molette rapide) peut passer par-dessus un titre sans qu'il croise l'écran.
    document.querySelectorAll(".revele:not(.vu)").forEach(el => { if (el.getBoundingClientRect().bottom < 0) el.classList.add("vu"); });
  });
}, { passive: true });
const liens = new Map([...document.querySelectorAll(".nav__liens a")].map(a => [a.getAttribute("href").slice(1), a]));
new IntersectionObserver(entrees => {
  entrees.forEach(e => {
    if (!e.isIntersecting) return;
    liens.forEach(a => a.classList.remove("ici"));
    liens.get(e.target.id)?.classList.add("ici");
  });
}, { rootMargin: "-45% 0px -50% 0px" }).observe(document.querySelector("#essai"));
["#agents", "#parcours", "#preuves"].forEach(s => document.querySelector(s) && (function (el) {
  new IntersectionObserver(entrees => entrees.forEach(e => {
    if (!e.isIntersecting) return;
    liens.forEach(a => a.classList.remove("ici"));
    liens.get(el.id)?.classList.add("ici");
  }), { rootMargin: "-45% 0px -50% 0px" }).observe(el);
})(document.querySelector(s)));
