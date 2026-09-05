'use strict';

/**
 * The shipped main process boots.
 *
 * Nothing in this repository had ever run `electron/main.js`. The suite
 * requires modules from it and asserts their behaviour in isolation, and
 * `npm run dev` starts a **different** main process — `desktop/`'s, which is
 * forty-six lines and owns none of the tray, shortcuts, backend launcher or
 * static server. So the file that every installed copy of Zaram runs was the
 * one file no check ever executed.
 *
 * What that cost: `windows._mainWindow.on('resize', …)` — a property
 * `WindowManager` has never had — threw inside `bootstrap()`, whose only
 * handler logs the message. Everything below the throw never ran, including
 * `backend.start()`. The application opened a splash screen and waited for a
 * backend nobody had launched, for ever. Every unit test passed throughout.
 *
 * The test is a smoke test on purpose. It asserts that bootstrap reaches its
 * last line, and nothing about what the app looks like. That is a low bar and
 * it is precisely the bar that was not being cleared.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const ROOT = path.join(__dirname, '..');
const ELECTRON = path.join(
  ROOT, 'node_modules', 'electron', 'dist',
  process.platform === 'win32' ? 'electron.exe' : 'electron',
);

/**
 * Electron needs a desktop session. On a headless runner it cannot start at
 * all, and a test that fails for want of a display teaches nobody anything —
 * so it says what is unproven rather than going red.
 */
/**
 * The environment for a real Electron run.
 *
 * `ELECTRON_RUN_AS_NODE` has to be **deleted**, not blanked. Electron tests for
 * the variable's presence rather than its value, so setting it to `''` still
 * re-execs as plain Node — where `app` is undefined and `main.js` dies on its
 * twenty-second line with a message about `isPackaged` that has nothing to do
 * with anything. `desktop/start-electron.js` deletes it for the same reason.
 */
function electronEnv() {
  const env = { ...process.env, ZARAM_SMOKE: '1' };
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}

const CANNOT_RUN =
  !fs.existsSync(ELECTRON)
    ? 'no Electron binary in node_modules — the shipped main process is unproven'
    : process.env.CI
      ? 'headless CI has no desktop session; run locally to prove the app boots'
      : false;

/**
 * Launch the real main process and return everything it said.
 *
 * Resolves as soon as the run has settled either way — the smoke line or the
 * bootstrap error — rather than waiting for exit. That matters because the
 * failure mode is precisely that the app *does not* exit: when `bootstrap`
 * throws, the window stays open and waits for a backend nobody started, so a
 * test that waits for exit takes the full timeout to report a fault it could
 * see in a second.
 *
 * The timeout stays as the backstop for a hang with no message at all, which
 * is the one case neither line covers.
 */
function boot() {
  return new Promise((resolve, reject) => {
    const child = spawn(ELECTRON, [path.join('electron', 'main.js')], {
      cwd: ROOT,
      env: electronEnv(),
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let text = '';
    let settled = false;

    const finish = (fn, arg) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (!child.killed) child.kill();
      fn(arg);
    };

    const read = (d) => {
      text += d;
      if (/Smoke: bootstrap reached the end|Bootstrap failed/.test(text)) {
        finish(resolve, text);
      }
    };

    child.stdout.on('data', read);
    child.stderr.on('data', read);

    // Generous, because bootstrap constructs the whole desktop runtime.
    const timer = setTimeout(
      () => finish(reject, new Error(`bootstrap said nothing in 90s.\n${text.slice(-2000)}`)),
      90_000,
    );

    child.on('error', (err) => finish(reject, err));
    child.on('exit', () => finish(resolve, text));
  });
}

test('the shipped main process reaches the end of bootstrap', { skip: CANNOT_RUN }, async () => {
  const output = await boot();

  assert.doesNotMatch(
    output,
    /Bootstrap failed/,
    `bootstrap threw, so everything after the throw — including backend.start() — did not run.\n${output.slice(-2000)}`,
  );
  assert.match(
    output,
    /Smoke: bootstrap reached the end/,
    `bootstrap never reached its last line.\n${output.slice(-2000)}`,
  );
});

/**
 * And the ambient surface is part of that boot.
 *
 * Asserted from the same run rather than a second launch: the accelerator
 * registering is the one fact about the overlay that cannot be checked from a
 * unit test, because it depends on whether another application on this machine
 * already owns the key.
 *
 * `registered: false` is a legitimate outcome — something else holds the
 * combination — so the assertion is that the surface *started and reported*,
 * not that it won the key. The line being absent means it never ran at all,
 * which is the failure worth catching.
 */
test('the ambient surface starts during bootstrap', { skip: CANNOT_RUN }, async () => {
  const output = await boot();

  assert.match(output, /"msg":"Ambient surface"/, `the overlay never started.\n${output.slice(-2000)}`);
  // The handle's real geometry, read back off the window rather than assumed.
  // A window manager that overrules a 6px request would show up here.
  const geometry = /"handle":\{[^}]*"width":(\d+)/.exec(output);
  assert.ok(geometry, `the overlay did not report its handle geometry.\n${output.slice(-1500)}`);
  assert.ok(
    Number(geometry[1]) <= 16,
    `the edge handle was created ${geometry[1]}px wide — a slab, not a hairline, ` +
      'over whatever the user is working in.',
  );
});
