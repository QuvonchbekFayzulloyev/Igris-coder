/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_IGRIS_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
