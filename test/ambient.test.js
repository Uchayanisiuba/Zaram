'use strict';

/**
 * The ambient surface: where it lands, and what it never does.
 *
 * The geometry tests are ordinary. The last one is not: it asserts at source
 * level that this module installs no passive capture of any kind. A prohibition
 * written only in a comment is a prohibition that survives exactly until
 * somebody has a good reason, and "read what they are typing" will always look
 * like a good reason to whoever is adding it.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const {
  panelBounds,
  handleBounds,
  panelUrl,
  DEFAULT_ACCELERATOR,
  PANEL,
  HANDLE,
} = require('../electron/native/ambient');

const FULL_HD = { x: 0, y: 0, width: 1920, height: 1040 };

test('ambient: the panel is centred on the display and sits in the upper third', () => {
  const b = panelBounds(FULL_HD);
  assert.strictEqual(b.width, PANEL.width);
  assert.strictEqual(b.x, Math.round((1920 - PANEL.width) / 2));
  assert.ok(b.y > 0 && b.y < FULL_HD.height / 2, `expected upper half, got y=${b.y}`);
});

test('ambient: the panel follows the display it is summoned on', () => {
  // A second monitor to the right, which is where the cursor was. The panel
  // must not appear on the primary display because that is where the main
  // window happens to live.
  const second = { x: 1920, y: 0, width: 2560, height: 1400 };
  const b = panelBounds(second);
  assert.ok(b.x >= second.x, `landed on the wrong display: x=${b.x}`);
  assert.ok(b.x + b.width <= second.x + second.width);
});

test('ambient: a work area smaller than the panel still produces visible bounds', () => {
  // Not theoretical — a side-docked taskbar on a small laptop display, or a
  // scaled 1366x768 panel, produces exactly this.
  const small = { x: 0, y: 0, width: 480, height: 320 };
  const b = panelBounds(small);
  assert.ok(b.width <= small.width, 'wider than the display');
  assert.ok(b.height <= small.height, 'taller than the display');
  assert.ok(b.y >= small.y, 'starts above the work area');
  assert.ok(b.y + b.height <= small.y + small.height, 'runs off the bottom');
});

test('ambient: the handle hugs the right edge and widens without moving its edge', () => {
  const rest = handleBounds(FULL_HD, false);
  const hovered = handleBounds(FULL_HD, true);

  assert.strictEqual(rest.x + rest.width, FULL_HD.width, 'not flush with the edge');
  assert.strictEqual(hovered.x + hovered.width, FULL_HD.width, 'edge moved on hover');
  assert.ok(hovered.width > rest.width, 'hovering did not widen it');
  assert.strictEqual(rest.width, HANDLE.restWidth);
  // Vertically centred, so it is in the same place on every display.
  assert.strictEqual(rest.y, Math.round((FULL_HD.height - rest.height) / 2));
});

test('ambient: the panel loads its own entry, not the shell', () => {
  assert.strictEqual(panelUrl('http://localhost:5173'), 'http://localhost:5173/ambient.html');
  // A trailing slash on the configured renderer URL must not produce `//`.
  assert.strictEqual(panelUrl('http://127.0.0.1:5180/'), 'http://127.0.0.1:5180/ambient.html');
});

test('ambient: the default accelerator avoids the two that collide', () => {
  // Alt+Space is the Windows system menu; Ctrl+Space is taken by most editors.
  assert.notStrictEqual(DEFAULT_ACCELERATOR, 'Alt+Space');
  assert.notStrictEqual(DEFAULT_ACCELERATOR, 'CommandOrControl+Space');
  assert.match(DEFAULT_ACCELERATOR, /Space$/);
});

/**
 * Invoked, never passive — asserted, not promised.
 *
 * `CLAUDE.md` prohibits a passive-capture mode at any accuracy. The whole
 * opening against Superhuman Go is that Zaram reads a selection when asked and
 * watches nothing otherwise, so this is the one property of the surface that
 * the product's pitch depends on being literally true.
 *
 * Source-level, because there is no runtime observation that proves an absence.
 * The list is of mechanisms rather than of words: each of these is a way to
 * observe the user without them having asked, and none of them has a legitimate
 * use in a window that appears on a keypress.
 */
test('ambient: the module installs nothing that watches the user', () => {
  const source = fs.readFileSync(
    path.join(__dirname, '..', 'electron', 'native', 'ambient.js'),
    'utf8',
  );
  // Comments explain the prohibition and must not trip it.
  const code = source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1');

  const forbidden = [
    // A repeating timer with no end is the shape of a poll. The module does
    // use a bounded `setTimeout` chain to retry a failed page load, which is
    // not the same thing and is deliberately still allowed: it observes a
    // renderer that would not start, never the person at the keyboard. The
    // entries below it are the actual observation mechanisms, and they are
    // what this test is really for — the timer ban is a shape, those are the
    // substance.
    ['setInterval', 'a poll is a watcher with extra steps'],
    ['clipboard.readText', 'reading the clipboard unasked is passive capture'],
    ['before-input-event', 'a keystroke hook is exactly what is prohibited'],
    ['globalShortcut.register', 'accelerators go through the tracked wrapper, not directly'],
    ['powerMonitor', 'no observation of what the user is doing between summons'],
    ['desktopCapturer', 'the surface never reads the screen'],
  ];

  for (const [mechanism, why] of forbidden) {
    assert.ok(
      !code.includes(mechanism),
      `ambient.js references ${mechanism} — ${why}`,
    );
  }
});
