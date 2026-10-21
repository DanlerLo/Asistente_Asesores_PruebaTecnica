/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const raizRepo = fileURLToPath(new URL('../..', import.meta.url));
const raizTests = fileURLToPath(new URL('../../tests/frontend', import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Las pruebas viven en tests/frontend (fuera de esta carpeta): se permite servirlas.
    fs: { allow: [raizRepo] },
    // En desarrollo, /api se reenvía al backend: no hace falta configurar CORS ni URLs.
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    dir: raizTests,
    include: ['**/*.test.{ts,tsx}'],
  },
});
