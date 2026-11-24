// « Cours déjà déposés » (page Dépôt) : les derniers cours ouverts, gardés dans le navigateur.
import type { Course, Langue } from "./types";

export interface CoursRecent {
  id: string;
  titre: string;
  format: "pdf" | "pptx";
  nombre_slides: number;
  langue: Langue;
}

const CLE = "mat-cours-recents";
const MAX = 6;

export function lireRecents(): CoursRecent[] {
  try {
    const liste = JSON.parse(localStorage.getItem(CLE) ?? "[]");
    return Array.isArray(liste) ? liste.filter((c) => typeof c?.id === "string") : [];
  } catch {
    return [];
  }
}

export function ajouterRecent(c: Course): CoursRecent[] {
  const entree: CoursRecent = { id: c.id, titre: c.titre, format: c.format, nombre_slides: c.nombre_slides, langue: c.langue };
  const liste = [entree, ...lireRecents().filter((r) => r.id !== c.id)].slice(0, MAX);
  try {
    localStorage.setItem(CLE, JSON.stringify(liste));
  } catch {
    /* stockage plein ou bloqué : la liste reste en mémoire pour cette session */
  }
  return liste;
}

export function retirerRecent(id: string): CoursRecent[] {
  const liste = lireRecents().filter((r) => r.id !== id);
  try {
    localStorage.setItem(CLE, JSON.stringify(liste));
  } catch {
    /* idem */
  }
  return liste;
}
