/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_COURS_PAR_DEFAUT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
