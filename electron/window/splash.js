'use strict';

const path = require('path');
const { BrowserWindow } = require('electron');

/**
 * Standalone splash window. Sandboxed, no Node access, no preload — it only
 * renders a static placeholder while the backend boots.
 */
function createSplashWindow(config) {
  const w = new BrowserWindow({
    width: config.window.splashWidth,
    height: config.window.splashHeight,
    frame: false,
    alwaysOnTop: true,
    center: true,
    resizable: false,
    backgroundColor: '#0b0b14',
    webPreferences: {
      sandbox: true,
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  w.loadFile(path.join(__dirname, '..', 'assets', 'splash.html'));
  return w;
}

module.exports = { createSplashWindow };
