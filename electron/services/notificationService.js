'use strict';

/**
 * Notification service. Lazily requires electron so the module can be imported
 * (and the container built) without a live Electron runtime.
 */
function createNotificationService({ appName }) {
  return {
    async show(opts) {
      const { Notification } = require('electron');
      const n = new Notification({
        title: (opts && opts.title) || appName || 'Zaram',
        body: (opts && opts.body) || '',
        icon: opts && opts.icon,
      });
      n.show();
      return 'shown';
    },
  };
}

module.exports = { createNotificationService };
