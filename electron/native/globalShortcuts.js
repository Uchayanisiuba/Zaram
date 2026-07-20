'use strict';

const { globalShortcut } = require('electron');

/**
 * Global shortcut abstraction (foundation).
 *
 * Thin, safe wrapper over Electron's globalShortcut. All registrations are
 * tracked so they can be released cleanly on shutdown. Real accelerators
 * (e.g. push-to-talk for Voice, summon Orb) are registered by later milestones.
 *
 * @param {import('../types').Logger} [logger]
 */
function createGlobalShortcuts({ logger } = {}) {
  const log = logger || console;
  const registered = new Set();

  return {
    register(accelerator, cb) {
      try {
        const ok = globalShortcut.register(accelerator, cb);
        if (ok) {
          registered.add(accelerator);
          log.info('Global shortcut registered', { accelerator });
        } else {
          log.warn('Global shortcut failed', { accelerator });
        }
        return ok;
      } catch (err) {
        log.warn('Global shortcut error', { accelerator, error: err.message });
        return false;
      }
    },
    unregisterAll() {
      try {
        globalShortcut.unregisterAll();
      } finally {
        registered.clear();
      }
    },
    getRegistered: () => Array.from(registered),
  };
}

module.exports = { createGlobalShortcuts };
