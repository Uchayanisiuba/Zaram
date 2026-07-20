'use strict';

/** Shell integration (open URLs, open files, reveal in folder). */
function createShellService() {
  return {
    async openExternal(url) {
      const { shell } = require('electron');
      await shell.openExternal(url);
    },
    async openPath(p) {
      const { shell } = require('electron');
      return shell.openPath(p);
    },
    showItemInFolder(p) {
      const { shell } = require('electron');
      shell.showItemInFolder(p);
    },
  };
}

module.exports = { createShellService };
