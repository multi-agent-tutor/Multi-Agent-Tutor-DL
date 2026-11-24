// Barre du haut de l'outil (maquettes D2 depot.html, cours.html, quiz.html) : marque vers l'accueil,
// cours actuel, onglets Déposer / Cours / Quiz, sélecteur de langue.
import { useLangue } from "../i18n";
import type { Course, LangueUI } from "../types";
import { Icone } from "./Icones";

export type Page = "accueil" | "depot" | "cours" | "quiz";
export type PageOutil = Exclude<Page, "accueil">;

interface Props {
  cours: Course | null;
  page: PageOutil;
  surPage: (p: PageOutil) => void;
}

const ONGLETS: PageOutil[] = ["depot", "cours", "quiz"];

export function SelecteurLangue() {
  const { t, langue, setLangue } = useLangue();
  return (
    <div className="langues" role="group" aria-label={t("langue")}>
      {(["fr", "en", "ar"] as LangueUI[]).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={langue === l}
          aria-label={l === "ar" ? "العربية" : undefined}
          lang={l}
          onClick={() => setLangue(l)}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export function Barre({ cours, page, surPage }: Props) {
  const { t } = useLangue();
  return (
    <header className="barre">
      <a className="marque" href="#accueil" aria-label={t("marque-accueil")}>
        <img src="/img/logo-icone.png" alt="" width={44} height={44} />
        <span className="marque-nom">
          Multi-Agent <b>Tutor</b>
        </span>
      </a>
      {cours && page !== "depot" && (
        <div className="cours-actuel">
          <Icone nom="livre" />
          <strong title={cours.fichier_source} dir="auto">
            {cours.titre}
          </strong>
        </div>
      )}
      <nav className="onglets" aria-label={t("sections")}>
        {ONGLETS.map((p) => (
          <a
            key={p}
            href={`#${p}`}
            aria-current={page === p ? "page" : undefined}
            onClick={(e) => {
              e.preventDefault();
              surPage(p);
            }}
          >
            <Icone nom={p} />
            <span>{t(p)}</span>
          </a>
        ))}
      </nav>
      <SelecteurLangue />
    </header>
  );
}
