import { ipcRenderer, contextBridge } from 'electron'

const tokenArgument = process.argv.find(argument => argument.startsWith('--pdftranslate-api-token='))
const apiToken = tokenArgument?.slice('--pdftranslate-api-token='.length) ?? ''

contextBridge.exposeInMainWorld('pdftranslate', {
  apiToken,
  apiBaseUrl: process.argv.find(argument => argument.startsWith('--pdftranslate-api-base='))?.slice('--pdftranslate-api-base='.length) || 'http://127.0.0.1:8089/api',
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
})
