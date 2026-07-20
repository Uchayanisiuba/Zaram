'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const { Channels, RENDERER_INVOKABLE, MAIN_EVENTS, listChannels, isInvokable } = require('../electron/ipc/channels');

test('channels: every channel is a non-empty string', () => {
  for (const ch of listChannels()) {
    assert.strictEqual(typeof ch, 'string');
    assert.ok(ch.length > 0);
  }
});

test('channels: no duplicate channel names', () => {
  const all = listChannels();
  const unique = new Set(all);
  assert.strictEqual(all.length, unique.size);
});

test('channels: renderer invokable list only contains known channels', () => {
  const known = new Set(listChannels());
  for (const ch of RENDERER_INVOKABLE) {
    assert.ok(known.has(ch), `whitelisted channel must be defined: ${ch}`);
  }
});

test('channels: sensitive channels are NOT invokable from the renderer', () => {
  // Backend lifecycle and native push events must never be renderer-invokable.
  assert.ok(!RENDERER_INVOKABLE.includes(MAIN_EVENTS.backendStatus));
  assert.ok(!RENDERER_INVOKABLE.includes(MAIN_EVENTS.downloadProgress));
  assert.ok(!RENDERER_INVOKABLE.includes(MAIN_EVENTS.updaterState));
});

test('channels: isInvokable validates against the whitelist', () => {
  assert.strictEqual(isInvokable(Channels.app.getVersion), true);
  assert.strictEqual(isInvokable('evil:rm-rf'), false);
});
