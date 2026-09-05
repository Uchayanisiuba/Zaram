import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const BACKEND = 'http://127.0.0.1:8420';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * The API credential, for development only.
 *
 * The backend refuses callers that cannot present it. In a packaged build the
 * desktop host mints one per launch and hands it to the renderer over IPC, and
 * nothing touches the disk. In a checkout there is no host: the backend and
 * this dev server are two programs a person starts independently, so they meet
 * at a file — `backend/core/api_secret.py` writes it, and this reads it.
 *
 * Deliberately **read, never created.** Whichever side generates it must be
 * the side that enforces it, or a race at first run leaves two different
 * secrets and a 401 that looks like a bug in the credential rather than in the
 * order things were started. Absent simply means the backend has not run yet;
 * start it, restart the dev server.
 *
 * This value only exists while serving. It is not defined for `vite build`, so
 * a development secret can never be baked into a shipped bundle.
 */
function devApiSecret() {
  const explicit = (process.env.ZARAM_API_SECRET || '').trim();
  if (explicit) return explicit;

  // The same resolution `core/paths.py` performs: a checkout that already
  // holds databases keeps its data beside the backend, otherwise the platform
  // location. Both are checked rather than guessed at.
  const candidates = [
    path.resolve(__dirname, '..', 'backend', 'api-secret'),
    process.platform === 'win32'
      ? path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'Zaram', 'api-secret')
      : process.platform === 'darwin'
        ? path.join(os.homedir(), 'Library', 'Application Support', 'Zaram', 'api-secret')
        : path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share'), 'zaram', 'api-secret'),
  ];

  for (const file of candidates) {
    try {
      const value = fs.readFileSync(file, 'utf8').trim();
      if (value) return value;
    } catch {
      /* not there is not an error — the next candidate, or none */
    }
  }
  return '';
}

export default defineConfig(({ command }) => ({
  // Serving only. `vite build` leaves this undefined, so the packaged bundle
  // has no secret in it and falls through to asking the desktop host.
  define: command === 'serve'
    ? { 'import.meta.env.VITE_ZARAM_API_SECRET': JSON.stringify(devApiSecret()) }
    : {},
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
  // Two entry points, not one.
  //
  // `ambient.html` is the overlay Electron summons on a global hotkey. It gets
  // its own entry so it gets its own bundle: the shell's is 550 kB plus a
  // 760 kB VRM chunk, and the overlay's entire claim is that it is the fastest
  // thing on the machine. A route inside the shell would have made the
  // smallest surface pay for the largest one.
  //
  // Declaring `main` explicitly is required — naming any input replaces Vite's
  // default of `index.html` rather than adding to it, so omitting it here
  // would build the overlay and ship no application.
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        ambient: path.resolve(__dirname, 'ambient.html'),
      },
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
      // The session store. Added with the routes rather than after the
      // first syntax-error-at-character-0, which is what a missing prefix
      // produces -- see the note further down.
      '/conversations': { target: BACKEND, changeOrigin: true },
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
      // A prefix missing from this list does not 404 — Vite answers with its
      // own index.html and a 200, so the client parses HTML as JSON and
      // reports a syntax error naming neither the route nor the proxy. That is
      // an hour to diagnose and a one-line fix, which is the worst ratio there
      // is, so `scripts/check-proxy-covers-backend.mjs` now asserts this list
      // against the backend's real route table instead of trusting a comment.
      '/providers': { target: BACKEND, changeOrigin: true },
      '/routing': { target: BACKEND, changeOrigin: true },
      '/search': { target: BACKEND, changeOrigin: true },
      // `/vision` was here because `POST /vision/analyze` existed. It was
      // deleted on 28 August 2026 — an entrance to inference that skipped
      // routing and the egress gate — so the prefix goes with it. Images now
      // travel on `/chat` like any other part of a message.
      '/export': { target: BACKEND, changeOrigin: true },
      '/character': { target: BACKEND, changeOrigin: true },
      // The obligations routes landed with the backend on 26 August and
      // neither proxy list was updated, so the check below had been
      // failing since. Read the guard's output rather than adding a
      // prefix here from memory — it names both lists.
      '/obligations': { target: BACKEND, changeOrigin: true },
    },
  },
}));