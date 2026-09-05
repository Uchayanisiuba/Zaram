'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { createConfig } = require('../electron/config');
const {
  BackendLauncher,
  resolvePythonCommand,
  buildArgs,
  bundledPython,
  insideArchive,
  unpackedTwin,
} = require('../electron/backend/backendLauncher');

function fakeChild() {
  const c = new EventEmitter();
  c.stdout = new EventEmitter();
  c.stderr = new EventEmitter();
  c.kill = () => c.emit('exit', 0, null);
  return c;
}

test('resolvePythonCommand: defaults to project venv', () => {
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: {}, platform: 'win32' }),
    path.join('/app', '.venv', 'Scripts', 'python.exe'),
  );
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: {}, platform: 'linux' }),
    path.join('/app', '.venv', 'bin', 'python'),
  );
});

/**
 * A throwaway install layout on disk. Resolution is filesystem-dependent, and
 * a mocked `existsSync` would only prove the mock agrees with itself.
 */
function fakeInstall({ runtime = false, platform = 'win32' }) {
  const fs = require('node:fs');
  const os = require('node:os');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-runtime-'));
  const backendDir = path.join(root, 'backend');
  fs.mkdirSync(backendDir, { recursive: true });
  fs.writeFileSync(path.join(backendDir, 'main.py'), '');

  if (runtime) {
    const exe = bundledPython(root, platform);
    fs.mkdirSync(path.dirname(exe), { recursive: true });
    fs.writeFileSync(exe, '');
  }
  return { root, backendDir, cleanup: () => fs.rmSync(root, { recursive: true, force: true }) };
}

test('resolvePythonCommand: prefers the bundled runtime', () => {
  // The whole point of M11's runtime work: a machine with no Python still has
  // an interpreter, because the installer brought one.
  const { root, backendDir, cleanup } = fakeInstall({ runtime: true });
  try {
    assert.strictEqual(
      resolvePythonCommand({ cwd: backendDir, env: {}, platform: 'win32' }),
      bundledPython(root, 'win32'),
    );
  } finally {
    cleanup();
  }
});

test('resolvePythonCommand: finds the runtime via resourcesPath when packaged', () => {
  const { root, backendDir, cleanup } = fakeInstall({ runtime: true });
  try {
    // In a packaged app the backend sits inside app.asar while the runtime is
    // unpacked beside it, so the only path that reaches it is resourcesPath.
    assert.strictEqual(
      resolvePythonCommand({
        cwd: path.join(root, 'app.asar', 'backend'),
        resourcesPath: root,
        env: {},
        platform: 'win32',
      }),
      bundledPython(root, 'win32'),
    );
  } finally {
    cleanup();
  }
});

test('resolvePythonCommand: never falls back to PATH when nothing is found', () => {
  // Finding some stranger's Python 3.9 is worse than finding none: it is the
  // wrong version, it lacks the backend's dependencies, and it fails later in
  // a way that reads as a broken product rather than a missing runtime.
  const { backendDir, cleanup } = fakeInstall({ runtime: false });
  try {
    const resolved = resolvePythonCommand({ cwd: backendDir, env: {}, platform: 'win32' });
    assert.notStrictEqual(resolved, 'python');
    assert.notStrictEqual(resolved, 'python3');
    assert.ok(
      path.isAbsolute(resolved),
      `expected an absolute path so the failure names a location, got ${resolved}`,
    );
  } finally {
    cleanup();
  }
});

test('resolvePythonCommand: honors ZARAM_PYTHON', () => {
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: { ZARAM_PYTHON: '/usr/bin/python3' }, platform: 'linux' }),
    '/usr/bin/python3',
  );
});

test('buildArgs: launches the backend through its own entrypoint', () => {
  // The launcher used to invoke uvicorn directly with an explicit
  // `--host 127.0.0.1`. It now runs `main.py`, so that both `backend.main` and
  // the relative `core`/`runtimes` imports resolve regardless of CWD.
  assert.deepStrictEqual(buildArgs(8420), ['main.py']);
});

test('buildArgs: never asks the backend to listen beyond loopback', () => {
  // **This assertion is the one that was lost, and losing it cost a real bug.**
  //
  // The previous version of this test hardcoded the full uvicorn argument list
  // including `--host 127.0.0.1`. When the launcher changed to `main.py` the
  // test began failing — and nothing in this repo ran it, because there was no
  // script wired to `test/`. The loopback binding then quietly moved into
  // `main.py`, where it was written as `0.0.0.0`: every network interface, on
  // an API with no authentication.
  //
  // So this asserts the *property* rather than the argument list. It holds
  // whether the launcher runs `main.py` or goes back to invoking uvicorn, which
  // is what the old test could not do. The binding inside `main.py` is asserted
  // separately by `backend/tests/test_backend_binds_loopback_only.py`; between
  // the two there is no way to open the port to a network without a test
  // objecting.
  const args = buildArgs(8420);
  const hostFlag = args.indexOf('--host');
  if (hostFlag !== -1) {
    const host = args[hostFlag + 1];
    assert.ok(
      host === '127.0.0.1' || host === 'localhost' || host === '::1',
      `launcher would bind ${host}, which is reachable from other machines`,
    );
  }
  for (const arg of args) {
    assert.ok(
      !String(arg).includes('0.0.0.0'),
      `launcher argument ${arg} would bind every network interface`,
    );
  }
});

test('BackendLauncher: transitions to available when health ok', async () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  cfg.backend.pollIntervalMs = 5;
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => true },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'available') resolve(s); });
    launcher.start();
  });
  assert.strictEqual(got.state, 'available');
  launcher.stop();
});

test('BackendLauncher: reports error when interpreter missing', async () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => false },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'error') resolve(s); });
    launcher.start();
  });
  assert.strictEqual(got.state, 'error');
  launcher.stop();
});

// --------------------------------------------------------------------------
// The archive boundary.
//
// A path inside `app.asar` exists to Electron's patched `fs` and to nothing
// else on the machine. The packaged app resolved its backend directory to
// exactly such a path, passed the existence check because that check runs in
// Electron, and then handed it to `spawn` as a working directory — which
// failed with ENOENT on the cwd while naming the interpreter.
//
// Every machine holding a checkout fell through to `process.cwd()/backend`
// and worked, so the defect was invisible to everyone who could have seen it.
// These tests fail if a backend directory inside the archive is ever
// selectable again.
// --------------------------------------------------------------------------

test('insideArchive: the archive is inside, the unpacked tree beside it is not', () => {
  assert.ok(insideArchive('/r/resources/app.asar'));
  assert.ok(insideArchive('/r/resources/app.asar/backend'));
  assert.ok(insideArchive('C:\\r\\resources\\app.asar\\backend'));

  assert.ok(!insideArchive('/r/resources/app.asar.unpacked/backend'));
  assert.ok(!insideArchive('C:\\r\\resources\\app.asar.unpacked\\backend'));
  // A directory that merely starts with the same letters is not the archive.
  assert.ok(!insideArchive('/r/app.asarge/backend'));
  assert.ok(!insideArchive('/home/me/zaram/backend'));
});

test('unpackedTwin: translates the archive path, leaves everything else alone', () => {
  assert.strictEqual(
    unpackedTwin('/r/resources/app.asar/backend'),
    '/r/resources/app.asar.unpacked/backend',
  );
  assert.strictEqual(
    unpackedTwin('C:\\r\\resources\\app.asar\\backend'),
    'C:\\r\\resources\\app.asar.unpacked\\backend',
  );
  assert.strictEqual(unpackedTwin('/home/me/zaram/backend'), '/home/me/zaram/backend');
  // Idempotent — translating twice must not produce `app.asar.unpacked.unpacked`.
  const once = unpackedTwin('/r/resources/app.asar/backend');
  assert.strictEqual(unpackedTwin(once), once);
});

test('BackendLauncher: never spawns with a working directory inside app.asar', () => {
  // The filesystem Electron would present: everything exists, including the
  // archive interior. This is precisely the lie that hid the defect.
  const everythingExists = { existsSync: () => true };
  const cfg = createConfig({
    isDev: false,
    appPath: path.join('/r', 'resources', 'app.asar'),
    userDataPath: '/data',
  });
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: everythingExists,
    realFsImpl: everythingExists,
    platform: 'linux',
  });

  const dir = launcher._resolveBackendDir();
  assert.ok(
    !insideArchive(dir),
    `resolved ${dir}, which no process outside Electron can enter`,
  );
  assert.strictEqual(dir, path.join('/r', 'resources', 'app.asar.unpacked', 'backend'));
});

test('BackendLauncher: falls back to a real path, not the archive, when nothing is found', () => {
  const nothingExists = { existsSync: () => false };
  const cfg = createConfig({
    isDev: false,
    appPath: path.join('/r', 'resources', 'app.asar'),
    userDataPath: '/data',
  });
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: nothingExists,
    realFsImpl: nothingExists,
    logger: { info() {}, warn() {}, error() {}, debug() {} },
    platform: 'linux',
  });

  assert.ok(!insideArchive(launcher._resolveBackendDir()));
});

test('BackendLauncher: child exit triggers unavailable and reconnect attempt', async () => {
  let spawned = 0;
  const spawnImpl = () => { spawned += 1; return fakeChild(); };
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  cfg.backend.pollIntervalMs = 5;
  cfg.backend.restartDelayMs = 100000; // keep the test fast
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl,
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => true },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'unavailable') resolve(s); });
    launcher.start();
    setTimeout(() => { if (launcher.child) launcher.child.emit('exit', 1, 'SIGTERM'); }, 20);
  });
  assert.strictEqual(got.state, 'unavailable');
  launcher.stop();
});
