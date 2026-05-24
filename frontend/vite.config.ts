import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Reminds the developer that `npm run dev:dev-auth-on` only flips the FRONTEND
// into public/auth mode — the backend must ALSO be started with
// NOVOTREE_APP_MODE=public, otherwise /auth/me still returns the dev owner and
// the login screen never appears.
const devAuthOnReminderPlugin = (mode: string) => ({
  name: 'dev-auth-on-reminder',
  configureServer() {
    if (mode !== 'dev-auth-on') return;
    const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
    const bold = (s: string) => `\x1b[1m${s}\x1b[0m`;
    console.log('');
    console.log(yellow(bold('  ⚠  dev-auth-on: frontend is in PUBLIC mode.')));
    console.log(yellow('     To actually see the login screen, the BACKEND must also run with'));
    console.log(yellow('     NOVOTREE_APP_MODE=public  (otherwise /auth/me returns the dev owner'));
    console.log(yellow('     and you stay auto-authenticated). Also clear any stale access_token'));
    console.log(yellow('     cookie for localhost:3000 in your browser.'));
    console.log('');
  },
});

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), devAuthOnReminderPlugin(mode)],
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
}))
