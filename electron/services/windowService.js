'use strict';

/**
 * Window service. Thin wrapper over the main BrowserWindow so runtimes can
 * control the window without touching Electron directly.
 */
function createWindowService({ getWindow }) {
  function win() {
    const w = getWindow && getWindow();
    if (!w || w.isDestroyed()) throw new Error('Main window is not available');
    return w;
  }

  return {
    minimize: () => win().minimize(),
    maximize: () => win().maximize(),
    restore: () => win().restore(),
    close: () => win().close(),
    reload: () => win().reload(),
    isMaximized: () => {
      try {
        return win().isMaximized();
      } catch (_) {
        return false;
      }
    },
    setTitle: (title) => win().setTitle(title || 'Zaram'),
  };
}

module.exports = { createWindowService };
