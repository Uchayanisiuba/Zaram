'use strict';

/** Native file dialogs. */
function createFileDialogService({ getWindow }) {
  function owner() {
    const w = getWindow && getWindow();
    return w && !w.isDestroyed() ? w : undefined;
  }

  return {
    async showOpen(opts) {
      const { dialog } = require('electron');
      const result = await dialog.showOpenDialog(owner(), opts || {});
      if (result.canceled) return null;
      return (result.filePaths && result.filePaths[0]) || null;
    },
    async showSave(opts) {
      const { dialog } = require('electron');
      const result = await dialog.showSaveDialog(owner(), opts || {});
      if (result.canceled) return null;
      return result.filePath || null;
    },
    async showMessage(opts) {
      const { dialog } = require('electron');
      await dialog.showMessageBox(owner(), opts || {});
    },
    async selectDirectory(opts) {
      const { dialog } = require('electron');
      const result = await dialog.showOpenDialog(owner(), Object.assign(
        { properties: ['openDirectory', 'createDirectory'] },
        opts || {}
      ));
      if (result.canceled) return null;
      return (result.filePaths && result.filePaths[0]) || null;
    },
  };
}

module.exports = { createFileDialogService };
