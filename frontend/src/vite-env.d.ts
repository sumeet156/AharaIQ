/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OCR_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
