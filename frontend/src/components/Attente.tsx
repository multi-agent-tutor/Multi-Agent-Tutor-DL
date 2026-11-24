// Indicateur de génération : le LLM local est lent (30 à 120 s), on montre le temps écoulé.
import { useEffect, useState } from "react";
import { useLangue } from "../i18n";

export function Attente({ libelle, surAnnuler }: { libelle?: string; surAnnuler?: () => void }) {
  const { t } = useLangue();
  const [secondes, setSecondes] = useState(0);
  useEffect(() => {
    const debut = Date.now();
    const id = setInterval(() => setSecondes(Math.floor((Date.now() - debut) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="attente" role="status">
      <span className="attente-points" aria-hidden="true"><i /><i /><i /></span>
      <span>
        {libelle ?? t("reflechit")} <b className="attente-temps">{secondes} s</b>
        {secondes >= 15 && <small>{t("lent")}</small>}
      </span>
      {surAnnuler && (
        <button type="button" className="bouton discret attente-annuler" onClick={surAnnuler}>
          {t("annuler")}
        </button>
      )}
    </div>
  );
}

export function Erreur({ message, surReessayer }: { message: string; surReessayer?: () => void }) {
  const { t } = useLangue();
  return (
    <div className="erreur" role="alert">
      <span>{message}</span>
      {surReessayer && (
        <button type="button" className="bouton" onClick={surReessayer}>
          {t("reessayer")}
        </button>
      )}
    </div>
  );
}
