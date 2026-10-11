import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In production FastAPI serves the built SPA at the site root; in dev the
// Vite server proxies the API to the backend.
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: { outDir: 'dist' },
})
