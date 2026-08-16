'use strict';

const path = require('path');
const { checkHealth } = require('./health');

/**
 * Where the interpreter lives inside a packaged install.
 *
 * Unpacked beside the app rather than inside `app.asar`, because an archived
 * file cannot be executed and a bundled CPython has to be. `extraResources` in
 * `electron-builder.yml` is what puts it here.
 */
const BUNDLED_RUNTIME_DIR = 'runtime';

function bundledPython(root, plat) {
  return plat === 'win32'
    ? path.join(root, BUNDLED_RUNTIME_DIR, 'python.exe')
    : path.join(root, BUNDLED_RUNTIME_DIR, 'bin', 'python3');
}

/**
 * Resolves the Python interpreter to launch the backend.
 *
 * Order: ZARAM_PYTHON -> bundled runtime -> development venv.
 * Kept pure (no child_process import at top level) so it can be unit tested.
 *
 * **A stranger has no Python, and that was the blocker.** This used to look for
 * `ZARAM_PYTHON`, then a `.venv`, then `python` on PATH — three things that
 * exist only on a developer's machine. The packaged app would install
 * correctly and then never start.
 *
 * **PATH is deliberately not a fallback.** Finding *some* Python on a stranger's
 * machine is worse than finding none: it will be the wrong version, without the
 * backend's dependencies, and the failure arrives later and reads as a broken
 * product rather than a missing runtime. Not finding an interpreter is a clear
 * error; finding the wrong one is a confusing one.
 *
 * @param {object} opts
 * @param {string} opts.cwd            backend directory (where main.py lives)
 * @param {string} [opts.resourcesPath] packaged resources dir, if packaged
 * @param {Record<string,string>} [opts.env]
 * @param {string} [opts.platform]
 * @returns {string}
 */
function resolvePythonCommand({ cwd, resourcesPath, env, platform }) {
  const e = env || process.env;
  if (e.ZARAM_PYTHON) return e.ZARAM_PYTHON;

  const plat = platform || process.platform;

  // The bundled runtime wins over any venv. In a packaged install it is the
  // only interpreter present; on a developer machine that has both, shipping
  // behaviour is what should be exercised by default.
  const roots = [resourcesPath, path.join(cwd, '..'), cwd].filter(Boolean);
  for (const root of roots) {
    const candidate = bundledPython(root, plat);
    if (fsExistsSync(candidate)) return candidate;
  }

  const venvLocal = plat === 'win32'
    ? path.join(cwd, '.venv', 'Scripts', 'python.exe')
    : path.join(cwd, '.venv', 'bin', 'python');
  const venvRoot = plat === 'win32'
    ? path.join(cwd, '..', '.venv', 'Scripts', 'python.exe')
    : path.join(cwd, '..', '.venv', 'bin', 'python');
  if (e.ZARAM_VENV && e.ZARAM_VENV !== '1') {
    // allow disabling venv discovery
    return plat === 'win32' ? 'python' : 'python3';
  }
  // Prefer a venv next to main.py, else one at the repo root.
  if (fsExistsSync(venvLocal)) return venvLocal;
  if (fsExistsSync(venvRoot)) return venvRoot;
  return venvLocal;
}

function fsExistsSync(p) {
  try { return realFs().existsSync(p); } catch (_) { return false; }
}

/**
 * A filesystem that cannot see inside `app.asar`.
 *
 * Electron patches `fs` in the main process so archive contents look like
 * ordinary files. That is convenient for `require` and a trap for anything
 * that hands a path to another process: `existsSync` says yes, `spawn` says
 * ENOENT, and the two disagree because only one of them is running inside
 * Electron. `original-fs` is Electron's unpatched copy and is what every check
 * on this path must use — the whole defect lives in the gap between the two.
 *
 * Outside Electron the module is absent and plain `fs` is already unpatched,
 * so the fallback is the same filesystem by a different name.
 */
function realFs() {
  try { return require('original-fs'); } catch (_) { return require('fs'); }
}

/** True for a path that lies inside the archive itself, unpacked tree aside. */
function insideArchive(p) {
  if (typeof p !== 'string') return false;
  return /app\.asar(?!\.unpacked)($|[\\/])/.test(p);
}

/**
 * The same location in the unpacked tree beside the archive.
 *
 * `asarUnpack` in `electron-builder.yml` writes `backend/**` to
 * `resources/app.asar.unpacked/backend`, but `app.getAppPath()` keeps naming
 * the archive. Translating is what connects the two.
 */
function unpackedTwin(p) {
  if (!insideArchive(p)) return p;
  return p.replace(/app\.asar($|[\\/])/, 'app.asar.unpacked$1');
}

function buildArgs() {
  // Launch the backend via its own __main__ so both `backend.main` (package)
  // and the relative `core`/`runtimes` imports resolve regardless of CWD.
  return ['main.py'];
}

/**
 * Launches and supervises the Python backend as a child process, polling its
 * health endpoint and reconnecting on failure. Event-driven: status changes
 * are pushed to subscribers.
 */
class BackendLauncher {
  constructor({ config, logger, spawnImpl, checkHealthImpl, fsImpl, realFsImpl, platform }) {
    this.config = config;
    this.logger = logger || console;
    this._spawn = spawnImpl || require('child_process').spawn;
    this._check = checkHealthImpl || checkHealth;
    this._fs = fsImpl || require('fs');
    // Separate from `_fs` on purpose — see `realFs`. A test injecting one
    // filesystem means it, so an injected `fsImpl` stands in for both unless
    // the test distinguishes them.
    this._realFs = realFsImpl || fsImpl || realFs();
    this._platform = platform || process.platform;
    this.child = null;
    this.status = { state: 'starting', url: config.backend.baseUrl, lastCheckedAt: 0 };
    this._subscribers = new Set();
    this._timer = null;
    this._stopping = false;
    this._restartTimer = null;
  }

  onStatus(cb) {
    this._subscribers.add(cb);
    return () => this._subscribers.delete(cb);
  }

  getStatus() {
    return Object.assign({}, this.status);
  }

  _emit(state, error) {
    this.status = {
      state,
      url: this.config.backend.baseUrl,
      lastCheckedAt: Date.now(),
      error: error || undefined,
    };
    for (const cb of this._subscribers) {
      try { cb(this.getStatus()); } catch (_) { /* ignore subscriber errors */ }
    }
  }

  start() {
    this._stopping = false;
    this._emit('starting');
    this._spawnBackend();
    this._startPolling();
  }

  _venvExists(command) {
    if (command.endsWith('python.exe') || command.endsWith(path.sep + 'python')) {
      try { return this._fs.existsSync(command); } catch (_) { return false; }
    }
    return true;
  }

  /**
   * Where `main.py` lives, as a path another process can actually enter.
   *
   * Two rules, and the first one is the fix for a packaged app that could
   * never start:
   *
   * 1. **A path inside `app.asar` is never returned**, however convincingly it
   *    exists. It exists to Electron and to nothing else, and handing it to
   *    `spawn` as a working directory fails on the cwd rather than on the
   *    command — an ENOENT that names the interpreter and blames the wrong
   *    thing. Each candidate is translated to its unpacked twin first, and the
   *    archive form is then discarded rather than kept as a fallback.
   * 2. **Existence is checked against `original-fs`.** Checking with the
   *    patched `fs` is what made rule 1 necessary and invisible at the same
   *    time.
   */
  _resolveBackendDir() {
    const roots = [
      this.config.appPath,
      process.cwd(),
      this.config.resourcesPath || process.cwd(),
    ].filter(Boolean);

    const candidates = [];
    for (const root of roots) {
      for (const c of [path.join(root, 'backend'), root]) {
        const real = unpackedTwin(c);
        if (insideArchive(real)) continue;
        if (!candidates.includes(real)) candidates.push(real);
      }
    }

    for (const c of candidates) {
      try {
        if (this._realFs.existsSync(path.join(c, 'main.py'))) return c;
      } catch (_) { /* ignore */ }
    }

    // Nothing was found. Return the unpacked location rather than the archive:
    // the spawn will still fail, but it fails naming a path a person can go
    // and look at, which the archive path never was.
    this.logger.error('No backend directory found', { candidates });
    return unpackedTwin(path.join(this.config.appPath, 'backend'));
  }

  _spawnBackend() {
    const backendDir = this._resolveBackendDir();
    const command = resolvePythonCommand({
      cwd: backendDir,
      resourcesPath: this.config.resourcesPath,
      env: process.env,
      platform: this._platform,
    });
    const args = buildArgs();
    this.logger.info('Launching backend', { command, args, cwd: backendDir });

    if (!this._venvExists(command)) {
      const err = `Python interpreter not found at ${command}`;
      this.logger.error(err);
      this._emit('error', err);
      return;
    }

    try {
      this.child = this._spawn(command, args, {
        cwd: backendDir,
        env: Object.assign({}, process.env, { PYTHONUNBUFFERED: '1' }),
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      this.logger.error('Failed to spawn backend', { error: err.message });
      this._emit('error', err.message);
      return;
    }

    if (this.child.stdout) {
      this.child.stdout.on('data', (d) => this.logger.debug('[backend]', { line: String(d).trim().slice(0, 200) }));
    }
    if (this.child.stderr) {
      this.child.stderr.on('data', (d) => this.logger.warn('[backend:err]', { line: String(d).trim().slice(0, 200) }));
    }
    this.child.on('exit', (code, signal) => {
      this.child = null;
      if (this._stopping) return;
      this.logger.warn('Backend process exited', { code, signal });
      this._emit('unavailable', `Backend exited (code=${code}, signal=${signal})`);
      this._scheduleRestart();
    });
    this.child.on('error', (err) => {
      this.logger.error('Backend spawn error', { error: err.message });
      this._emit('error', err.message);
    });
  }

  _scheduleRestart() {
    if (this._stopping || this._restartTimer) return;
    this.logger.info('Scheduling backend restart', { delayMs: this.config.backend.restartDelayMs });
    this._restartTimer = setTimeout(() => {
      this._restartTimer = null;
      if (!this._stopping) this._spawnBackend();
    }, this.config.backend.restartDelayMs);
  }

  /**
   * The credential this launch's backend was started with.
   *
   * Read from `process.env` rather than held as a field: the desktop host sets
   * it before spawning anything, the backend inherits it through the spawn
   * environment, and this reads the same one value. Three copies of a secret
   * are three chances for two of them to differ.
   *
   * Empty when there is none — a developer running the backend by hand, which
   * uses the file fallback instead. Sending no header is then correct, and the
   * request fails with 401 rather than being silently let through.
   */
  _authHeaders() {
    const secret = process.env.ZARAM_API_SECRET || '';
    return secret ? { 'X-Zaram-Auth': secret } : {};
  }

  _startPolling() {
    if (this._timer) return;
    this._timer = setInterval(async () => {
      try {
        // The credential goes on the probe. `/health` is not exempt from
        // authentication, so a probe without it is a 401, which reads here as
        // "the backend never started" — a splash screen for ever, in front of
        // a backend that is running.
        const res = await this._check(
          this.config.backend.baseUrl,
          this.config.backend.healthPath,
          undefined,
          this._authHeaders(),
        );
        console.log('[BackendLauncher] Health check result:', res.ok ? 'OK' : `FAIL(${res.status})`, 'current state:', this.status.state)
        if (res.ok) {
          if (this.status.state !== 'available') {
            console.log('[BackendLauncher] Emitting available')
            this._emit('available')
          }
        } else if (this.status.state === 'available') {
          console.log('[BackendLauncher] Emitting unavailable - status:', res.status)
          this._emit('unavailable', `Health check returned status ${res.status}`);
        }
      } catch (err) {
        console.log('[BackendLauncher] Health check error:', err.message, 'current state:', this.status.state)
        if (this.status.state === 'available') {
          console.log('[BackendLauncher] Emitting unavailable - error')
          this._emit('unavailable', err.message);
        }
      }
    }, this.config.backend.pollIntervalMs);
    if (this._timer.unref) this._timer.unref();
  }

  _stopPolling() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._restartTimer) {
      clearTimeout(this._restartTimer);
      this._restartTimer = null;
    }
  }

  restart() {
    this.logger.info('Manual backend restart requested');
    this._stopPolling();
    if (this.child) {
      try { this.child.kill(); } catch (_) { /* ignore */ }
      this.child = null;
    }
    this._emit('restarting');
    this._spawnBackend();
    this._startPolling();
  }

  stop() {
    this._stopping = true;
    this._stopPolling();
    if (this.child) {
      try {
        this.child.kill();
      } catch (_) {
        /* ignore */
      }
      this.child = null;
    }
  }
}

module.exports = {
  BackendLauncher,
  resolvePythonCommand,
  buildArgs,
  bundledPython,
  BUNDLED_RUNTIME_DIR,
  insideArchive,
  unpackedTwin,
};
