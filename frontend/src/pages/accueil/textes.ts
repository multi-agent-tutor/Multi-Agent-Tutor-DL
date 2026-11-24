// Textes de la landing (maquette D2 docs/maquettes/accueil/index.html et accueil.js) en FR / EN / AR.
// Mini-balisage : **gras**, $formule LaTeX$ (rendue par KaTeX). Les noms d'agents restent en anglais.
import type { LangueUI, Niveau } from "../../types";

export type Route = "explainer" | "qa" | "quiz" | "resources" | "refus";
export type NumeroDemo = 5 | 7 | 23;
type Reponse = [texte: string, sources: number[]];

export interface TextesAccueil {
  titrePage: string;
  evitement: string;
  hautDePage: string;
  navAria: string;
  nav: { essai: string; agents: string; parcours: string; preuves: string };
  langueAria: string;
  deposerCours: string;
  deposerMonCours: string;
  hero: { lignes: [string, string]; surligne: string; chapo: string; demo: string; local: string; defiler: string };
  bulles: [string, string, string];
  bandeauAria: string;
  matieres: string[];
  essai: {
    titre: string;
    accent: string;
    texte: string;
    cours: string;
    chapitre: string;
    meta: string;
    choisir: string;
    niveau: string;
    recherche: string;
    tester: string;
    essayer: string;
  };
  slides: Record<NumeroDemo, { titre: string; question: string; reponses: Record<Niveau, Reponse> }>;
  niveaux: Record<Niveau, string>;
  chiffresAria: string;
  chiffres: [string, string, string, string];
  agents: {
    titre: string;
    accent: string;
    texte: string;
    demandesAria: string;
    demandesTitre: string;
    demandes: Record<Route, string>;
    router: string;
    sous: Record<Exclude<Route, "refus">, string>;
    criticRepos: string;
    local: string;
    routes: Record<Route, { critic: string; valide: boolean; titre: string; texte: string; sources: number[] }>;
  };
  parcours: {
    titre: string;
    accent: string;
    texte: string;
    aria: string;
    etapes: [string, string][];
    fichier: string;
    fichierMeta: string;
    lu: [string, string][];
    rubriques: { dt: string; dd: string; source?: number; retenir?: boolean }[];
    qa: { q1: string; r1: string; s1: number[]; q2: string; refus: string };
    carte: { aria: string; recto: string; rectoTexte: string; verso: string; versoTexte: string; indice: string };
  };
  preuves: {
    titre: string;
    accent: string;
    texte: string;
    qcmTitre: string;
    question: string;
    choix: [string, string, string, string];
    juste: string;
    faux: string;
    verdictJuste: string;
    verdictFaux: string;
    reessayer: string;
    corpusTitre: string;
    corpus: [string, string, number][];
    note: string;
  };
  faq: { titre: string; texte: string; items: [string, string][] };
  fin: { titre: string; surligne: string; texte: string; demo: string };
  pied: { aria: string; quiz: string; copyright: string };
  actionAria: string;
}

const fr: TextesAccueil = {
  titrePage: "Multi-Agent Tutor : tuteur IA pour réviser tes slides de cours",
  evitement: "Aller au contenu",
  hautDePage: "Multi-Agent Tutor, haut de page",
  navAria: "Principal",
  nav: { essai: "Essayer", agents: "Agents", parcours: "Parcours", preuves: "Preuves" },
  langueAria: "Langue",
  deposerCours: "Déposer un cours",
  deposerMonCours: "Déposer mon cours",
  hero: {
    lignes: ["Tes slides de cours,", "expliquées, questionnées,"],
    surligne: "révisées.",
    chapo:
      "Dépose un cours en PPTX ou PDF : six agents l'expliquent slide par slide sur trois niveaux, répondent en citant tes slides et te font réviser.",
    demo: "Essayer la démo",
    local: "100 % local : aucune API, ton cours ne quitte pas ta machine.",
    defiler: "Descendre vers la démonstration",
  },
  bulles: ["Explainer **3 niveaux**", "Q&A", "Critic **4/4 ✓**"],
  bandeauAria: "Matières du corpus de test",
  matieres: ["Machine learning", "Deep learning", "Maths", "Réseaux", "Cloud", "Bases de données", "Français", "English", "العربية"],
  essai: {
    titre: "Choisis une slide et un niveau.",
    accent: "Le tuteur répond.",
    texte:
      "Une vraie page du cours d'optimisation : la réponse change avec la slide et avec ton niveau, et cite toujours ses sources.",
    cours: "Optimisation pour le ML",
    chapitre: "Ch. 3",
    meta: "FR · 24 slides",
    choisir: "Choisis une slide",
    niveau: "Niveau de l'explication",
    recherche: "Recherche dans les slides du chapitre 3",
    tester: "Me tester sur cette slide",
    essayer: "Essayer avec mon cours",
  },
  slides: {
    5: {
      titre: "Un petit gradient",
      question: "C'est quoi un gradient stochastique ?",
      reponses: {
        debutant: [
          "Au lieu de calculer la pente sur toutes les données, on la calcule sur un seul exemple tiré au hasard : c'est bien plus rapide, mais un peu bruité.",
          [5],
        ],
        intermediaire: [
          "On remplace le gradient de la perte totale par celui d'un exemple $i$ tiré au hasard : $\\nabla f_i(x)$ est un estimateur sans biais de $\\nabla f(x)$, bien moins coûteux à calculer.",
          [5, 3],
        ],
        avance: [
          "Avec $i$ uniforme, $\\nabla f_i(x)$ estime $\\nabla f(x)$ sans biais pour un coût en $O(1)$ au lieu de $O(n)$, au prix d'une variance qui ne s'annule pas au minimiseur.",
          [5, 7],
        ],
      },
    },
    7: {
      titre: "Pourquoi ça marche ?",
      question: "Pourquoi la méthode oscille autour du minimum ?",
      reponses: {
        debutant: [
          "Au fond de la vallée, la pente moyenne est nulle, mais chaque exemple tire encore dans sa propre direction : avec des pas de taille fixe, on continue de bouger un peu.",
          [7],
        ],
        intermediaire: [
          "Au minimiseur $X^*$, le gradient total est nul mais pas les gradients locaux : à pas constant, chaque pas déplace encore le point.",
          [7, 23],
        ],
        avance: [
          "En $X^*$, $\\nabla f(X^*) = 0$ mais la variance des $\\nabla f_i(X^*)$ reste positive : à pas constant $\\alpha$, l'itéré ne converge que vers un voisinage de $X^*$ de taille proportionnelle à $\\alpha$.",
          [7, 23],
        ],
      },
    },
    23: {
      titre: "Pas décroissant",
      question: "Pourquoi faire décroître le pas ?",
      reponses: {
        debutant: [
          "Des pas de plus en plus petits calment les oscillations : on avance vite au début, puis on se pose doucement sur le minimum.",
          [23],
        ],
        intermediaire: [
          "Avec un pas $\\alpha_k$ qui décroît, par exemple en $1/k$, le bruit des gradients locaux s'atténue et l'itéré converge vers $X^*$.",
          [23, 7],
        ],
        avance: [
          "Il faut $\\sum \\alpha_k = \\infty$ pour atteindre $X^*$ et $\\sum \\alpha_k^2 < \\infty$ pour contrôler la variance : $\\alpha_k = 1/k$ vérifie les deux conditions.",
          [23],
        ],
      },
    },
  },
  niveaux: { debutant: "Débutant", intermediaire: "Intermédiaire", avance: "Avancé" },
  chiffresAria: "Le projet en chiffres",
  chiffres: ["vrais cours de test", "questions relues", "agents spécialisés", "appel à une API"],
  agents: {
    titre: "Six agents.",
    accent: "Une seule réponse, vérifiée.",
    texte:
      "Choisis une demande : le Router la confie au bon agent, puis le Critic vérifie la réponse dans ton cours avant qu'elle t'arrive.",
    demandesAria: "Demandes d'exemple",
    demandesTitre: "Ta demande sur la slide 7",
    demandes: {
      explainer: "Explique-moi cette slide",
      qa: "Pourquoi le pas doit-il décroître ?",
      quiz: "Teste-moi sur ce chapitre",
      resources: "Une vidéo pour aller plus loin",
      refus: "Qui a inventé Python ?",
    },
    router: "lit ta demande",
    sous: { explainer: "3 niveaux", qa: "cite ses slides", quiz: "QCM, flashcards", resources: "catalogue local" },
    criticRepos: "**Critic** vérifie chaque affirmation dans le cours",
    local: "Un seul modèle de langage local fait tourner les six agents : aucune API, aucun envoi de ton cours.",
    routes: {
      explainer: {
        critic: "Critic : **4 affirmations sur 4** appuyées par le cours",
        valide: true,
        titre: "Explainer · niveau intermédiaire",
        texte: "Idée clé : à pas constant, la descente stochastique oscille autour du minimum, car les gradients locaux n'y sont pas nuls.",
        sources: [7],
      },
      qa: {
        critic: "Critic : **3 affirmations sur 3** appuyées par le cours",
        valide: true,
        titre: "Q&A · réponse sourcée",
        texte: "Pour que le bruit des gradients locaux s'éteigne : avec un pas décroissant, l'itéré converge vers $X^*$.",
        sources: [23, 7],
      },
      refus: {
        critic: "Critic : refus, **rien à vérifier**",
        valide: true,
        titre: "Q&A · hors du cours",
        texte: "L'information n'est pas dans le cours. Je peux t'expliquer la descente de gradient stochastique, le sujet de ce chapitre.",
        sources: [],
      },
      quiz: {
        critic: "Critic : **3 QCM sur 3** validés, une seule bonne réponse chacun",
        valide: true,
        titre: "Quiz · 3 QCM",
        texte: "1. Que vaut le gradient total au minimiseur $X^*$ ?",
        sources: [7],
      },
      resources: {
        critic: "Pas de Critic : ressources tirées du catalogue local",
        valide: false,
        titre: "Resources · catalogue local",
        texte: "Deux ressources sur « descente de gradient stochastique » : un chapitre de cours et une vidéo, classés par niveau.",
        sources: [],
      },
    },
  },
  parcours: {
    titre: "Quatre étapes,",
    accent: "un cours compris.",
    texte:
      "Chaque étape est confiée à un agent spécialisé ; le Critic vérifie que tout ce qui est dit vient bien de tes slides.",
    aria: "Étapes du parcours",
    etapes: [
      ["Dépôt du cours en PPTX ou PDF", "Même scanné : texte, figures et formules sont lus en local."],
      ["Explication de chaque slide", "À partir de la slide, de ses voisines et des notions qu'elle suppose."],
      ["Questions avec leurs sources", "Chaque réponse cite ses slides ; hors du cours, le tuteur le dit."],
      ["Quiz et flashcards de révision", "QCM corrigés tout de suite, flashcards à retourner."],
    ],
    fichier: "optimisation_ml_ch3.pdf",
    fichierMeta: "24 slides · 3,1 Mo · lu sur ta machine",
    lu: [
      ["24", "slides de texte"],
      ["9", "figures décrites"],
      ["14", "formules lues"],
    ],
    rubriques: [
      { dt: "Idée clé", dd: "À pas constant, la méthode oscille autour du minimum.", source: 7 },
      { dt: "Explication", dd: "Le gradient total s'annule en $X^*$, mais pas les gradients locaux." },
      { dt: "Exemple", dd: "Deux exemples tirent à gauche, un à droite : le point bouge encore." },
      { dt: "Lien slide 6", dd: "On reprend le pas constant présenté juste avant.", source: 6 },
      { dt: "À retenir", dd: "Pas constant = convergence vers un voisinage de $X^*$", retenir: true },
    ],
    qa: {
      q1: "Pourquoi faire décroître le pas ?",
      r1: "Avec un pas qui décroît, le bruit des gradients locaux s'atténue et l'itéré converge vers $X^*$.",
      s1: [23, 7],
      q2: "Et qui a inventé Python ?",
      refus: "L'information n'est pas dans le cours.",
    },
    carte: {
      aria: "Flashcard : clique pour voir la réponse",
      recto: "Recto · slide 23",
      rectoTexte: "Quelles conditions sur le pas $\\alpha_k$ ?",
      verso: "Verso",
      versoTexte: "$\\sum \\alpha_k = \\infty$ et $\\sum \\alpha_k^2 < \\infty$, par exemple $\\alpha_k = 1/k$.",
      indice: "Clique sur la carte pour la retourner.",
    },
  },
  preuves: {
    titre: "Testé sur 47 vrais cours.",
    accent: "À toi de jouer.",
    texte: "En français et en anglais, avec 160 questions d'évaluation écrites et relues par l'équipe. En voici une.",
    qcmTitre: "Une question du jeu d'évaluation",
    question: "Pourquoi la descente stochastique à pas constant oscille-t-elle autour du minimiseur ?",
    choix: [
      "Le gradient total ne s'annule jamais",
      "Au minimiseur, les gradients locaux ne sont pas nuls",
      "Le pas est trop petit pour converger",
      "La fonction de coût n'est pas convexe",
    ],
    juste: "Exact : au minimiseur, le gradient total est nul, mais pas les gradients locaux.",
    faux: "Pas tout à fait : au minimiseur, le gradient total est nul, mais les gradients locaux ne le sont pas. C'est ce qui fait osciller la méthode.",
    verdictJuste: "Juste",
    verdictFaux: "Faux",
    reessayer: "Réessayer",
    corpusTitre: "Les cours du corpus de test",
    corpus: [
      ["Machine learning et deep learning", "23 cours", 0.489],
      ["Maths", "13 cours", 0.277],
      ["Réseaux", "8 cours", 0.17],
      ["Cloud et bases de données", "3 cours", 0.064],
    ],
    note: "Barres : part de chaque domaine dans les 47 cours.",
  },
  faq: {
    titre: "Questions fréquentes",
    texte: "Ce que les étudiants et les enseignants nous demandent le plus.",
    items: [
      [
        "Mes cours quittent-ils mon ordinateur ?",
        "Non. Le modèle de langage, la lecture des slides, la recherche et la voix tournent en local ; aucun service en ligne n'est appelé.",
      ],
      ["Quels fichiers puis-je déposer ?", "Des présentations PPTX et des PDF, y compris des slides scannées : le texte est alors lu par OCR."],
      [
        "Dans quelles langues fonctionne-t-il ?",
        "L'interface et les réponses existent en français, en anglais et en arabe, avec une mise en page de droite à gauche pour l'arabe.",
      ],
      [
        "Que se passe-t-il si la réponse n'est pas dans le cours ?",
        "Le tuteur répond que l'information n'est pas dans ton cours plutôt que d'inventer, et propose une notion proche qu'il peut expliquer.",
      ],
      [
        "Comment sait-on que l'explication est fidèle au cours ?",
        "L'agent Critic relit chaque réponse et vérifie que ses affirmations sont appuyées par les slides citées. Sinon, la réponse repart vers l'agent avec les corrections, deux fois au plus.",
      ],
    ],
  },
  fin: {
    titre: "Révise ton prochain cours",
    surligne: "autrement.",
    texte:
      "Un PPTX ou un PDF suffit : le tuteur le lit sur ta machine et t'ouvre la première slide. Pas encore de cours sous la main ? La démo s'ouvre sur un vrai cours.",
    demo: "Voir la démo",
  },
  pied: { aria: "Pied de page", quiz: "Page Quiz", copyright: "© 2026 Multi-Agent Tutor · projet de l'équipe Esprit" },
  actionAria: "Action rapide",
};

const en: TextesAccueil = {
  titrePage: "Multi-Agent Tutor: an AI tutor to revise your course slides",
  evitement: "Skip to content",
  hautDePage: "Multi-Agent Tutor, back to top",
  navAria: "Main",
  nav: { essai: "Try it", agents: "Agents", parcours: "How it works", preuves: "Evidence" },
  langueAria: "Language",
  deposerCours: "Upload a course",
  deposerMonCours: "Upload my course",
  hero: {
    lignes: ["Your course slides,", "explained, questioned,"],
    surligne: "revised.",
    chapo:
      "Upload a course as PPTX or PDF: six agents explain it slide by slide on three levels, answer by citing your slides and help you revise.",
    demo: "Try the demo",
    local: "100% local: no API, your course never leaves your machine.",
    defiler: "Scroll down to the demo",
  },
  bulles: ["Explainer **3 levels**", "Q&A", "Critic **4/4 ✓**"],
  bandeauAria: "Subjects of the test corpus",
  matieres: ["Machine learning", "Deep learning", "Maths", "Networks", "Cloud", "Databases", "Français", "English", "العربية"],
  essai: {
    titre: "Pick a slide and a level.",
    accent: "The tutor answers.",
    texte: "A real page from the optimisation course: the answer changes with the slide and with your level, and always cites its sources.",
    cours: "Optimisation for ML",
    chapitre: "Ch. 3",
    meta: "FR · 24 slides",
    choisir: "Pick a slide",
    niveau: "Explanation level",
    recherche: "Searching the slides of chapter 3",
    tester: "Test me on this slide",
    essayer: "Try with my course",
  },
  slides: {
    5: {
      titre: "A small gradient",
      question: "What is a stochastic gradient?",
      reponses: {
        debutant: [
          "Instead of computing the slope on all the data, we compute it on a single example picked at random: much faster, but a little noisy.",
          [5],
        ],
        intermediaire: [
          "We replace the gradient of the total loss with that of a random example $i$: $\\nabla f_i(x)$ is an unbiased estimator of $\\nabla f(x)$, far cheaper to compute.",
          [5, 3],
        ],
        avance: [
          "With $i$ uniform, $\\nabla f_i(x)$ estimates $\\nabla f(x)$ without bias at a cost of $O(1)$ instead of $O(n)$, at the price of a variance that does not vanish at the minimiser.",
          [5, 7],
        ],
      },
    },
    7: {
      titre: "Why does it work?",
      question: "Why does the method oscillate around the minimum?",
      reponses: {
        debutant: [
          "At the bottom of the valley the average slope is zero, but each example still pulls in its own direction: with fixed-size steps, we keep moving a little.",
          [7],
        ],
        intermediaire: [
          "At the minimiser $X^*$ the total gradient is zero but the local gradients are not: with a constant step, every step still moves the point.",
          [7, 23],
        ],
        avance: [
          "At $X^*$, $\\nabla f(X^*) = 0$ but the variance of the $\\nabla f_i(X^*)$ stays positive: with a constant step $\\alpha$, the iterate only converges to a neighbourhood of $X^*$ whose size is proportional to $\\alpha$.",
          [7, 23],
        ],
      },
    },
    23: {
      titre: "Decreasing step",
      question: "Why make the step decrease?",
      reponses: {
        debutant: ["Smaller and smaller steps calm the oscillations: we move fast at first, then settle gently on the minimum.", [23]],
        intermediaire: [
          "With a decreasing step $\\alpha_k$, for instance $1/k$, the noise of the local gradients fades and the iterate converges to $X^*$.",
          [23, 7],
        ],
        avance: [
          "We need $\\sum \\alpha_k = \\infty$ to reach $X^*$ and $\\sum \\alpha_k^2 < \\infty$ to control the variance: $\\alpha_k = 1/k$ satisfies both.",
          [23],
        ],
      },
    },
  },
  niveaux: { debutant: "Beginner", intermediaire: "Intermediate", avance: "Advanced" },
  chiffresAria: "The project in numbers",
  chiffres: ["real test courses", "reviewed questions", "specialised agents", "API calls"],
  agents: {
    titre: "Six agents.",
    accent: "One answer, checked.",
    texte: "Pick a request: the Router hands it to the right agent, then the Critic checks the answer against your course before it reaches you.",
    demandesAria: "Sample requests",
    demandesTitre: "Your request about slide 7",
    demandes: {
      explainer: "Explain this slide to me",
      qa: "Why must the step decrease?",
      quiz: "Test me on this chapter",
      resources: "A video to go further",
      refus: "Who invented Python?",
    },
    router: "reads your request",
    sous: { explainer: "3 levels", qa: "cites its slides", quiz: "MCQ, flashcards", resources: "local catalogue" },
    criticRepos: "**Critic** checks every claim against the course",
    local: "A single local language model runs all six agents: no API, your course is never sent anywhere.",
    routes: {
      explainer: {
        critic: "Critic: **4 claims out of 4** backed by the course",
        valide: true,
        titre: "Explainer · intermediate level",
        texte: "Key idea: with a constant step, stochastic descent oscillates around the minimum, because the local gradients are not zero there.",
        sources: [7],
      },
      qa: {
        critic: "Critic: **3 claims out of 3** backed by the course",
        valide: true,
        titre: "Q&A · sourced answer",
        texte: "So that the noise of the local gradients dies out: with a decreasing step, the iterate converges to $X^*$.",
        sources: [23, 7],
      },
      refus: {
        critic: "Critic: refusal, **nothing to check**",
        valide: true,
        titre: "Q&A · not in the course",
        texte: "This information is not in the course. I can explain stochastic gradient descent, the topic of this chapter.",
        sources: [],
      },
      quiz: {
        critic: "Critic: **3 MCQs out of 3** validated, one correct answer each",
        valide: true,
        titre: "Quiz · 3 MCQs",
        texte: "1. What is the total gradient at the minimiser $X^*$?",
        sources: [7],
      },
      resources: {
        critic: "No Critic: resources drawn from the local catalogue",
        valide: false,
        titre: "Resources · local catalogue",
        texte: "Two resources on “stochastic gradient descent”: a course chapter and a video, sorted by level.",
        sources: [],
      },
    },
  },
  parcours: {
    titre: "Four steps,",
    accent: "one course understood.",
    texte: "Each step is handled by a specialised agent; the Critic checks that everything said really comes from your slides.",
    aria: "Steps",
    etapes: [
      ["Upload your course as PPTX or PDF", "Even scanned: text, figures and formulas are read locally."],
      ["An explanation for every slide", "Built from the slide, its neighbours and the notions it assumes."],
      ["Questions with their sources", "Every answer cites its slides; outside the course, the tutor says so."],
      ["Quizzes and revision flashcards", "MCQs corrected instantly, flashcards to flip."],
    ],
    fichier: "optimisation_ml_ch3.pdf",
    fichierMeta: "24 slides · 3.1 MB · read on your machine",
    lu: [
      ["24", "text slides"],
      ["9", "figures described"],
      ["14", "formulas read"],
    ],
    rubriques: [
      { dt: "Key idea", dd: "With a constant step, the method oscillates around the minimum.", source: 7 },
      { dt: "Explanation", dd: "The total gradient vanishes at $X^*$, but the local gradients do not." },
      { dt: "Example", dd: "Two examples pull left, one pulls right: the point still moves." },
      { dt: "Link to slide 6", dd: "We build on the constant step introduced just before.", source: 6 },
      { dt: "Key takeaway", dd: "Constant step = convergence to a neighbourhood of $X^*$", retenir: true },
    ],
    qa: {
      q1: "Why make the step decrease?",
      r1: "With a decreasing step, the noise of the local gradients fades and the iterate converges to $X^*$.",
      s1: [23, 7],
      q2: "And who invented Python?",
      refus: "This information is not in the course.",
    },
    carte: {
      aria: "Flashcard: click to see the answer",
      recto: "Front · slide 23",
      rectoTexte: "Which conditions on the step $\\alpha_k$?",
      verso: "Back",
      versoTexte: "$\\sum \\alpha_k = \\infty$ and $\\sum \\alpha_k^2 < \\infty$, for instance $\\alpha_k = 1/k$.",
      indice: "Click the card to flip it.",
    },
  },
  preuves: {
    titre: "Tested on 47 real courses.",
    accent: "Your turn.",
    texte: "In French and English, with 160 evaluation questions written and reviewed by the team. Here is one.",
    qcmTitre: "A question from the evaluation set",
    question: "Why does constant-step stochastic descent oscillate around the minimiser?",
    choix: [
      "The total gradient never vanishes",
      "At the minimiser, the local gradients are not zero",
      "The step is too small to converge",
      "The cost function is not convex",
    ],
    juste: "Correct: at the minimiser the total gradient is zero, but the local gradients are not.",
    faux: "Not quite: at the minimiser the total gradient is zero, but the local gradients are not. That is what makes the method oscillate.",
    verdictJuste: "Correct",
    verdictFaux: "Wrong",
    reessayer: "Try again",
    corpusTitre: "Courses in the test corpus",
    corpus: [
      ["Machine learning and deep learning", "23 courses", 0.489],
      ["Maths", "13 courses", 0.277],
      ["Networks", "8 courses", 0.17],
      ["Cloud and databases", "3 courses", 0.064],
    ],
    note: "Bars: share of each field among the 47 courses.",
  },
  faq: {
    titre: "Frequently asked questions",
    texte: "What students and teachers ask us most.",
    items: [
      [
        "Do my courses leave my computer?",
        "No. The language model, slide reading, search and voice all run locally; no online service is called.",
      ],
      ["Which files can I upload?", "PPTX presentations and PDFs, including scanned slides: the text is then read by OCR."],
      ["Which languages does it support?", "The interface and the answers exist in French, English and Arabic, with a right-to-left layout for Arabic."],
      [
        "What if the answer is not in the course?",
        "The tutor says the information is not in your course instead of making it up, and suggests a related notion it can explain.",
      ],
      [
        "How do we know the explanation is faithful to the course?",
        "The Critic agent rereads every answer and checks that its claims are backed by the cited slides. Otherwise the answer goes back to the agent with corrections, at most twice.",
      ],
    ],
  },
  fin: {
    titre: "Revise your next course",
    surligne: "differently.",
    texte: "A PPTX or a PDF is all it takes: the tutor reads it on your machine and opens the first slide. No course at hand yet? The demo opens on a real course.",
    demo: "See the demo",
  },
  pied: { aria: "Footer", quiz: "Quiz page", copyright: "© 2026 Multi-Agent Tutor · a project by the Esprit team" },
  actionAria: "Quick action",
};

const ar: TextesAccueil = {
  titrePage: "Multi-Agent Tutor: معلّم ذكي لمراجعة شرائح دروسك",
  evitement: "الانتقال إلى المحتوى",
  hautDePage: "Multi-Agent Tutor، أعلى الصفحة",
  navAria: "القائمة الرئيسية",
  nav: { essai: "جرّب", agents: "الوكلاء", parcours: "المسار", preuves: "الأدلة" },
  langueAria: "اللغة",
  deposerCours: "ارفع درسًا",
  deposerMonCours: "ارفع درسي",
  hero: {
    lignes: ["شرائح دروسك،", "مشروحة، ومُسائَلة،"],
    surligne: "ومُراجَعة.",
    chapo: "ارفع درسًا بصيغة PPTX أو PDF: ستة وكلاء يشرحونه شريحة بشريحة على ثلاثة مستويات، ويجيبون مستشهدين بشرائحك، ويساعدونك على المراجعة.",
    demo: "جرّب العرض",
    local: "محلي 100٪: بلا واجهة برمجة، ولا يغادر درسك جهازك.",
    defiler: "انزل إلى العرض التوضيحي",
  },
  bulles: ["Explainer **3 مستويات**", "Q&A", "Critic **4/4 ✓**"],
  bandeauAria: "مواد مدوّنة الاختبار",
  matieres: ["تعلّم الآلة", "التعلّم العميق", "رياضيات", "شبكات", "الحوسبة السحابية", "قواعد البيانات", "Français", "English", "العربية"],
  essai: {
    titre: "اختر شريحة ومستوى.",
    accent: "المعلّم يجيب.",
    texte: "صفحة حقيقية من درس التحسين: تتغيّر الإجابة بتغيّر الشريحة ومستواك، وتذكر مصادرها دائمًا.",
    cours: "التحسين لتعلّم الآلة",
    chapitre: "الفصل 3",
    meta: "FR · 24 شريحة",
    choisir: "اختر شريحة",
    niveau: "مستوى الشرح",
    recherche: "بحث في شرائح الفصل 3",
    tester: "اختبرني في هذه الشريحة",
    essayer: "جرّب مع درسي",
  },
  slides: {
    5: {
      titre: "تدرّج صغير",
      question: "ما هو التدرّج العشوائي؟",
      reponses: {
        debutant: ["بدل حساب الميل على كل البيانات، نحسبه على مثال واحد يُختار عشوائيًا: أسرع بكثير، لكنه مشوَّش قليلًا.", [5]],
        intermediaire: [
          "نستبدل تدرّج الخسارة الكلية بتدرّج مثال $i$ يُختار عشوائيًا: $\\nabla f_i(x)$ مقدِّر غير متحيّز لـ $\\nabla f(x)$، وحسابه أقل كلفة بكثير.",
          [5, 3],
        ],
        avance: [
          "عندما يكون $i$ منتظم التوزيع، يقدّر $\\nabla f_i(x)$ قيمة $\\nabla f(x)$ دون تحيّز بكلفة $O(1)$ بدل $O(n)$، مقابل تباين لا ينعدم عند النقطة الدنيا.",
          [5, 7],
        ],
      },
    },
    7: {
      titre: "لماذا تنجح الطريقة؟",
      question: "لماذا تتذبذب الطريقة حول النقطة الدنيا؟",
      reponses: {
        debutant: ["في قاع الوادي يكون الميل المتوسط صفرًا، لكن كل مثال يشدّ في اتجاهه الخاص: مع خطوات ثابتة الطول نواصل التحرّك قليلًا.", [7]],
        intermediaire: [
          "عند النقطة الدنيا $X^*$ يكون التدرّج الكلي صفرًا، أما التدرّجات المحلية فلا: مع خطوة ثابتة، تحرّك كل خطوة النقطة من جديد.",
          [7, 23],
        ],
        avance: [
          "عند $X^*$ لدينا $\\nabla f(X^*) = 0$، لكن تباين $\\nabla f_i(X^*)$ يبقى موجبًا: مع خطوة ثابتة $\\alpha$ لا يتقارب التكرار إلا نحو جوار لـ $X^*$ حجمه متناسب مع $\\alpha$.",
          [7, 23],
        ],
      },
    },
    23: {
      titre: "خطوة متناقصة",
      question: "لماذا نجعل الخطوة تتناقص؟",
      reponses: {
        debutant: ["خطوات تصغر شيئًا فشيئًا تهدّئ التذبذب: نتقدّم بسرعة في البداية، ثم نستقر بهدوء عند النقطة الدنيا.", [23]],
        intermediaire: ["مع خطوة $\\alpha_k$ متناقصة، مثل $1/k$، يخفت تشويش التدرّجات المحلية ويتقارب التكرار نحو $X^*$.", [23, 7]],
        avance: [
          "نحتاج إلى $\\sum \\alpha_k = \\infty$ لبلوغ $X^*$ وإلى $\\sum \\alpha_k^2 < \\infty$ للتحكّم في التباين: الخطوة $\\alpha_k = 1/k$ تحقّق الشرطين.",
          [23],
        ],
      },
    },
  },
  niveaux: { debutant: "مبتدئ", intermediaire: "متوسط", avance: "متقدم" },
  chiffresAria: "المشروع بالأرقام",
  chiffres: ["درسًا حقيقيًا للاختبار", "سؤالًا مُراجَعًا", "وكلاء متخصّصين", "استدعاء لواجهة برمجة"],
  agents: {
    titre: "ستة وكلاء.",
    accent: "إجابة واحدة، مُتحقَّق منها.",
    texte: "اختر طلبًا: يسلّمه الـ Router إلى الوكيل المناسب، ثم يتحقّق الـ Critic من الإجابة في درسك قبل أن تصلك.",
    demandesAria: "طلبات نموذجية",
    demandesTitre: "طلبك حول الشريحة 7",
    demandes: {
      explainer: "اشرح لي هذه الشريحة",
      qa: "لماذا يجب أن تتناقص الخطوة؟",
      quiz: "اختبرني في هذا الفصل",
      resources: "فيديو للتعمّق أكثر",
      refus: "من اخترع Python؟",
    },
    router: "يقرأ طلبك",
    sous: { explainer: "3 مستويات", qa: "يذكر شرائحه", quiz: "أسئلة وبطاقات", resources: "فهرس محلي" },
    criticRepos: "**Critic** يتحقّق من كل ادعاء في الدرس",
    local: "نموذج لغوي محلي واحد يشغّل الوكلاء الستة: بلا واجهة برمجة، ولا يُرسَل درسك إلى أي مكان.",
    routes: {
      explainer: {
        critic: "Critic: **4 ادعاءات من 4** يدعمها الدرس",
        valide: true,
        titre: "Explainer · المستوى المتوسط",
        texte: "الفكرة الأساسية: مع خطوة ثابتة يتذبذب الانحدار العشوائي حول النقطة الدنيا، لأن التدرّجات المحلية لا تنعدم هناك.",
        sources: [7],
      },
      qa: {
        critic: "Critic: **3 ادعاءات من 3** يدعمها الدرس",
        valide: true,
        titre: "Q&A · إجابة موثّقة",
        texte: "كي يخمد تشويش التدرّجات المحلية: مع خطوة متناقصة يتقارب التكرار نحو $X^*$.",
        sources: [23, 7],
      },
      refus: {
        critic: "Critic: رفض، **لا شيء للتحقّق منه**",
        valide: true,
        titre: "Q&A · خارج الدرس",
        texte: "هذه المعلومة ليست في الدرس. يمكنني أن أشرح لك الانحدار التدرّجي العشوائي، موضوع هذا الفصل.",
        sources: [],
      },
      quiz: {
        critic: "Critic: **3 أسئلة من 3** صالحة، لكل منها إجابة صحيحة واحدة",
        valide: true,
        titre: "Quiz · 3 أسئلة",
        texte: "1. ما قيمة التدرّج الكلي عند النقطة الدنيا $X^*$؟",
        sources: [7],
      },
      resources: {
        critic: "بلا Critic: مصادر من الفهرس المحلي",
        valide: false,
        titre: "Resources · فهرس محلي",
        texte: "مصدران حول «الانحدار التدرّجي العشوائي»: فصل من درس وفيديو، مرتّبان حسب المستوى.",
        sources: [],
      },
    },
  },
  parcours: {
    titre: "أربع خطوات،",
    accent: "ودرس مفهوم.",
    texte: "كل خطوة يتولّاها وكيل متخصّص؛ ويتحقّق الـ Critic من أن كل ما يُقال مصدره شرائحك.",
    aria: "خطوات المسار",
    etapes: [
      ["رفع الدرس بصيغة PPTX أو PDF", "حتى الممسوح ضوئيًا: تُقرأ النصوص والأشكال والمعادلات محليًا."],
      ["شرح لكل شريحة", "انطلاقًا من الشريحة وجاراتها والمفاهيم التي تفترضها."],
      ["أسئلة مع مصادرها", "كل إجابة تذكر شرائحها؛ وخارج الدرس، يقول المعلّم ذلك."],
      ["اختبارات وبطاقات مراجعة", "أسئلة اختيار من متعدد تُصحَّح فورًا، وبطاقات تُقلب."],
    ],
    fichier: "optimisation_ml_ch3.pdf",
    fichierMeta: "24 شريحة · 3,1 ميغابايت · قُرئ على جهازك",
    lu: [
      ["24", "شريحة نصية"],
      ["9", "أشكال موصوفة"],
      ["14", "معادلة مقروءة"],
    ],
    rubriques: [
      { dt: "الفكرة الأساسية", dd: "مع خطوة ثابتة تتذبذب الطريقة حول النقطة الدنيا.", source: 7 },
      { dt: "الشرح", dd: "ينعدم التدرّج الكلي عند $X^*$، أما التدرّجات المحلية فلا." },
      { dt: "مثال", dd: "مثالان يشدّان يسارًا وواحد يمينًا: النقطة ما زالت تتحرّك." },
      { dt: "الصلة بالشريحة 6", dd: "نعود إلى الخطوة الثابتة المعروضة قبلها مباشرة.", source: 6 },
      { dt: "للتذكّر", dd: "خطوة ثابتة = تقارب نحو جوار لـ $X^*$", retenir: true },
    ],
    qa: {
      q1: "لماذا نجعل الخطوة تتناقص؟",
      r1: "مع خطوة متناقصة يخفت تشويش التدرّجات المحلية ويتقارب التكرار نحو $X^*$.",
      s1: [23, 7],
      q2: "ومن اخترع Python؟",
      refus: "هذه المعلومة ليست في الدرس.",
    },
    carte: {
      aria: "بطاقة: انقر لرؤية الجواب",
      recto: "الوجه · الشريحة 23",
      rectoTexte: "ما الشروط على الخطوة $\\alpha_k$؟",
      verso: "الظهر",
      versoTexte: "$\\sum \\alpha_k = \\infty$ و $\\sum \\alpha_k^2 < \\infty$، مثلًا $\\alpha_k = 1/k$.",
      indice: "انقر على البطاقة لقلبها.",
    },
  },
  preuves: {
    titre: "اختُبر على 47 درسًا حقيقيًا.",
    accent: "دورك الآن.",
    texte: "بالفرنسية والإنجليزية، مع 160 سؤال تقييم كتبها الفريق وراجعها. إليك واحدًا منها.",
    qcmTitre: "سؤال من مجموعة التقييم",
    question: "لماذا يتذبذب الانحدار العشوائي ذو الخطوة الثابتة حول النقطة الدنيا؟",
    choix: ["التدرّج الكلي لا ينعدم أبدًا", "عند النقطة الدنيا، التدرّجات المحلية ليست صفرًا", "الخطوة أصغر من أن تتقارب", "دالة الكلفة ليست محدّبة"],
    juste: "صحيح: عند النقطة الدنيا ينعدم التدرّج الكلي، أما التدرّجات المحلية فلا.",
    faux: "ليس تمامًا: عند النقطة الدنيا ينعدم التدرّج الكلي، لكن التدرّجات المحلية لا تنعدم. وهذا ما يجعل الطريقة تتذبذب.",
    verdictJuste: "صحيح",
    verdictFaux: "خطأ",
    reessayer: "أعد المحاولة",
    corpusTitre: "دروس مدوّنة الاختبار",
    corpus: [
      ["تعلّم الآلة والتعلّم العميق", "23 درسًا", 0.489],
      ["رياضيات", "13 درسًا", 0.277],
      ["شبكات", "8 دروس", 0.17],
      ["الحوسبة السحابية وقواعد البيانات", "3 دروس", 0.064],
    ],
    note: "الأشرطة: نصيب كل مجال من الدروس الـ 47.",
  },
  faq: {
    titre: "أسئلة شائعة",
    texte: "أكثر ما يسألنا عنه الطلاب والأساتذة.",
    items: [
      ["هل تغادر دروسي حاسوبي؟", "لا. النموذج اللغوي وقراءة الشرائح والبحث والصوت كلها تعمل محليًا؛ ولا تُستدعى أي خدمة عبر الإنترنت."],
      ["ما الملفات التي يمكنني رفعها؟", "عروض PPTX وملفات PDF، بما فيها الشرائح الممسوحة ضوئيًا: يُقرأ النص حينها بالتعرّف الضوئي."],
      ["بأي لغات يعمل؟", "الواجهة والإجابات متاحة بالفرنسية والإنجليزية والعربية، مع تخطيط من اليمين إلى اليسار للعربية."],
      ["ماذا يحدث إن لم تكن الإجابة في الدرس؟", "يقول المعلّم إن المعلومة ليست في درسك بدل أن يختلقها، ويقترح مفهومًا قريبًا يمكنه شرحه."],
      [
        "كيف نعرف أن الشرح وفيّ للدرس؟",
        "يعيد وكيل Critic قراءة كل إجابة ويتحقّق من أن ادعاءاتها تدعمها الشرائح المذكورة. وإلا تعود الإجابة إلى الوكيل مع التصحيحات، مرتين على الأكثر.",
      ],
    ],
  },
  fin: {
    titre: "راجع درسك القادم",
    surligne: "بطريقة مختلفة.",
    texte: "يكفي ملف PPTX أو PDF: يقرؤه المعلّم على جهازك ويفتح لك الشريحة الأولى. ليس لديك درس الآن؟ يُفتح العرض على درس حقيقي.",
    demo: "شاهد العرض",
  },
  pied: { aria: "تذييل الصفحة", quiz: "صفحة الاختبار", copyright: "© 2026 Multi-Agent Tutor · مشروع فريق Esprit" },
  actionAria: "إجراء سريع",
};

export const TEXTES_ACCUEIL: Record<LangueUI, TextesAccueil> = { fr, en, ar };
