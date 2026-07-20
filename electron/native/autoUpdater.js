'use strict';

/**
 * Auto-updater abstraction (foundation / interface only).
 *
 * Uses `electron-updater` when available; otherwise degrades to a no-op that
 * reports a "not configured" state. Full update UI, signing, and release
 * channels belong to a later milestone. The contract below is stable so the
 * UI/runtimes can consume it without rework.
 *
 * @param {object} [opts]
 * @param {(state: object) => void} [opts.onState]
 * @param {import('../types').Logger} [opts.logger]
 */
function createAutoUpdater({ onState, logger } = {}) {
  const log = logger || console;
  let impl = null;
  try {
    impl = require('electron-updater');
  } catch (_) {
    impl = null;
  }

  function emit(state) {
    if (onState) onState(state);
  }

  if (!impl || !impl.autoUpdater) {
    log.info('Auto-updater not configured (electron-updater unavailable)');
    emit({ phase: 'unavailable', detail: 'electron-updater not installed' });
    return {
      isConfigured: false,
      checkForUpdates: async () => emit({ phase: 'skipped', detail: 'not configured' }),
      quitAndInstall: () => {},
    };
  }

  const autoUpdater = impl.autoUpdater;
  autoUpdater.on('checking-for-update', () => emit({ phase: 'checking' }));
  autoUpdater.on('update-available', (i) => emit({ phase: 'available', version: i && i.version }));
  autoUpdater.on('update-not-available', () => emit({ phase: 'up-to-date' }));
  autoUpdater.on('download-progress', (p) => emit({ phase: 'downloading', percent: p && p.percent }));
  autoUpdater.on('update-downloaded', () => emit({ phase: 'downloaded' }));
  autoUpdater.on('error', (e) => emit({ phase: 'error', detail: e && e.message }));

  return {
    isConfigured: true,
    checkForUpdates: async () => {
      try {
        await autoUpdater.checkForUpdates();
      } catch (e) {
        emit({ phase: 'error', detail: e.message });
      }
    },
    quitAndInstall: () => autoUpdater.quitAndInstall(),
  };
}

module.exports = { createAutoUpdater };
