import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // "base" tells Vite what URL prefix the app is served under.
  // Vite embeds this prefix into all generated asset URLs (JS, CSS, images),
  // so the browser can find them. Without the correct prefix, the browser
  // requests /assets/... but the server only knows /novotree/assets/..., causing 404s.
  // VITE_BASE_PATH is injected at build time by vm-setup.py, which knows the
  // deployment path. Defaults to '/' for local dev (npm run dev).
  base: process.env.VITE_BASE_PATH ?? '/',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
