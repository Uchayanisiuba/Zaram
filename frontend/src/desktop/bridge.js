// Safe desktop bridge for the renderer.
//
// This module is intentionally non-visual and degrades gracefully when the app
// runs in a plain browser (e.g. `vite` dev without Electron). It only forwards
// to `window.zaram` when the secure preload is present, so future runtimes
// (UI Runtime, Orb Runtime, Character Runtime, Garage Runtime, Project Runtime)
// can consume desktop capabilities without caring whether they run in Electron.

const zaram = (typeof window !== 'undefined' && window.zaram) ? window.zaram : null;

export const isDesktop = Boolean(zaram);

function safe(fn, fallback) {
  return (...args) => {
    if (!zaram) {
      return Promise.resolve(fallback === undefined ? null : fallback);
    }
    try {
      return fn(...args);
    } catch (err) {
      return Promise.reject(err);
    }
  };
}

export const desktop = {
  app: {
    getInfo: safe(() => zaram.app.getInfo()),
    getVersion: safe(() => zaram.app.getVersion()),
    getPlatform: safe(() => zaram.app.getPlatform()),
  },
  backend: {
    getStatus: safe(() => zaram.backend.getStatus()),
    restart: safe(() => zaram.backend.restart()),
    onStatus: (cb) =>
      zaram && zaram.backend.onStatus ? zaram.backend.onStatus(cb) : () => {},
  },
  notify: {
    show: safe((opts) => zaram.notify.show(opts)),
  },
  shell: {
    openExternal: safe((url) => zaram.shell.openExternal(url)),
    openPath: safe((p) => zaram.shell.openPath(p)),
    showItemInFolder: safe((p) => zaram.shell.showItemInFolder(p)),
  },
  dialog: {
    showOpen: safe((opts) => zaram.dialog.showOpen(opts)),
    showSave: safe((opts) => zaram.dialog.showSave(opts)),
    showMessage: safe((opts) => zaram.dialog.showMessage(opts)),
  },
  fs: {
    getPath: safe((name) => zaram.fs.getPath(name)),
    readText: safe((root, rel) => zaram.fs.readText(root, rel)),
    writeText: safe((root, rel, content) => zaram.fs.writeText(root, rel, content)),
    listDir: safe((root, rel) => zaram.fs.listDir(root, rel)),
  },
  settings: {
    get: safe((key) => zaram.settings.get(key)),
    set: safe((key, value) => zaram.settings.set(key, value)),
    getAll: safe(() => zaram.settings.getAll(), {}),
  },
  download: {
    start: safe((url, opts) => zaram.download.start(url, opts)),
    cancel: safe((id) => zaram.download.cancel(id)),
    onProgress: (cb) =>
      zaram && zaram.download.onProgress ? zaram.download.onProgress(cb) : () => {},
  },
};

export default desktop;
