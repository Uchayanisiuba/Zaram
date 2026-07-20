'use strict';

/**
 * File association abstraction (foundation / interface only).
 *
 * The actual OS registration is declared in the electron-builder config
 * (`fileAssociations`). This module provides a stable runtime hook so the app
 * can react when a file is opened through the OS. The handler is wired by the
 * main process via `app.on('open-file')` / second-instance events.
 *
 * @param {object} [opts]
 * @param {(filePath: string) => void} [opts.onFileOpen]
 */
function createFileAssociations({ onFileOpen } = {}) {
  return {
    onFileOpen,
    /** Returns the extensions this build is registered for (from builder cfg). */
    getRegisteredExtensions: () => {
      try {
        const cfg = require('../../electron-builder.yml');
        const list = cfg && cfg.fileAssociations;
        if (Array.isArray(list)) return list.map((e) => e.ext).filter(Boolean);
      } catch (_) {
        /* config not present at runtime */
      }
      return [];
    },
  };
}

module.exports = { createFileAssociations };
