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
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-tree': ['@xyflow/react', 'html-to-image'],
          'vendor-forms': ['react-hook-form', 'zod', '@hookform/resolvers'],
          'vendor-ui': ['framer-motion', 'lucide-react', 'date-fns'],
        },
      },
    },
  },
  server: {
    // Bind to 0.0.0.0 so the dev server is reachable from other devices on the
    // LAN (e.g. a phone on the same Wi-Fi hitting http://<laptop-ip>:3000).
    // Without this Vite listens on 127.0.0.1 only and the phone gets
    // "connection refused". Used for mobile-layout testing on real devices.
    host: true,
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
