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
  const backendPort = o.backendPort || 8000;
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
      apiProxyPrefixes: [
        '/api',
        '/chat',
        '/personalities',
        '/audio',
        '/models',
        '/garage',
        '/knowledge',
        '/voice',
        '/health',
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
