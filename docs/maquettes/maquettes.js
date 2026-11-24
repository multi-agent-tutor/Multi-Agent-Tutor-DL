// D2 — Comportements communs des maquettes : mascotte du logo et langue de l'interface.

// La mascotte du logo, redessinée en SVG pour pouvoir changer d'état :
// data-etat = "" (sourit), "reflechit" (l'agent génère), "contente" (bonne réponse), "oups" (erreur).
const MASCOTTE_SVG = `
<svg class="mascotte" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
  <g class="eclats">
    <path d="M10 30 L4 26"/><path d="M14 22 L11 15"/><path d="M8 40 L1 40"/>
  </g>
  <g class="tete">
    <rect class="contour" x="12" y="49" width="9" height="17" rx="4.5" fill="#fff"/>
    <rect class="contour" x="79" y="49" width="9" height="17" rx="4.5" fill="#fff"/>
    <rect class="contour" x="19" y="33" width="62" height="52" rx="25" fill="#fff"/>
    <rect x="27" y="45" width="46" height="26" rx="12" fill="#0B1A45"/>
    <g class="yeux yeux-arcs" fill="none" stroke="#4C8AFD" stroke-width="4" stroke-linecap="round">
      <path d="M36 61 q5.5 -8 11 0"/><path d="M53 61 q5.5 -8 11 0"/>
    </g>
    <g class="yeux yeux-points" fill="#4C8AFD">
      <circle cx="40" cy="58" r="3.4"/><circle cx="50" cy="58" r="3.4"/><circle cx="60" cy="58" r="3.4"/>
    </g>
    <g class="yeux yeux-oups" fill="none" stroke="#4C8AFD" stroke-width="4" stroke-linecap="round">
      <path d="M36 58 h11"/><path d="M53 58 h11"/>
    </g>
    <path class="contour" d="M18 21 L52 9 L86 21 L52 33 Z" fill="#2563EB"/>
    <path class="contour" d="M33 27 V35 H71 V27" fill="#1D4ED8"/>
    <path d="M82 22 V37" stroke="#FBBF24" stroke-width="3" stroke-linecap="round"/>
    <rect x="78.5" y="35" width="7" height="10" rx="3" fill="#FBBF24" stroke="#0B1A45" stroke-width="2"/>
  </g>
</svg>`;

function dessinerMascottes(racine = document) {
  racine.querySelectorAll("[data-mascotte]").forEach(el => {
    if (!el.querySelector("svg.mascotte")) el.insertAdjacentHTML("afterbegin", MASCOTTE_SVG);
  });
}

function etatMascotte(el, etat, duree) {
  const svg = el.matches("svg.mascotte") ? el : el.querySelector("svg.mascotte");
  if (!svg) return;
  svg.dataset.etat = etat || "";
  clearTimeout(svg._minuteur);
  if (duree) svg._minuteur = setTimeout(() => (svg.dataset.etat = ""), duree);
}

// Langue de l'interface (A7) : libellés traduits, l'arabe passe la mise en page de droite à gauche.
let LIBELLES = null, LANGUE = "fr";
function traduire(racine = document) {
  if (!LIBELLES) return;
  const t = LIBELLES[LANGUE];
  racine.querySelectorAll("[data-t]").forEach(e => { if (t[e.dataset.t]) e.textContent = t[e.dataset.t]; });
  racine.querySelectorAll("[data-ph]").forEach(e => { if (t[e.dataset.ph]) e.placeholder = t[e.dataset.ph]; });
}
function brancherLangues(libelles, apres) {
  LIBELLES = libelles;
  const boutons = document.querySelectorAll(".langues button");
  boutons.forEach(b => b.addEventListener("click", () => {
    LANGUE = b.dataset.lang;
    document.documentElement.lang = LANGUE;
    document.documentElement.dir = LANGUE === "ar" ? "rtl" : "ltr";
    traduire();
    boutons.forEach(x => x.setAttribute("aria-pressed", x === b));
    if (apres) apres(LANGUE);
  }));
}

const reduireMouvement = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
