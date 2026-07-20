import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const BACKEND = 'http://127.0.0.1:8000'
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Same-origin proxy so the renderer never crosses origins to reach the backend.
// The Electron production build mirrors this with its own static-server proxy.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Project source alias used throughout the frontend.
      '@': path.resolve(__dirname, 'src')
      // The Living Orb Engine is consumed as an external black-box dependency.
      // The renderer is implemented in the frontend and consumes FrameState over IPC.
    }
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
      '/artifacts': { target: BACKEND, changeOrigin: true },
    },
  },
})
