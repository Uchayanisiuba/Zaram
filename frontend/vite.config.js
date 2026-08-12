import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const BACKEND = 'http://127.0.0.1:8420';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    force: true,
    exclude: ['@react-three/postprocessing', 'lucide-react'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    // Fail rather than drift. Electron's dev window loads localhost:5173 as a
    // literal, so when this port is busy Vite's default behaviour — quietly
    // moving to 5174 — produces an app window that fails to load with nothing
    // on screen and only `ERR_FAILED (-2)` in a log nobody is reading. The
    // usual cause is a previous dev server that outlived its terminal, so it
    // happens exactly when someone is already debugging something else.
    //
    // strictPort turns that into an immediate, named failure: "Port 5173 is
    // already in use", before Electron ever opens a window.
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/chat': { target: BACKEND, changeOrigin: true },
      '/personalities': { target: BACKEND, changeOrigin: true },
      '/audio': { target: BACKEND, changeOrigin: true },
      '/models': { target: BACKEND, changeOrigin: true },
      '/garage': { target: BACKEND, changeOrigin: true },
      '/knowledge': { target: BACKEND, changeOrigin: true },
      '/voice': { target: BACKEND, changeOrigin: true },
      '/health': { target: BACKEND, changeOrigin: true },
      '/readiness': { target: BACKEND, changeOrigin: true },
      '/memory': { target: BACKEND, changeOrigin: true },
      '/egress': { target: BACKEND, changeOrigin: true },
      '/artifacts': { target: BACKEND, changeOrigin: true },
      '/projects': { target: BACKEND, changeOrigin: true },
      '/ingest': { target: BACKEND, changeOrigin: true },
    },
  },
});