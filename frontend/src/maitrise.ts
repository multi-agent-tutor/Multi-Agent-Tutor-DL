// Bande des slides : état de maîtrise de chaque slide, gardé dans le navigateur.
// vue = slide affichée · comprise = explication lue · testee = question de quiz répondue.
import { useCallback, useEffect, useState } from "react";

export type EtatMaitrise = "vue" | "comprise" | "testee";
export type Maitrise = Record<number, EtatMaitrise>;

const RANG: Record<EtatMaitrise, number> = { vue: 1, comprise: 2, testee: 3 };
const cle = (courseId: string) => `mat-maitrise-${courseId}`;

function lire(courseId: string | null): Maitrise {
  if (!courseId) return {};
  try {
    return JSON.parse(localStorage.getItem(cle(courseId)) ?? "{}") as Maitrise;
  } catch {
    return {};
  }
}

export function useMaitrise(courseId: string | null) {
  const [maitrise, setMaitrise] = useState<Maitrise>(() => lire(courseId));
  useEffect(() => setMaitrise(lire(courseId)), [courseId]);

  /** Monter une slide à un état (jamais redescendre : testée reste testée). */
  const marquer = useCallback(
    (numero: number, etat: EtatMaitrise) => {
      if (!courseId) return;
      setMaitrise((m) => {
        const actuel = m[numero];
        if (actuel && RANG[actuel] >= RANG[etat]) return m;
        const suivant = { ...m, [numero]: etat };
        localStorage.setItem(cle(courseId), JSON.stringify(suivant));
        return suivant;
      });
    },
    [courseId],
  );
  return { maitrise, marquer };
}
