import { defineConfig } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import electron from 'vite-plugin-electron/simple'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    electron({
      main: {
        vite: {
          build: {
            rollupOptions: {
              input: path.join(__dirname, 'electron/main.ts'),
              output: {
                format: 'cjs',
                entryFileNames: '[name].cjs',
                chunkFileNames: '[name].cjs',
              },
            },
          },
        },
      },
      preload: {
        input: path.join(__dirname, 'electron/preload.ts'),
      },
    }),
  ],
})
