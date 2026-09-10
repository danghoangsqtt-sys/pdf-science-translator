export interface PDFTranslateBridge {
  apiToken: string;
  openExternal: (url: string) => Promise<void>;
}

declare global {
  interface Window {
    pdftranslate?: PDFTranslateBridge;
  }
}
