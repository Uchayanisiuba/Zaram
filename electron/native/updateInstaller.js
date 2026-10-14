'use strict';

/**
 * Running the update the backend has already fetched and checked.
 *
 * The backend finds a newer build and downloads it through the egress gate
 * (`backend/core/updates.py`); this is the one step that cannot be done there,
 * because replacing the program means the program has to leave first. So the
 * split is: the backend never starts a program, and this never opens a network
 * connection. It replaced a stub that wrapped `electron-updater` -- a library
 * that makes its own requests from this process, where the egress log cannot see
 * them, which is the reason rule 3 is built the way it is.
 *
 * **The renderer supplies nothing.** `install()` takes no arguments. The path,
 * the name and the checksum all come from the backend's own answer, fetched here
 * with this launch's credential, so a compromised page can at most ask for an
 * installer that was downloaded, verified and is waiting -- which is what the
 * button it would be pressing does anyway.
 *
 * **Checked again before it runs.** The name must be the one the build produces,
 * the file must sit in a folder called `updates`, and its SHA-256 is computed
 * here and compared with the one the backend recorded. The backend already did
 * this once; the file has sat on disk since.
 *
 * **It runs after Zaram has gone.** The installer replaces files the running
 * program holds open -- the bundled Python among them -- so it is started from
 * the `quit` event, which fires once the windows are closed and the backend has
 * been stopped, and detached so it outlives this process. `/S` makes it silent,
 * `--updated` makes the uninstall step of the old version skip its question about
 * the person's data (`build/installer.nsh` guards on exactly that flag, and an
 * update must never ask about deleting them), and `--force-run` starts the new
 * version when it is done. All three are the NSIS template's own; none is ours.
 *
 * Refused, in words, where it cannot work: a development run, a portable build
 * (which cannot replace itself), and anything but Windows.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

/** What the build names its installer. The portable build is `Zaram-Portable-…`. */
const INSTALLER_NAME = /^Zaram-\d+\.\d+\.\d+-x64\.exe$/;
const INSTALLER_ARGS = ['/S', '--updated', '--force-run'];
const FOLDER = 'updates';

function sha256File(file, fsImpl = fs) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = fsImpl.createReadStream(file);
    stream.on('error', reject);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

/**
 * @param {object} o
 * @param {import('electron').App} o.app
 * @param {import('../types').Logger} [o.logger]
 * @param {() => string} o.getBaseUrl   the backend's address
 * @param {() => string} o.getSecret    this launch's API credential
 * @param {boolean} [o.isDev]
 */
function createUpdateInstaller({
  app,
  logger,
  getBaseUrl,
  getSecret,
  isDev = false,
  platform = process.platform,
  env = process.env,
  fetchImpl = (...args) => fetch(...args),
  spawnImpl = spawn,
  fsImpl = fs,
  schedule = (fn) => setImmediate(fn),
}) {
  const log = logger || console;
  let started = false;

  async function install() {
    if (started) return { ok: true, reason: 'already on its way' };
    if (isDev) return { ok: false, reason: 'This is a development run, not an installed copy of Zaram.' };
    if (platform !== 'win32') return { ok: false, reason: 'Installing an update from inside Zaram is only built for Windows.' };
    if (env.PORTABLE_EXECUTABLE_FILE) {
      return { ok: false, reason: 'This is the portable build, which cannot replace itself. Download the new one from the release page.' };
    }

    let info;
    try {
      const response = await fetchImpl(`${getBaseUrl()}/updates/installer`, { headers: { 'X-Zaram-Auth': getSecret() } });
      if (response.status === 404) return { ok: false, reason: 'There is no downloaded update ready to install.' };
      if (!response.ok) return { ok: false, reason: `Zaram could not ask for the update (${response.status}).` };
      info = await response.json();
    } catch (err) {
      return { ok: false, reason: `Zaram could not ask for the update: ${err.message}` };
    }

    const file = info && typeof info.path === 'string' ? info.path : '';
    const name = info && typeof info.name === 'string' ? info.name : '';
    const wanted = info && typeof info.sha256 === 'string' ? info.sha256.toLowerCase() : '';
    if (!INSTALLER_NAME.test(name) || !path.isAbsolute(file) || path.basename(file) !== name
        || path.basename(path.dirname(file)) !== FOLDER || !/^[0-9a-f]{64}$/.test(wanted)) {
      log.warn('Update installer refused: unexpected description', { name });
      return { ok: false, reason: 'The downloaded update did not look the way Zaram expects, so it was not run.' };
    }
    if (!fsImpl.existsSync(file)) return { ok: false, reason: 'The downloaded update is no longer on disk. Download it again.' };

    let actual;
    try {
      actual = await sha256File(file, fsImpl);
    } catch (err) {
      return { ok: false, reason: `The downloaded update could not be read: ${err.message}` };
    }
    if (actual !== wanted) {
      log.warn('Update installer refused: checksum differs');
      return { ok: false, reason: 'The downloaded update changed on disk after it was checked, so it was not run. Download it again.' };
    }

    started = true;
    app.once('quit', () => {
      try {
        const child = spawnImpl(file, INSTALLER_ARGS, { detached: true, stdio: 'ignore' });
        if (child && typeof child.unref === 'function') child.unref();
      } catch (err) {
        log.error('Could not start the update installer', { error: err.message });
      }
    });
    log.info('Update: quitting so the installer can replace this version', { name });
    schedule(() => app.quit());
    return { ok: true };
  }

  return { install };
}

module.exports = { createUpdateInstaller, INSTALLER_NAME, INSTALLER_ARGS, sha256File };
