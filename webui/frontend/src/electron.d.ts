export interface PDFTranslateBridge {
  apiToken: string;
  apiBaseUrl: string;
  openExternal: (url: string) => Promise<void>;
}

declare global {
  interface Window {
    pdftranslate?: PDFTranslateBridge;
  }
}
