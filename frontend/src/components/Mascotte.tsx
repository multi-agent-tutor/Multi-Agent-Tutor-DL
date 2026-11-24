// La mascotte du logo (D2), redessinée en SVG pour changer d'état :
// "" sourit, "reflechit" un agent génère, "contente" bonne réponse, "oups" erreur ou refus.
import type { CSSProperties } from "react";

export type EtatMascotte = "" | "reflechit" | "contente" | "oups";

export function Mascotte({ etat = "", taille, style }: { etat?: EtatMascotte; taille?: number; style?: CSSProperties }) {
  const dims = taille ? { width: taille, height: taille } : {};
  return (
    <svg className="mascotte" viewBox="0 0 100 100" aria-hidden="true" focusable="false" data-etat={etat} style={{ ...dims, ...style }}>
      <g className="eclats">
        <path d="M10 30 L4 26" />
        <path d="M14 22 L11 15" />
        <path d="M8 40 L1 40" />
      </g>
      <g className="tete">
        <rect className="contour" x="12" y="49" width="9" height="17" rx="4.5" fill="#fff" />
        <rect className="contour" x="79" y="49" width="9" height="17" rx="4.5" fill="#fff" />
        <rect className="contour" x="19" y="33" width="62" height="52" rx="25" fill="#fff" />
        <rect x="27" y="45" width="46" height="26" rx="12" fill="#0B1A45" />
        <g className="yeux yeux-arcs" fill="none" stroke="#4C8AFD" strokeWidth="4" strokeLinecap="round">
          <path d="M36 61 q5.5 -8 11 0" />
          <path d="M53 61 q5.5 -8 11 0" />
        </g>
        <g className="yeux yeux-points" fill="#4C8AFD">
          <circle cx="40" cy="58" r="3.4" />
          <circle cx="50" cy="58" r="3.4" />
          <circle cx="60" cy="58" r="3.4" />
        </g>
        <g className="yeux yeux-oups" fill="none" stroke="#4C8AFD" strokeWidth="4" strokeLinecap="round">
          <path d="M36 58 h11" />
          <path d="M53 58 h11" />
        </g>
        <path className="contour" d="M18 21 L52 9 L86 21 L52 33 Z" fill="#2563EB" />
        <path className="contour" d="M33 27 V35 H71 V27" fill="#1D4ED8" />
        <path d="M82 22 V37" stroke="#FBBF24" strokeWidth="3" strokeLinecap="round" />
        <rect x="78.5" y="35" width="7" height="10" rx="3" fill="#FBBF24" stroke="#0B1A45" strokeWidth="2" />
      </g>
    </svg>
  );
}
