import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'serve' ? '/' : '/admin/',
  build: {
    outDir: resolve(__dirname, '../api/public/admin'),
    emptyOutDir: true,
  },
}))
