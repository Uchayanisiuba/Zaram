'use strict';

const path = require('path');
const fs = require('fs');
const { app, ipcMain } = require('electron');

const { createConfig } = require('./config');
const { createLogger } = require('./logger');
const { MAIN_EVENTS } = require('./ipc/channels');
const { registerHandlers } = require('./ipc/handlers');
const { WindowManager } = require('./window/windowManager');
const { BackendLauncher } = require('./backend/backendLauncher');
const { createServices } = require('./services/index');
const { createStaticServer } = require('./staticServer');
const { createTray } = require('./native/tray');
const { createAutoUpdater } = require('./native/autoUpdater');
const { createFileAssociations } = require('./native/fileAssociations');
const { createDeepLinks } = require('./native/deepLinks');
const { createGlobalShortcuts } = require('./native/globalShortcuts');
const { createAmbientSurface } = require('./native/ambient');

const isDev = !app.isPackaged;

// config + logger are created inside bootstrap() once `app` is ready, because
// app.getPath()/app.getVersion() must not be called before the ready event.
let config = null;
let logger = null;

// --- Single instance lock ---
if (!app.requestSingleInstanceLock()) {
  app.quit();
  return;
}

let windows = null;
let backend = null;
let services = null;
let staticServer = null;
let tray = null;
let shortcuts = null;
let ambient = null;
let updater = null;
let logStream = null;
let appLoaded = false;
let quitting = false;

function pushToRenderer(channel, payload) {
  const w = windows && windows.getMainWindow();
  if (w && !w.isDestroyed()) {
    try {
      w.webContents.send(channel, payload);
    } catch (_) {
      /* window may be mid-load */
    }
  }
}

function hardenWindow(win) {
  // Prevent the renderer from opening new windows / navigating off-app.
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (event, url) => {
    if (url !== config.renderer.url && !url.startsWith('file://')) {
      event.preventDefault();
    }
  });
}

let desktopRuntime = null;

function loadDesktopRuntime() {
  try {
    const appPath = config ? config.appPath : process.cwd();
    const resourcesPath = config ? config.resourcesPath : process.resourcesPath;
    const desktopPaths = [
      // Dev: desktop runtime built to <repo>/desktop/dist/src/runtime/bootstrap
      path.join(__dirname, '..', 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
      path.join(appPath, 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
      path.join(resourcesPath, 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
      path.join(__dirname, '..', '..', 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
      // Packaged: resources/desktop/dist/desktop/src/runtime/bootstrap
      path.join(resourcesPath, 'app.asar.unpacked', 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
      path.join(process.resourcesPath, 'desktop', 'dist', 'src', 'runtime', 'bootstrap'),
    ];
    for (const p of desktopPaths) {
      try {
        const mod = require(p);
        if (mod && mod.bootstrapPresence) {
          const backendUrl = config.backend.baseUrl
          console.log('[Electron] Loading desktop runtime from:', p)
          console.log('[Electron] Passing backendUrl:', backendUrl)
          desktopRuntime = mod.bootstrapPresence({ backendUrl })
          logger.info('Desktop runtime loaded', { path: p, backendUrl });
          return true;
        }
      } catch (e) {
        // try next path
      }
    }
    logger.warn('Desktop runtime not found at expected paths');
    return false;
  } catch (error) {
    logger.warn('Failed to load desktop runtime', { error: error.message });
    return false;
  }
}

function detectZaramWorkspace(appPath) {
  // Phase 2: prefer the canonical C:\Zaram workspace, then fall back to the
  // project root that contains the backend package.
  const candidates = [
    'C:\\Zaram',
    path.join(appPath || '', '..', '..'),
    appPath,
  ];
  for (const c of candidates) {
    if (!c) continue;
    try {
      if (fs.existsSync(path.join(c, 'backend', 'main.py')) || fs.existsSync(path.join(c, 'package.json'))) {
        return c;
      }
    } catch (_) { /* ignore */ }
  }
  return appPath || 'C:\\Zaram';
}

function cleanup() {
  if (quitting) return;
  quitting = true;
  logger.info('Shutting down desktop runtime');
  stopPresenceFrameTimer();
  if (backend) backend.stop();
  if (shortcuts) shortcuts.unregisterAll();
  // Before `windows.destroy()`, because the overlay is always-on-top and
  // outlives an ordinary close: a panel left floating after the app has quit
  // is a window with nothing behind it.
  if (ambient) ambient.destroy();
  if (staticServer) {
    try { staticServer.close(); } catch (_) { /* ignore */ }
  }
  if (windows) windows.destroy();
  if (desktopRuntime && desktopRuntime.presenceRuntime) {
    try { desktopRuntime.presenceRuntime.shutdown(); } catch (_) { /* ignore */ }
  }
  try { logStream.end(); } catch (_) { /* ignore */ }
}

async function bootstrap() {
  // Build config + logger now that `app` is ready.
  const resourcesPath = app.isPackaged ? process.resourcesPath : app.getAppPath();
  config = createConfig({
    isDev,
    appPath: resourcesPath,
    userDataPath: app.getPath('userData'),
    resourcesPath,
    backendPort: Number(process.env.ZARAM_BACKEND_PORT) || 8420,
    rendererDevPort: 5173,
    staticPort: Number(process.env.ZARAM_STATIC_PORT) || 5180,
  });
  fs.mkdirSync(config.logsPath, { recursive: true });
  logStream = fs.createWriteStream(path.join(config.logsPath, 'desktop.log'), { flags: 'a' });
  logger = createLogger({
    scope: 'main',
    fileStream: logStream,
    enableConsole: isDev,
    minLevel: isDev ? 'debug' : 'info',
  });
  logger.info('Zaram desktop starting', { version: app.getVersion(), isDev, platform: process.platform });

  // Deep-link protocol registration (Windows/Linux).
  if (!process.defaultApp) {
    try {
      app.setAsDefaultProtocolClient('zaram');
    } catch (err) {
      logger.warn('Failed to register protocol client', { error: err.message });
    }
  }

  // Production: serve the built frontend + reverse-proxy the backend.
  if (!isDev) {
    staticServer = createStaticServer({
      staticDir: config.renderer.staticDir,
      backendBaseUrl: config.backend.baseUrl,
      apiPrefixes: config.renderer.apiProxyPrefixes,
    });
    await new Promise((resolve) => {
      staticServer.listen(config.renderer.staticPort, '127.0.0.1', () => {
        logger.info('Static server listening', { port: config.renderer.staticPort });
        resolve();
      });
    }).catch((err) => logger.error('Static server failed', { error: err.message }));
  }

  windows = new WindowManager({ config, logger: logger.child('window') });
  windows.createSplash();
  const mainWin = windows.createMainWindow();
  hardenWindow(mainWin);

  // Desktop services (require app ready for platform-aware paths).
  const roots = {
    appData: app.getPath('userData'),
    logs: config.logsPath,
    downloads: app.getPath('downloads'),
    documents: app.getPath('documents'),
    temp: app.getPath('temp'),
  };
  services = createServices({
    config,
    logger: logger.child('services'),
    getWindow: () => windows.getMainWindow(),
    pushDownload: (id, payload) => pushToRenderer(MAIN_EVENTS.downloadProgress, payload),
    roots,
  });

  backend = new BackendLauncher({ config, logger: logger.child('backend') });

  const loadedDesktop = loadDesktopRuntime();
  const rtTokens = desktopRuntime ? desktopRuntime.tokens : null;
  if (loadedDesktop && desktopRuntime) {
    try {
      desktopRuntime.presenceRuntime.start();
      logger.info('Desktop runtime started');
    } catch (e) {
      logger.warn('Desktop runtime start failed', { error: e.message });
    }

    const workspace = desktopRuntime.container.resolve(rtTokens ? rtTokens.workspaceRuntime : 'WorkspaceRuntime');
    if (workspace && !workspace.getRootPath && !workspace.getRootPath()) {
      if (workspace.setRootPath) {
        // Phase 2: automatically detect the Zaram workspace root.
        const detected = detectZaramWorkspace(config.appPath);
        workspace.setRootPath(detected);
        logger.info('Workspace root set', { root: detected });
      }
    }
  }

  registerHandlers(ipcMain, {
    services, app, config, backend, logger, desktopRuntime,
    // A getter, because the ambient surface is constructed below with the
    // other native capabilities and this runs first.
    getAmbient: () => ambient,
  });

  if (loadedDesktop && desktopRuntime) {
    const exec = desktopRuntime.container.resolve(rtTokens ? rtTokens.executionRuntime : 'ExecutionRuntime');
    if (exec && exec.subscribe) {
      exec.subscribe((event) => {
        pushToRenderer(MAIN_EVENTS.executionEvent, event);
      });
    }
    if (desktopRuntime.presenceRuntime && desktopRuntime.presenceRuntime.subscribeExecutive) {
      desktopRuntime.presenceRuntime.subscribeExecutive((snapshot) => {
        pushToRenderer(MAIN_EVENTS.executiveSnapshot, snapshot);
      });
    }

    const workspace = desktopRuntime.container.resolve(rtTokens ? rtTokens.workspaceRuntime : 'WorkspaceRuntime');
    if (workspace) {
      if (workspace.subscribe) {
        workspace.subscribe((event) => {
          pushToRenderer(MAIN_EVENTS.workspaceEvent, event);
        });
      }
      setTimeout(() => {
        try {
          if (workspace.discover) workspace.discover([], 'shallow');
        } catch (e) {
          logger.warn('Initial workspace discovery failed', { error: e.message });
        }
      }, 500);
    }

    const vscodePack = desktopRuntime.container.resolve(rtTokens ? rtTokens.vscodePack : 'VSCodeCapabilityPack');
    if (vscodePack) {
      vscodePack.getAdapter().subscribe((event) => {
        pushToRenderer(MAIN_EVENTS.vscodeEvent, event);
      });
    }

    // --- Presence Runtime bridge (desktop runtime -> renderer IPC) ---
  let presenceFrameTimer = null;

  function stopPresenceFrameTimer() {
    if (presenceFrameTimer) {
      clearInterval(presenceFrameTimer)
      presenceFrameTimer = null
    }
  }

  function broadcastViewport() {
    const win = windows && windows.getMainWindow();
    if (win && !win.isDestroyed()) {
      const bounds = win.getBounds();
      const dpr = win.webContents.getZoomFactor() || 1;
      pushToRenderer(MAIN_EVENTS.presenceViewport, {
        width: bounds.width,
        height: bounds.height,
        scaleFactor: dpr,
      });
    }
  }

  // `getMainWindow()`, not `_mainWindow` — which `WindowManager` has never had.
  //
  // **This one line stopped the desktop application booting.** It threw
  // `Cannot read properties of undefined (reading 'on')` inside `bootstrap()`,
  // whose only handler logs the message, so everything below it simply never
  // ran: the tray, the global shortcuts, the auto-updater, deep links, file
  // associations, the `backend.onStatus` wiring that loads the app — and
  // `backend.start()` itself, at line 389. The window stayed on the splash
  // for ever and no backend was ever launched.
  //
  // It only fires when the desktop runtime loads, because this block is inside
  // `if (loadedDesktop && desktopRuntime)`. A build without `desktop/dist` was
  // therefore fine, and `desktop/dist` is in the installer's file list — so
  // the packaged app got the broken path and a bare checkout could get the
  // working one, which is the same asymmetry that hid the asar defect.
  //
  // The guard is kept: `windows` is truthy here today, and a null check that
  // reads a property off the object it is checking is not a guard.
  const mainWindow = windows && windows.getMainWindow();
  if (mainWindow) {
    mainWindow.on('resize', broadcastViewport);
  }

  if (desktopRuntime.presenceRuntime) {
    presenceFrameTimer = setInterval(() => {
      try {
        const frame = desktopRuntime.presenceRuntime.getRendererFrame()
        if (frame) {
          pushToRenderer(MAIN_EVENTS.presenceFrame, frame)
        }
      } catch (e) {
        // ignore frame push errors
      }
    }, 1000 / 30)
  }
  }

  // Native capabilities (abstractions; safe no-ops when unavailable).
  tray = createTray({
    getWindow: () => windows.getMainWindow(),
    onQuit: () => app.quit(),
    iconPath: null,
    logger,
  });
  shortcuts = createGlobalShortcuts({ logger });

  // The ambient surface. Started here rather than on first use, deliberately:
  // the panel window is created hidden so that summoning it is a `show()`
  // rather than a renderer boot. Proximity is the point, and a surface that
  // takes a second to appear is one people stop reaching for.
  ambient = createAmbientSurface({
    config,
    shortcuts,
    logger: logger.child ? logger.child('ambient') : logger,
    accelerator: services.settings.get('ambient.accelerator') || undefined,
    // Opt-out rather than opt-in: an overlay nobody knows about is an overlay
    // nobody uses, and it does nothing at all until it is summoned. The
    // setting exists so it can be turned off, which is a different question
    // from whether it may read anything — it never reads anything.
    enabled: services.settings.get('ambient.enabled') !== false,
  });
  const ambientStarted = ambient.start();
  logger.info('Ambient surface', ambientStarted);
  updater = createAutoUpdater({
    onState: (s) => pushToRenderer(MAIN_EVENTS.updaterState, s),
    logger,
  });
  createDeepLinks({
    scheme: 'zaram',
    onDeepLink: (url) => pushToRenderer(MAIN_EVENTS.deepLink, url),
  });
  createFileAssociations({
    onFileOpen: (f) => pushToRenderer(MAIN_EVENTS.fileOpen, f),
  });

  // --- Backend lifecycle -> window state ---
  const startupTimer = setTimeout(() => {
    if (!appLoaded) {
      logger.warn('Backend did not become available within startup timeout');
      windows.loadError(backend.getStatus());
      windows.closeSplash();
    }
  }, config.backend.startupTimeoutMs);

  // Delay app load until backend is available.
  backend.onStatus((status) => {
    pushToRenderer(MAIN_EVENTS.backendStatus, status);
    if (status.state === 'available') {
      if (!appLoaded) {
        clearTimeout(startupTimer);
        appLoaded = true;
        windows.loadApp();
        windows.showMainWindow();
        windows.closeSplash();
      } else {
        windows.loadApp();
        windows.showMainWindow();
      }
      broadcastViewport();
    } else if ((status.state === 'unavailable' || status.state === 'error') && appLoaded) {
      appLoaded = false;
      windows.loadError(status);
    }
  });

  // A boot that can prove it booted.
  //
  // `bootstrap` had been throwing on its way here for some time, and its only
  // handler logs the message — so the tray, the shortcuts, the updater and
  // `backend.start()` below simply never ran, and the product sat on a splash
  // screen. Nothing caught it because nothing has ever executed this file: the
  // suite loads modules, and `npm run dev` starts a *different* main process
  // (`desktop/dist/src/main/index.js`), which is why every developer's machine
  // looked healthy.
  //
  // This flag is the smallest thing that closes that gap. `test/bootstrap.test.js`
  // launches the real main process, waits for this line, and fails if the
  // error appears instead. Placed before `backend.start()` deliberately: a
  // smoke test should not leave a Python process behind.
  if (process.env.ZARAM_SMOKE === '1') {
    logger.info('Smoke: bootstrap reached the end');
    setImmediate(() => app.quit());
    return;
  }

  backend.start();

  if (!isDev) {
    updater.checkForUpdates();
  }
}

app.whenReady().then(bootstrap).catch((err) => {
  logger.error('Bootstrap failed', { error: err && err.message });
});

// --- Lifecycle / cleanup wiring ---
app.on('second-instance', (_event, argv) => {
  const w = windows && windows.getMainWindow();
  if (w && !w.isDestroyed()) {
    if (w.isMinimized()) w.restore();
    w.show();
    w.focus();
  }
  const link = (argv || []).find((a) => a && a.startsWith('zaram://'));
  if (link) pushToRenderer(MAIN_EVENTS.deepLink, link);
});

app.on('open-url', (event, url) => {
  event.preventDefault();
  pushToRenderer(MAIN_EVENTS.deepLink, url);
});

app.on('open-file', (event, file) => {
  event.preventDefault();
  pushToRenderer(MAIN_EVENTS.fileOpen, file);
});

app.on('activate', () => {
  const w = windows && windows.getMainWindow();
  if (w && !w.isDestroyed()) {
    w.show();
    w.focus();
  }
});

app.on('window-all-closed', () => {
  // With a tray we keep running after the window closes; otherwise quit.
  if (!tray && process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  cleanup();
});

// Close-to-tray when a tray exists. Only the main window is affected; the
// splash/error windows must always be allowed to close.
app.on('browser-window-created', (_event, win) => {
  if (windows && win === windows.getMainWindow()) {
    win.on('close', (e) => {
      if (!quitting && tray && win === windows.getMainWindow()) {
        e.preventDefault();
        win.hide();
      }
    });
  }
});

process.on('uncaughtException', (err) => {
  logger.error('Uncaught exception', { error: err && err.message });
});

module.exports = { config, logger };
