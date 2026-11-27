import "katex/dist/katex.min.css"; // KaTeX et ses polices, servis par Vite (aucun CDN)
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { FournisseurLangue } from "./i18n";
import "./styles/maquettes.css";
import "./styles/app.css";
import "./styles/depot.css";
import "./styles/accueil.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <FournisseurLangue>
      <App />
    </FournisseurLangue>
  </StrictMode>,
);
