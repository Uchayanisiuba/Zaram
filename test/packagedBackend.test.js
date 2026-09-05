'use strict';

/**
 * Does the backend inside a *built* Zaram start?
 *
 * `backendLauncher.test.js` asserts the resolution rules against fabricated
 * install layouts, and `scripts/check-installer-payload.mjs` asserts the
 * packaging config. Both passed while the packaged product could not start,
 * because neither of them looks at a build. This one does.
 *
 * **Two things make it the test that could have caught it.**
 *
 * It runs in plain Node rather than in Electron. Electron's patched `fs` reads
 * an asar transparently, which is exactly what hid the defect: the launcher's
 * existence check said the backend was there — that check runs in Electron —
 * and the spawned `python.exe`, an ordinary Windows process with an ordinary
 * `fs`, could not reach it at all. Plain Node sees what python.exe sees.
 *
 * And it chdirs somewhere that is not a checkout. `_resolveBackendDir` lists
 * `process.cwd()` among its roots, so a test running from C:\Zaram finds
 * `C:\Zaram\backend` and proves nothing about an installed copy. Every machine
 * that could have found this bug was standing in the one directory that hides
 * it.
 *
 * **A skip here is a finding, not a pass.** It means no build exists to look
 * at, so the single acceptance criterion that has never been met is still not
 * met. Build one with::
 *
 *     npm run build:desktop -- --config.win.signAndEditExecutable=false
 *
 * It is still not the whole criterion. Running the installer on a machine that
 * has never seen this repository also exercises NSIS, the shortcut, the data
 * directory under %APPDATA% and first run. This covers the part that was
 * actually broken.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

const {
  BackendLauncher,
  resolvePythonCommand,
} = require('../electron/backend/backendLauncher');

const UNPACKED = path.join(__dirname, '..', 'dist-electron', 'win-unpacked');
const RESOURCES = path.join(UNPACKED, 'resources');

const NO_BUILD =
  'no build to inspect — dist-electron/win-unpacked is absent, so whether a ' +
  'packaged Zaram can start its backend is still unmeasured. Build with ' +
  '`npm run build:desktop -- --config.win.signAndEditExecutable=false`.';

const built = fs.existsSync(RESOURCES);

/** A launcher pointed at the build, from a directory that is not a checkout. */
function launcherOverBuild() {
  return new BackendLauncher({
    config: {
      appPath: path.join(RESOURCES, 'app.asar'),
      resourcesPath: RESOURCES,
      backend: {},
    },
    logger: { info() {}, warn() {}, error() {}, debug() {} },
  });
}

/**
 * Run `fn` with the process standing somewhere unrelated to this repository.
 *
 * Restoring the previous directory matters more than it looks: `node --test`
 * runs files in one process, and a leaked chdir would make every later test
 * resolve its fixtures against a temporary directory.
 */
function fromOutsideTheRepo(fn) {
  const before = process.cwd();
  const elsewhere = fs.mkdtempSync(path.join(os.tmpdir(), 'not-a-checkout-'));
  try {
    process.chdir(elsewhere);
    return fn(elsewhere);
  } finally {
    process.chdir(before);
    try {
      fs.rmSync(elsewhere, { recursive: true, force: true });
    } catch (_) {
      /* a temp directory that outlives the test is not a failure */
    }
  }
}

test('packaged: the backend is on the filesystem, not sealed in app.asar', { skip: built ? false : NO_BUILD }, () => {
  fromOutsideTheRepo(() => {
    const dir = launcherOverBuild()._resolveBackendDir();

    assert.ok(
      !dir.includes(`app.asar${path.sep}`),
      `resolved a path inside the archive, which python.exe cannot read: ${dir}`,
    );
    // Plain `fs`, deliberately. This is the assertion that was true in Electron
    // and false everywhere else for the entire life of the packaged build.
    assert.ok(
      fs.existsSync(path.join(dir, 'main.py')),
      `main.py is not readable by a non-Electron process at ${dir}`,
    );
  });
});

test('packaged: the bundled interpreter is what gets chosen', { skip: built ? false : NO_BUILD }, () => {
  fromOutsideTheRepo(() => {
    const dir = launcherOverBuild()._resolveBackendDir();
    const python = resolvePythonCommand({
      cwd: dir,
      resourcesPath: RESOURCES,
      // Empty rather than `process.env`: ZARAM_PYTHON on a developer machine
      // would silently substitute a different interpreter and the test would
      // pass while proving nothing about what ships.
      env: {},
      platform: 'win32',
    });

    assert.ok(
      python.startsWith(RESOURCES),
      `chose an interpreter from outside the install: ${python}`,
    );
    assert.ok(fs.existsSync(python), `bundled interpreter missing at ${python}`);
  });
});

test('packaged: that interpreter can import main.py with that cwd', { skip: built ? false : NO_BUILD }, () => {
  fromOutsideTheRepo(() => {
    const dir = launcherOverBuild()._resolveBackendDir();
    const python = resolvePythonCommand({
      cwd: dir,
      resourcesPath: RESOURCES,
      env: {},
      platform: 'win32',
    });

    // The original failure was ENOENT on the *working directory*, not on the
    // interpreter, which is why the error message named neither. So the thing
    // worth asserting is that a process starts with this cwd and can reach the
    // backend's own entry module from it.
    const probe = spawnSync(
      python,
      ['-c', 'import os, sys; sys.path.insert(0, os.getcwd()); import main; print("ok")'],
      { cwd: dir, encoding: 'utf8', timeout: 180000, env: { ...process.env, PYTHONUNBUFFERED: '1' } },
    );

    assert.strictEqual(
      probe.error && probe.error.code,
      undefined,
      `spawn failed: ${probe.error && probe.error.message}`,
    );
    assert.strictEqual(
      probe.status,
      0,
      `backend entry did not import.\nstdout: ${probe.stdout}\nstderr: ${probe.stderr}`,
    );
    assert.match(probe.stdout, /\bok\b/);
  });
});
