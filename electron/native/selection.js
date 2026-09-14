'use strict';

const { clipboard } = require('electron');
const { execFile } = require('child_process');

/**
 * The selection under the pointer, read once, when asked.
 *
 * `CLAUDE.md`, "The ambient surface": *"Zaram reads the selection when asked:
 * a hotkey, a click on the edge handle, a drag. It does not watch what is
 * typed."* This is the "when asked" half. On the summon key the focused
 * application is sent one copy keystroke, the clipboard is read, and the
 * clipboard is put back the way it was. No hook is installed, nothing
 * listens between summons, and nothing here runs unless the key was pressed.
 *
 * **No native module.** Sending a keystroke needs the operating system, and
 * the candidates (nut.js, robotjs) are either commercially licensed in their
 * current versions or unmaintained. Windows can do it from a one-line
 * PowerShell call to `SendKeys`, which ships with the OS; on other platforms
 * this returns nothing and the panel opens empty, which is what it did
 * before. That is a smaller capability than a native hook would give and it
 * is the honest one: the same keystroke a person would press, once.
 *
 * **The clipboard is the user's.** What was on it before is written back
 * after the read, so a summon never eats the thing they were about to paste.
 * The read is compared against what was there: if the copy changed nothing
 * — no selection, or an application that does not honour it — nothing is
 * reported, rather than the old clipboard being passed off as a selection.
 */

const SETTLE_MS = 160;

function sendCopyKeystroke() {
  return new Promise((resolve) => {
    if (process.platform !== 'win32') {
      resolve(false);
      return;
    }
    const script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^c')";
    execFile(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', script],
      { windowsHide: true, timeout: 2500 },
      (error) => resolve(!error),
    );
  });
}

/**
 * Read the current selection by copying it, then restore the clipboard.
 * Resolves to the selected text, or `''` when there was none or the platform
 * cannot send the keystroke.
 */
async function readSelection() {
  const before = clipboard.readText();
  const sent = await sendCopyKeystroke();
  if (!sent) return '';
  await new Promise((r) => setTimeout(r, SETTLE_MS));
  const after = clipboard.readText();
  // Put back what was theirs, whether or not anything was read.
  if (after !== before) clipboard.writeText(before);
  if (!after || after === before) return '';
  return after;
}

module.exports = { readSelection };
