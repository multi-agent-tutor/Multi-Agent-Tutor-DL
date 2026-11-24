// Pictogrammes au trait des maquettes D2 (sprite SVG inséré une fois dans la page).
const SYMBOLES: Record<string, string> = {
  livre: '<path d="M3 5.5C5.5 4 8.5 4 12 6c3.5-2 6.5-2 9-.5V19c-2.5-1.5-5.5-1.5-9 .5-3.5-2-6.5-2-9-.5z"/><path d="M12 6v13.5"/>',
  cours: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14"/><path d="M12 17h.01"/>',
  gauche: '<path d="M15 6l-6 6 6 6"/>',
  droite: '<path d="M9 6l6 6-6 6"/>',
  etoile: '<path d="M12 3l2.4 5.6 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>',
  bouclier: '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
  son: '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  monde: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  bulle: '<path d="M4 5h16v11H9l-5 4z"/>',
  envoyer: '<path d="M4 12l16-8-6 16-3-7z"/>',
  ok: '<path d="M6 12.5l4 4L18 8"/>',
  ko: '<path d="M7 7l10 10M17 7L7 17"/>',
  recommencer: '<path d="M4 12a8 8 0 1 0 2.5-5.8"/><path d="M4 4v4h4"/>',
  export: '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/>',
  cartes: '<rect x="3" y="6" width="14" height="14" rx="2"/><path d="M7 3h12a2 2 0 0 1 2 2v12"/>',
  niveau: '<path d="M3 20h5v-5h5v-5h5V5h3"/>',
  depot: '<path d="M12 15V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  importer: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  alerte: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16h.01"/>',
  ecran: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  lien: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
};

export type NomIcone = keyof typeof SYMBOLES;

export function SpriteIcones() {
  const contenu = Object.entries(SYMBOLES)
    .map(([nom, d]) => `<symbol id="i-${nom}" viewBox="0 0 24 24">${d}</symbol>`)
    .join("");
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true" dangerouslySetInnerHTML={{ __html: contenu }} />
  );
}

export function Icone({ nom, miroir, label }: { nom: NomIcone; miroir?: boolean; label?: string }) {
  return (
    <svg className={miroir ? "icone miroir" : "icone"} aria-hidden={label ? undefined : true} aria-label={label} role={label ? "img" : undefined}>
      <use href={`#i-${nom}`} />
    </svg>
  );
}
