'use strict';

/**
 * Running a downloaded update: what the shell will and will not start.
 *
 * The backend fetches and checks; this is the one step that runs a program, so
 * what is pinned here is the ways it must refuse -- a name the build does not
 * produce, a folder that is not the update folder, a file that changed after it
 * was checked, a renderer that tries to name its own -- and the order it acts in:
 * the installer starts only after the app has quit, with the flags that keep an
 * update from asking about the person's data.
 */

const test = require('node:test');
const assert = require('node:assert');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');

const { createUpdateInstaller, INSTALLER_ARGS, INSTALLER_NAME } = require('../electron/native/updateInstaller');

const BYTES = Buffer.from('MZ-installer-bytes'.repeat(1000));
const SHA = crypto.createHash('sha256').update(BYTES).digest('hex');

function folder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-update-'));
  const dir = path.join(root, 'updates');
  fs.mkdirSync(dir);
  return { root, dir };
}

function fakeApp() {
  const app = new EventEmitter();
  app.quitCalls = 0;
  app.quit = () => {
    app.quitCalls += 1;
    app.emit('quit');
  };
  return app;
}

function harness(over = {}) {
  const { dir } = folder();
  const file = path.join(dir, 'Zaram-0.1.0-x64.exe');
  fs.writeFileSync(file, BYTES);
  const info = { path: file, name: 'Zaram-0.1.0-x64.exe', sha256: SHA, tag: 'v0.1.0-alpha.8', ...(over.info || {}) };
  const app = fakeApp();
  const spawned = [];
  const asked = [];
  const installer = createUpdateInstaller({
    app,
    getBaseUrl: () => 'http://127.0.0.1:8420',
    getSecret: () => 'launch-secret',
    platform: 'win32',
    env: {},
    isDev: false,
    schedule: (fn) => fn(),
    spawnImpl: (cmd, args, opts) => {
      spawned.push({ cmd, args, opts });
      return { unref() { spawned.at(-1).unref = true; } };
    },
    fetchImpl: async (url, init) => {
      asked.push({ url, headers: init && init.headers });
      if (over.status) return { ok: false, status: over.status, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => info };
    },
    ...(over.deps || {}),
  });
  return { installer, app, spawned, asked, file, info };
}

test('the installer is started only after the app has quit, silent, updated and force-run', async () => {
  const { installer, app, spawned, file } = harness();
  const out = await installer.install();
  // quit was called and the `quit` event fired, so the spawn has happened -- and
  // it happened in that order: nothing is started while the app is still up.
  assert.deepStrictEqual(out, { ok: true });
  assert.strictEqual(app.quitCalls, 1);
  assert.strictEqual(spawned.length, 1);
  assert.strictEqual(spawned[0].cmd, file);
  assert.deepStrictEqual(spawned[0].args, ['/S', '--updated', '--force-run']);
  assert.deepStrictEqual(INSTALLER_ARGS, ['/S', '--updated', '--force-run']);
  assert.strictEqual(spawned[0].opts.detached, true);
  assert.strictEqual(spawned[0].unref, true);
});

test('nothing is spawned before quit fires', async () => {
  const { dir } = folder();
  const file = path.join(dir, 'Zaram-0.1.0-x64.exe');
  fs.writeFileSync(file, BYTES);
  const app = new EventEmitter();
  let quitRequested = false;
  app.quit = () => { quitRequested = true; };
  const spawned = [];
  const installer = createUpdateInstaller({
    app, getBaseUrl: () => 'http://x', getSecret: () => 's', platform: 'win32', env: {},
    schedule: (fn) => fn(),
    spawnImpl: (...a) => { spawned.push(a); return { unref() {} }; },
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ path: file, name: 'Zaram-0.1.0-x64.exe', sha256: SHA }) }),
  });
  await installer.install();
  assert.strictEqual(quitRequested, true);
  assert.strictEqual(spawned.length, 0, 'it must wait for the app to be gone');
  app.emit('quit');
  assert.strictEqual(spawned.length, 1);
});

test('it asks the backend with the launch credential and takes nothing from the renderer', async () => {
  const { installer, asked } = harness();
  assert.strictEqual(installer.install.length, 0, 'install takes no arguments');
  await installer.install();
  assert.deepStrictEqual(asked, [{ url: 'http://127.0.0.1:8420/updates/installer', headers: { 'X-Zaram-Auth': 'launch-secret' } }]);
});

test('a second press while it is on its way does not start a second installer', async () => {
  const { installer, spawned, app } = harness();
  await installer.install();
  const again = await installer.install();
  assert.strictEqual(again.ok, true);
  assert.strictEqual(spawned.length, 1);
  assert.strictEqual(app.quitCalls, 1);
});

for (const [label, deps, reason] of [
  ['a development run', { isDev: true }, /development run/],
  ['a platform other than Windows', { platform: 'linux' }, /only built for Windows/],
  ['the portable build', { env: { PORTABLE_EXECUTABLE_FILE: 'C:/x/Zaram-Portable.exe' } }, /portable build/],
]) {
  test(`it refuses, in words, on ${label}`, async () => {
    const { installer, spawned, asked, app } = harness({ deps });
    const out = await installer.install();
    assert.strictEqual(out.ok, false);
    assert.match(out.reason, reason);
    assert.strictEqual(spawned.length, 0);
    assert.strictEqual(asked.length, 0, 'it did not even ask');
    assert.strictEqual(app.quitCalls, 0);
  });
}

test('nothing downloaded is a plain answer, not an error', async () => {
  const { installer, spawned } = harness({ status: 404 });
  const out = await installer.install();
  assert.strictEqual(out.ok, false);
  assert.match(out.reason, /no downloaded update/);
  assert.strictEqual(spawned.length, 0);
});

test('an unreachable backend is reported and nothing runs', async () => {
  const { installer, spawned } = harness({ deps: { fetchImpl: async () => { throw new Error('connection refused'); } } });
  const out = await installer.install();
  assert.strictEqual(out.ok, false);
  assert.match(out.reason, /connection refused/);
  assert.strictEqual(spawned.length, 0);
});

test('a file that changed after it was checked is not run', async () => {
  const { installer, spawned, file, app } = harness();
  fs.appendFileSync(file, 'tampered');
  const out = await installer.install();
  assert.strictEqual(out.ok, false);
  assert.match(out.reason, /changed on disk/);
  assert.strictEqual(spawned.length, 0);
  assert.strictEqual(app.quitCalls, 0, 'the app was not closed for an update that will not run');
});

test('a file that is gone is reported', async () => {
  const { installer, file, spawned } = harness();
  fs.unlinkSync(file);
  const out = await installer.install();
  assert.strictEqual(out.ok, false);
  assert.match(out.reason, /no longer on disk/);
  assert.strictEqual(spawned.length, 0);
});

for (const [label, info] of [
  ['the portable build', { name: 'Zaram-Portable-0.1.0-x64.exe' }],
  ['a name the build does not produce', { name: 'setup.exe' }],
  ['a name with a path in it', { name: '..\\Zaram-0.1.0-x64.exe' }],
  ['a checksum that is not a checksum', { sha256: 'abc' }],
  ['a path that is not absolute', { path: 'updates/Zaram-0.1.0-x64.exe' }],
  ['a file whose name differs from the one described', { path: path.join(os.tmpdir(), 'updates', 'Zaram-9.9.9-x64.exe') }],
  ['a folder that is not the update folder', { path: path.join(os.tmpdir(), 'Zaram-0.1.0-x64.exe') }],
]) {
  test(`it will not run ${label}`, async () => {
    const { installer, spawned, app } = harness({ info });
    const out = await installer.install();
    assert.strictEqual(out.ok, false);
    assert.strictEqual(spawned.length, 0);
    assert.strictEqual(app.quitCalls, 0);
  });
}

test('the installer name pattern matches the build and not the portable one', () => {
  assert.ok(INSTALLER_NAME.test('Zaram-0.1.0-x64.exe'));
  assert.ok(INSTALLER_NAME.test('Zaram-1.12.3-x64.exe'));
  assert.ok(!INSTALLER_NAME.test('Zaram-Portable-0.1.0-x64.exe'));
  assert.ok(!INSTALLER_NAME.test('Zaram-0.1.0-x64.exe.part'));
  assert.ok(!INSTALLER_NAME.test('evil/Zaram-0.1.0-x64.exe'));
});

test('a refused installer start is logged and does not crash the quit', async () => {
  const logged = [];
  const { installer } = harness({
    deps: {
      logger: { info() {}, warn() {}, error: (m, d) => logged.push([m, d]) },
      spawnImpl: () => { throw new Error('EACCES'); },
    },
  });
  const out = await installer.install();
  assert.strictEqual(out.ok, true);
  assert.strictEqual(logged.length, 1);
  assert.match(logged[0][1].error, /EACCES/);
});
