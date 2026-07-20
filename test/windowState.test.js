'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const state = require('../electron/window/windowState');

function makeConfig(overrides) {
  return Object.assign(
    {
      window: { minWidth: 1024, minHeight: 700, defaultWidth: 1280, defaultHeight: 800 },
    },
    overrides || {},
  );
}

test('windowState: returns defaults when no file exists', () => {
  const cfg = makeConfig();
  const s = state.loadState(path.join(os.tmpdir(), `zaram-noexist-${Date.now()}.json`), cfg);
  assert.strictEqual(s.width, 1280);
  assert.strictEqual(s.height, 800);
});

test('windowState: clamps to minimum size', () => {
  const cfg = makeConfig();
  const clamped = state.clampBounds({ width: 100, height: 50 }, cfg.window.minWidth, cfg.window.minHeight);
  assert.strictEqual(clamped.width, 1024);
  assert.strictEqual(clamped.height, 700);
});

test('windowState: persists and reloads geometry', () => {
  const cfg = makeConfig();
  const file = path.join(os.tmpdir(), `zaram-state-${Date.now()}.json`);
  try {
    fs.rmSync(file, { force: true });
    const saved = state.saveState(file, cfg, { width: 1400, height: 900, x: 10, y: 20, maximized: false });
    assert.strictEqual(saved, true);
    const loaded = state.loadState(file, cfg);
    assert.strictEqual(loaded.width, 1400);
    assert.strictEqual(loaded.height, 900);
    assert.strictEqual(loaded.x, 10);
    assert.strictEqual(loaded.y, 20);
  } finally {
    fs.rmSync(file, { force: true });
  }
});

test('windowState: corrupt file falls back to defaults without throwing', () => {
  const cfg = makeConfig();
  const file = path.join(os.tmpdir(), `zaram-corrupt-${Date.now()}.json`);
  try {
    fs.writeFileSync(file, '{not valid json');
    const loaded = state.loadState(file, cfg);
    assert.strictEqual(loaded.width, 1280);
  } finally {
    fs.rmSync(file, { force: true });
  }
});
