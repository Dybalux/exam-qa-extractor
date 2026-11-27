import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In production FastAPI serves the built SPA at the site root; in dev the
// Vite server proxies the API to the backend.
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // Preserve the browser's Host header (e.g. localhost:5173) so FastAPI's
        // CSRF middleware sees Origin matching Host instead of a rewritten
        // 127.0.0.1:8000 Host header (Vite defaults string proxies to changeOrigin: true).
        changeOrigin: false,
      },
    },
  },
  build: { outDir: 'dist' },
})
