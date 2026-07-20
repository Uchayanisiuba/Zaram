'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { createSettingsService } = require('../electron/services/settingsService');
const { createDownloadService } = require('../electron/services/downloadService');
const { createFileSystemService } = require('../electron/services/fileSystemService');

test('settings: set/get persists to disk', () => {
  const file = path.join(os.tmpdir(), `zaram-set-${Date.now()}.json`);
  fs.rmSync(file, { force: true });
  try {
    const s = createSettingsService({ filePath: file });
    s.set('theme', 'dark');
    assert.strictEqual(s.get('theme'), 'dark');
    const reloaded = createSettingsService({ filePath: file });
    assert.strictEqual(reloaded.get('theme'), 'dark');
  } finally {
    fs.rmSync(file, { force: true });
  }
});

test('settings: corrupt file does not throw', () => {
  const file = path.join(os.tmpdir(), `zaram-set-bad-${Date.now()}.json`);
  fs.rmSync(file, { force: true });
  try {
    fs.writeFileSync(file, 'not json');
    const s = createSettingsService({ filePath: file });
    s.set('x', 1);
    assert.strictEqual(s.get('x'), 1);
  } finally {
    fs.rmSync(file, { force: true });
  }
});

test('download: start returns id and emits progress event', async () => {
  const events = [];
  const d = createDownloadService({ emit: (id, p) => events.push(p) });
  const id = await d.start('https://example.com/model.bin');
  assert.ok(id.startsWith('dl_'));
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].status, 'queued');
});

test('fs: write then read inside an allowed root', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-fs-'));
  try {
    const svc = createFileSystemService({ roots: { appData: root } });
    svc.writeText('appData', 'note.txt', 'hello');
    assert.strictEqual(svc.readText('appData', 'note.txt'), 'hello');
    assert.strictEqual(svc.getPath('appData'), root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('fs: path traversal is denied', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-fs-'));
  try {
    const svc = createFileSystemService({ roots: { appData: root } });
    assert.throws(() => svc.readText('appData', '../../etc/passwd'));
    assert.throws(() => svc.writeText('appData', '../escape.txt', 'x'));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
