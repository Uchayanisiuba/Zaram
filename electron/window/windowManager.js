'use strict';

const path = require('path');
const { BrowserWindow } = require('electron');
const { createSplashWindow } = require('./splash');
const windowState = require('./windowState');

/**
 * Owns the main BrowserWindow plus the splash window and the friendly error
 * state. The main window is reused for both the application and the error
 * screen (loaded via loadFile) so no React changes are required.
 */
class WindowManager {
  constructor({ config, logger }) {
    this.config = config;
    this.logger = logger || console;
    this.mainWindow = null;
    this.splashWindow = null;
    this.state = windowState.loadState(config.windowStatePath, config);
    this._preload = path.join(__dirname, '..', 'preload.js');
    this._assets = path.join(__dirname, '..', 'assets');
  }

  getMainWindow() {
    return this.mainWindow;
  }

  createSplash() {
    this.splashWindow = createSplashWindow(this.config);
    return this.splashWindow;
  }

  closeSplash() {
    if (this.splashWindow && !this.splashWindow.isDestroyed()) {
      this.splashWindow.close();
    }
    this.splashWindow = null;
  }

  createMainWindow() {
    const cfg = this.config.window;
    const bounds = this._boundsFromState();
    const win = new BrowserWindow({
      width: bounds.width,
      height: bounds.height,
      x: bounds.x,
      y: bounds.y,
      minWidth: cfg.minWidth,
      minHeight: cfg.minHeight,
      show: false,
      backgroundColor: '#0b0b14',
      autoHideMenuBar: true,
      webPreferences: {
        preload: this._preload,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
        webSecurity: true,
      },
    });
    this.mainWindow = win;
    this._trackState(win);
    win.on('closed', () => {
      if (this.mainWindow === win) this.mainWindow = null;
    });
    return win;
  }

  _boundsFromState() {
    const s = this.state;
    const b = { width: s.width, height: s.height };
    if (typeof s.x === 'number' && typeof s.y === 'number') {
      b.x = s.x;
      b.y = s.y;
    }
    return b;
  }

  _trackState(win) {
    const save = () => {
      try {
        const b = win.getBounds();
        this.state.width = b.width;
        this.state.height = b.height;
        this.state.x = b.x;
        this.state.y = b.y;
        this.state.maximized = win.isMaximized();
        windowState.saveState(this.config.windowStatePath, this.config, this.state);
      } catch (err) {
        // never block shutdown on a state write failure
      }
    };
    win.on('resize', save);
    win.on('move', save);
    win.on('close', save);
  }

  showMainWindow() {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      if (this.state.maximized) this.mainWindow.maximize();
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  loadApp() {
    if (!this.mainWindow) this.createMainWindow();
    const url = this.config.renderer.url;
    // Named, and its failure reported. `loadURL` returns a promise that
    // rejects when the page cannot be reached; nothing was awaiting it, so a
    // renderer that failed to load produced an empty window in silence — and
    // in dev the URL is a dev server that may not be listening, which is the
    // likeliest single cause of exactly that.
    const done = this.mainWindow.loadURL(url);
    if (done && typeof done.catch === 'function') {
      done.catch((err) => {
        if (this.logger && this.logger.error) {
          this.logger.error('Renderer failed to load', { url, error: err && err.message });
        }
      });
    }
    if (this.logger && this.logger.info) this.logger.info('Loading renderer', { url });
  }

  loadError(info) {
    if (!this.mainWindow) this.createMainWindow();
    const reason = info && info.error ? String(info.error).slice(0, 300) : '';
    this.mainWindow.loadFile(path.join(this._assets, 'error.html'), {
      query: { reason },
    });
    this.showMainWindow();
  }

  destroy() {
    this.closeSplash();
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.destroy();
    }
    this.mainWindow = null;
  }
}

module.exports = { WindowManager };
