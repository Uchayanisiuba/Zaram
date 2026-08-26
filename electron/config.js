'use strict';

const path = require('path');

/**
 * Builds the desktop application configuration.
 *
 * Kept free of any `electron` import so it can be unit tested in plain Node.
 * The Electron main process injects the runtime values (appPath, userDataPath,
 * resourcesPath, isDev) when it boots.
 *
 * @param {object} [options]
 * @param {boolean} [options.isDev]
 * @param {string}  [options.appPath]
 * @param {string}  [options.userDataPath]
 * @param {string}  [options.resourcesPath]
 * @param {number}  [options.backendPort]
 * @param {number}  [options.rendererDevPort]
 * @param {number}  [options.staticPort]
 * @returns {import('./types').DesktopConfig}
 */
function createConfig(options) {
  const o = options || {};
  const isDev = o.isDev === true;
  const appPath = o.appPath || process.cwd();
  const backendPort = o.backendPort || 8420;
  const rendererDevPort = o.rendererDevPort || 5173;
  const staticPort = o.staticPort || 5180;

  const userDataPath = o.userDataPath || path.join(appPath, 'userdata');
  const frontendDist = path.join(appPath, 'frontend', 'dist');

  return {
    isDev,
    appPath,
    resourcesPath: o.resourcesPath || appPath,
    userDataPath,
    logsPath: path.join(userDataPath, 'logs'),
    settingsPath: path.join(userDataPath, 'settings.json'),
    windowStatePath: path.join(userDataPath, 'window-state.json'),
    backend: {
      baseUrl: `http://127.0.0.1:${backendPort}`,
      port: backendPort,
      healthPath: '/health',
      startupTimeoutMs: 30000,
      pollIntervalMs: 2000,
      restartDelayMs: 3000,
    },
    renderer: {
      devUrl: `http://localhost:${rendererDevPort}`,
      prodUrl: `http://127.0.0.1:${staticPort}`,
      url: isDev ? `http://localhost:${rendererDevPort}` : `http://127.0.0.1:${staticPort}`,
      staticDir: frontendDist,
      staticPort,
      // Every backend prefix the packaged origin must forward to 8420.
      //
      // **This list is not a convenience, it is the packaged product's routing
      // table**, and it was missing eleven prefixes. `createStaticServer`
      // serves anything it does not recognise from `frontend/dist`, so a
      // forgotten prefix does not 404 — it answers **200 with index.html**, and
      // the client hands HTML to `response.json()`. Measured against the built
      // app: `/health` and `/chat` returned 502 with no backend running, which
      // is a proxy working; `/egress`, `/artifacts`, `/providers`, `/export`,
      // `/character`, `/routing/preference` and `/projects` all returned 200
      // and a document. The egress log and the exporter — rules 3 and 7 — were
      // unreachable in every packaged build, and only in packaged builds.
      //
      // The dev proxy in `frontend/vite.config.js` had all of them, which is
      // why nobody saw it: development is the environment that does not use
      // this list. `check-proxy-covers-backend.mjs` now checks both, and its
      // own header used to reason that "the packaged build does not use the
      // proxy at all" — the premise, not the code, is what was wrong.
      //
      // Add a prefix here whenever one is added to the backend. The guard
      // fails the build if this drifts, so the list stays explicit rather than
      // derived: an allow-list nobody can quietly widen is the same reason
      // `electron-builder.yml` names what it ships.
      apiProxyPrefixes: [
        '/api',
        '/artifacts',
        '/audio',
        '/character',
        '/chat',
        '/egress',
        '/export',
        '/garage',
        '/health',
        '/ingest',
        '/knowledge',
        '/memory',
        '/models',
        '/obligations',
        '/personalities',
        '/projects',
        '/providers',
        '/readiness',
        '/routing',
        '/search',
        '/vision',
        '/voice',
      ],
    },
    window: {
      minWidth: 1024,
      minHeight: 700,
      defaultWidth: 1280,
      defaultHeight: 800,
      splashWidth: 480,
      splashHeight: 300,
    },
  };
}

module.exports = { createConfig };
