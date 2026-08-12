/**
 * Refuse to ship an installer with no Python in it.
 *
 * The failure this prevents is the quietest one in the whole packaging story:
 * `extraResources` silently skips a directory that is not there, so a release
 * built without `runtime/` packages cleanly, installs cleanly, and then never
 * starts — on someone else's machine, where the reason is invisible.
 *
 * A development build without a runtime is fine and normal: the launcher falls
 * back to the repo venv. So this only refuses under ZARAM_RELEASE=1, the same
 * switch `check-signing.mjs` uses.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RUNTIME = path.join(ROOT, 'runtime');
const PYTHON = path.join(RUNTIME, 'python.exe');

const isRelease = process.env.ZARAM_RELEASE === '1';

function fail(lines) {
  console.error(`\n${lines.join('\n')}\n`);
  process.exit(1);
}

if (!fs.existsSync(PYTHON)) {
  if (!isRelease) {
    console.log(
      'check:runtime — no bundled runtime; development build will use the repo venv.',
    );
    process.exit(0);
  }
  fail([
    '  ZARAM_RELEASE=1 but there is no Python runtime to ship.',
    '',
    `  Expected an interpreter at ${path.relative(ROOT, PYTHON)}.`,
    '',
    '  electron-builder skips a missing extraResources directory without',
    '  complaining, so this build would install correctly and then fail to',
    '  start on any machine that does not already have Python — which is every',
    '  machine that is not this one.',
    '',
    '  Build it first:  npm run build:runtime',
  ]);
}

// Present. Check it is a real install rather than a half-finished download.
const required = ['Lib', 'DLLs'];
const missing = required.filter((d) => !fs.existsSync(path.join(RUNTIME, d)));
if (missing.length > 0) {
  fail([
    `  The runtime at ${path.relative(ROOT, RUNTIME)} is incomplete: missing ${missing.join(', ')}.`,
    '',
    '  A partial runtime is worse than none — it looks present and fails at',
    '  import time. Rebuild it: npm run build:runtime',
  ]);
}

// The backend's own entrypoint has to be importable, which means its
// dependencies have to be installed into *this* interpreter, not the venv.
const sitePackages = path.join(RUNTIME, 'Lib', 'site-packages');
const sentinels = ['fastapi', 'uvicorn', 'pydantic'];
const absent = sentinels.filter((p) => !fs.existsSync(path.join(sitePackages, p)));
if (absent.length > 0) {
  fail([
    `  The runtime has no ${absent.join(', ')} installed.`,
    '',
    '  The interpreter shipped but its dependencies did not, so the backend',
    '  would fail on its first import. Rebuild it: npm run build:runtime',
  ]);
}

console.log('check:runtime — bundled runtime present, with backend dependencies.');
