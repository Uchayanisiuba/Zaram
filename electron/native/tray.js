'use strict';

const { Tray, Menu, app } = require('electron');

/**
 * System tray abstraction (foundation).
 *
 * Creates a tray icon with a minimal menu. The icon is optional — if none is
 * provided the tray is skipped gracefully (full icon asset pipeline is a later
 * milestone). Returns the Tray instance or null.
 */
function createTray({ getWindow, onQuit, iconPath, logger }) {
  if (!iconPath) {
    if (logger) logger.info('Tray disabled: no icon provided');
    return null;
  }
  try {
    const tray = new Tray(iconPath);
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Show Zaram',
        click: () => {
          const w = getWindow();
          if (w && !w.isDestroyed()) {
            w.show();
            w.focus();
          }
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Zaram',
        click: () => {
          if (onQuit) onQuit();
          else app.quit();
        },
      },
    ]);
    tray.setToolTip('Zaram');
    tray.setContextMenu(contextMenu);
    return tray;
  } catch (err) {
    if (logger) logger.warn('Failed to create tray', { error: err.message });
    return null;
  }
}

module.exports = { createTray };
