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
      '/memory': { target: BACKEND, changeOrigin: true },
      '/egress': { target: BACKEND, changeOrigin: true },
      '/artifacts': { target: BACKEND, changeOrigin: true },
      '/ingest': { target: BACKEND, changeOrigin: true },
    },
  },
});