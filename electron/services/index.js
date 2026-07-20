'use strict';

const { createSettingsService } = require('./settingsService');
const { createDownloadService } = require('./downloadService');
const { createWindowService } = require('./windowService');
const { createNotificationService } = require('./notificationService');
const { createShellService } = require('./shellService');
const { createFileDialogService } = require('./fileDialogService');
const { createFileSystemService } = require('./fileSystemService');

/**
 * Desktop service container (dependency-injection provider).
 *
 * Central place that constructs every desktop capability. Main process builds
 * this once after `app` is ready and injects it into the IPC handlers. Kept
 * free of a hard `electron` dependency at construction time so the pure
 * services (settings, downloads) remain unit testable.
 *
 * @param {object} ctx
 * @param {import('../types').DesktopConfig} ctx.config
 * @param {import('../types').Logger} ctx.logger
 * @param {() => any} ctx.getWindow
 * @param {(id: string, payload: any) => void} ctx.pushDownload
 * @param {Record<string,string>} [ctx.roots]  Platform-aware fs roots.
 */
function createServices({ config, logger, getWindow, pushDownload, roots }) {
  const log = logger || console;

  const settings = createSettingsService({ filePath: config.settingsPath });
  const downloads = createDownloadService({ emit: pushDownload, logger: log.child ? log.child('download') : log });
  const window = createWindowService({ getWindow });
  const notification = createNotificationService({ appName: 'Zaram' });
  const shell = createShellService();
  const dialog = createFileDialogService({ getWindow });
  const fs = createFileSystemService({ roots: roots || {}, fsImpl: undefined });

  return {
    settings,
    downloads,
    window,
    notification,
    shell,
    dialog,
    fs,
    all: { settings, downloads, window, notification, shell, dialog, fs },
  };
}

module.exports = { createServices };
