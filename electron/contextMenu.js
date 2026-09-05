'use strict';

/**
 * The right-click menu, because Electron does not have one.
 *
 * **This is an absence, not a disabled feature.** A web page in a browser gets
 * the browser's own context menu; an Electron window gets *nothing at all*
 * unless the app builds one. So right-clicking a picture Zaram had just drawn
 * did nothing whatsoever — reported by the maintainer on 4 September 2026, and
 * it reads as the image being inert rather than as a menu being absent.
 *
 * **`copyImageAt` is Chromium's own copy, and that is why it is used.** The
 * alternative — fetching the image in the renderer, making a `Blob`, and
 * writing it through the async clipboard API — re-encodes the picture, needs a
 * permission that behaves differently across platforms, and would put a second
 * copy of a generated image through JavaScript for no gain.
 * `webContents.copyImageAt(x, y)` copies the decoded bitmap the page is already
 * showing, as a real image the user can paste into anything.
 *
 * Deliberately small. This is not a place to put application commands: a menu
 * that grows into a second command surface is one more thing to keep in step
 * with the interface, and `CLAUDE.md` is explicit that capability belongs in
 * the conversation rather than in chrome. Copy an image, copy selected text,
 * and the editing commands a text field is expected to have.
 */

const { Menu, clipboard, shell } = require('electron');

/**
 * Attach the menu to a window's web contents.
 *
 * @param {import('electron').BrowserWindow} win
 * @param {import('./types').Logger} [logger]
 */
function attachContextMenu(win, logger) {
  if (!win || win.isDestroyed()) return;
  const contents = win.webContents;

  contents.on('context-menu', (_event, params) => {
    const items = [];

    if (params.mediaType === 'image' && params.srcURL) {
      items.push({
        label: 'Copy image',
        click: () => {
          try {
            contents.copyImageAt(params.x, params.y);
          } catch (error) {
            if (logger) logger.warn('copy image failed', { error: String(error) });
          }
        },
      });
      // The address, not the bytes. Useful for a file:// artifact — it is what
      // a user pastes into a file manager — and harmless for a data: URI, which
      // is simply long.
      items.push({
        label: 'Copy image address',
        click: () => clipboard.writeText(params.srcURL),
      });
      // Only for a real file on disk. A generated image is written to the
      // artifacts directory, so this is the ordinary case; a `data:` URI has no
      // folder to show and the item is left off rather than shown doing
      // nothing.
      if (params.srcURL.startsWith('file://')) {
        items.push({
          label: 'Show in folder',
          click: () => {
            try {
              shell.showItemInFolder(decodeURIComponent(new URL(params.srcURL).pathname.replace(/^\//, '')));
            } catch (error) {
              if (logger) logger.warn('show in folder failed', { error: String(error) });
            }
          },
        });
      }
    }

    if (params.selectionText && params.selectionText.trim()) {
      if (items.length) items.push({ type: 'separator' });
      items.push({ label: 'Copy', role: 'copy' });
    }

    // A text field gets what a text field is expected to have. `isEditable`
    // covers inputs, textareas and contenteditable, so the composer and every
    // Settings field are included without naming any of them.
    if (params.isEditable) {
      if (items.length) items.push({ type: 'separator' });
      items.push(
        { label: 'Cut', role: 'cut', enabled: params.editFlags.canCut },
        { label: 'Copy', role: 'copy', enabled: params.editFlags.canCopy },
        { label: 'Paste', role: 'paste', enabled: params.editFlags.canPaste },
        { type: 'separator' },
        { label: 'Select all', role: 'selectAll' },
      );
    }

    // Nothing to offer means no menu. An empty grey rectangle is worse than the
    // nothing that was there before, because it looks broken rather than absent.
    if (!items.length) return;

    Menu.buildFromTemplate(items).popup({ window: win });
  });
}

module.exports = { attachContextMenu };
