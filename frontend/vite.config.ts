import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// API_TARGET: in docker compose l'API è il servizio `api`. VITE_POLLING=1: nei container su Windows
// gli eventi del filesystem non arrivano, quindi Vite deve controllare i file a intervalli.
// In dev il frontend chiama /api/...: Vite lo inoltra all'API togliendo il prefisso,
// così il browser vede un solo origin (niente CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    watch: { usePolling: process.env.VITE_POLLING === '1' },
    proxy: {
      '/api': {
        target: process.env.API_TARGET ?? 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    pool: 'threads',
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
