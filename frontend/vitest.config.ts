import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate Vitest config so 'vite build' is unaffected.
// Test files live inside frontend/ so they're within Vite's root.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['./tests/frontend/**/*.test.{ts,tsx}'],
    // NODE_ENV must be 'test' (not the default 'production') so React and react-dom/test-utils
    // load their development builds, which export React.act required by
    // @testing-library/react with React 19.
    // NODE_ENV is used by 'npm test' and it has no impact on deployment scripts.
    // VITE_NOVOTREE_APP_MODE='public' ensures the viewer auth flow
    // (getShareInfo → viewerOwnerId) is exercised, matching production.
    env: { NODE_ENV: 'test', VITE_NOVOTREE_APP_MODE: 'public' },
  },
});
