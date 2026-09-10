import { ipcRenderer, contextBridge } from 'electron'

const tokenArgument = process.argv.find(argument => argument.startsWith('--pdftranslate-api-token='))
const apiToken = tokenArgument?.slice('--pdftranslate-api-token='.length) ?? ''

contextBridge.exposeInMainWorld('pdftranslate', {
  apiToken,
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
})
