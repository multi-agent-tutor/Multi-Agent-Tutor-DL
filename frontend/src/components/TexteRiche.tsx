// Texte d'un agent : formules LaTeX (KaTeX, installé en local) et citations [Slide N] cliquables.
import katex from "katex";
import { Fragment, type ReactNode } from "react";

// $$…$$, \[…\], $…$, \(…\) puis [Slide N] / [Slides N, M] / [Slide N-M]
const MOTIF =
  /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)|\[(?:Slides?|Diapo(?:sitive)?s?|شريحة)\s*([\d\s,–-]+)\]/gi;

export function Formule({ latex, bloc = false }: { latex: string; bloc?: boolean }) {
  const html = katex.renderToString(latex, { displayMode: bloc, throwOnError: false, output: "htmlAndMathml" });
  return <span className={bloc ? "katex-bloc" : undefined} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Numéros cités dans « 3, 5 » ou « 3-5 ». */
export function numerosCites(liste: string): number[] {
  const numeros: number[] = [];
  for (const morceau of liste.split(",")) {
    const [a, b] = morceau.split(/[–-]/).map((x) => parseInt(x.trim(), 10));
    if (Number.isNaN(a)) continue;
    if (!Number.isNaN(b) && b >= a && b - a < 50) for (let n = a; n <= b; n++) numeros.push(n);
    else numeros.push(a);
  }
  return numeros;
}

export function Citation({ numero, surCitation }: { numero: number; surCitation?: (n: number) => void }) {
  return (
    <button type="button" className="source" onClick={() => surCitation?.(numero)}>
      Slide {numero}
    </button>
  );
}

/** Rendu d'une ligne de texte (sans paragraphes). */
export function TexteEnLigne({ texte, surCitation }: { texte: string; surCitation?: (n: number) => void }) {
  const morceaux: ReactNode[] = [];
  let dernier = 0;
  let cle = 0;
  for (const m of texte.matchAll(MOTIF)) {
    if (m.index > dernier) morceaux.push(texte.slice(dernier, m.index));
    const [, bloc1, bloc2, enLigne1, enLigne2, slides] = m;
    if (slides !== undefined) {
      morceaux.push(
        <Fragment key={cle++}>
          {numerosCites(slides).map((n) => (
            <Citation key={n} numero={n} surCitation={surCitation} />
          ))}
        </Fragment>,
      );
    } else {
      const latex = bloc1 ?? bloc2 ?? enLigne1 ?? enLigne2 ?? "";
      morceaux.push(<Formule key={cle++} latex={latex} bloc={bloc1 !== undefined || bloc2 !== undefined} />);
    }
    dernier = m.index + m[0].length;
  }
  if (dernier < texte.length) morceaux.push(texte.slice(dernier));
  return <>{morceaux}</>;
}

/** Découper un texte en paragraphes (lignes vides) ; les lignes « - » ou « • » deviennent une liste. */
export function TexteRiche({
  texte,
  surCitation,
  classeParagraphe,
}: {
  texte: string;
  surCitation?: (n: number) => void;
  classeParagraphe?: string;
}) {
  const paragraphes = texte.split(/\n\s*\n/).filter((p) => p.trim());
  return (
    <>
      {paragraphes.map((p, i) => {
        const lignes = p.split("\n").filter((l) => l.trim());
        const puces = lignes.length > 0 && lignes.every((l) => /^\s*[-•*]\s+/.test(l));
        if (puces)
          return (
            <ul key={i} dir="auto">
              {lignes.map((l, j) => (
                <li key={j}>
                  <TexteEnLigne texte={l.replace(/^\s*[-•*]\s+/, "")} surCitation={surCitation} />
                </li>
              ))}
            </ul>
          );
        return (
          <p key={i} className={classeParagraphe} dir="auto">
            <TexteEnLigne texte={lignes.join(" ")} surCitation={surCitation} />
          </p>
        );
      })}
    </>
  );
}
