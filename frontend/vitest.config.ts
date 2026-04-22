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
  },
});
