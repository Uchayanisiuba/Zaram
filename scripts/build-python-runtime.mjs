/**
 * Assemble the Python runtime that ships inside Zaram.
 *
 * **This is the blocker M11 exists for.** A stranger has no Python, no venv and
 * no `pip`. Until the installer carries an interpreter, the packaged app
 * installs correctly and then never starts — every other v1 item is
 * unverifiable in the form a user will actually meet it.
 *
 * ## Why a relocatable CPython, and not PyInstaller
 *
 * PyInstaller freezes the interpreter and the dependency set into one bundle.
 * It would be smaller and it is the obvious choice, and it is ruled out by a
 * decision the product has already made and already tells users about:
 *
 *     backend/ingest/quality.py:
 *       "Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time)."
 *
 * Voice, microphone and OCR are optional extras that the user installs *after*
 * the product is running, on the product's own instruction. You cannot
 * `pip install` into a frozen bundle. Choosing PyInstaller would silently
 * break three documented features and turn a user-facing remedy into a lie.
 *
 * So the runtime is a real, relocatable CPython that `pip` works against.
 *
 * ## What this script does
 *
 * 1. Downloads a standalone CPython build matching the version in .python-version
 * 2. Verifies its SHA-256 against the checksum published beside it
 * 3. Extracts it to `runtime/`
 * 4. Installs `backend/requirements.txt` into it — base only, no dev tooling,
 *    no voice, no OCR
 * 5. Prints the resulting size, because that number is the installer
 *
 * Re-runnable. Deletes `runtime/` first, so a half-finished attempt cannot
 * leave a runtime that is missing packages but looks present — which would
 * fail later, at import time, on a user's machine.
 *
 * ## What it deliberately does not do
 *
 * It does not verify a signature, because these builds do not publish one; the
 * checksum protects against corruption and a substituted file at the URL, not
 * against a compromised publisher. That is a real limit and is stated rather
 * than papered over — see docs/CODE-SIGNING.md for the same distinction
 * applied to Zaram's own output.
 */
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RUNTIME_DIR = path.join(ROOT, 'runtime');
const DOWNLOAD_DIR = path.join(ROOT, '.runtime-download');

/**
 * python-build-standalone, the distribution `uv` and Rye use.
 *
 * Pinned by exact release rather than "latest": a runtime that changes under
 * you between builds is a dependency you did not choose, and the installer is
 * the one artifact where reproducibility is worth the maintenance.
 */
const PYTHON_VERSION = '3.11.9';
const RELEASE = '20240726';
const ASSET = `cpython-${PYTHON_VERSION}+${RELEASE}-x86_64-pc-windows-msvc-install_only.tar.gz`;
const BASE_URL = `https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE}`;

function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (res.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} exited ${res.status}`);
  }
}

function sha256(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

async function download(url, dest, { cached = false } = {}) {
  // Retries are normal here — extraction and pip both fail for local reasons —
  // and refetching 41 MB each time is a tax on every one of them.
  if (cached && fs.existsSync(dest)) {
    console.log(`  reusing ${path.basename(dest)} (${(fs.statSync(dest).size / 1e6).toFixed(1)} MB)`);
    return dest;
  }
  process.stdout.write(`  fetching ${path.basename(dest)} … `);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(dest, buf);
  console.log(`${(buf.length / 1e6).toFixed(1)} MB`);
  return dest;
}

function dirSize(dir) {
  let total = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) total += dirSize(full);
    else {
      try {
        total += fs.statSync(full).size;
      } catch {
        /* vanished mid-walk */
      }
    }
  }
  return total;
}

async function main() {
  console.log(`Building the Zaram Python runtime (CPython ${PYTHON_VERSION}).\n`);

  // A partial runtime is worse than none: it looks present and fails at import
  // time, on someone else's machine.
  fs.rmSync(RUNTIME_DIR, { recursive: true, force: true });
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

  const archive = path.join(DOWNLOAD_DIR, ASSET);
  await download(`${BASE_URL}/${ASSET}`, archive, { cached: true });

  const sumsFile = path.join(DOWNLOAD_DIR, `${ASSET}.sha256`);
  await download(`${BASE_URL}/${ASSET}.sha256`, sumsFile, { cached: true });

  const expected = fs.readFileSync(sumsFile, 'utf8').trim().split(/\s+/)[0];
  const actual = sha256(archive);
  if (expected !== actual) {
    throw new Error(
      `checksum mismatch for ${ASSET}\n  expected ${expected}\n  actual   ${actual}`,
    );
  }
  console.log(`  checksum ok (${actual.slice(0, 16)}…)\n`);

  console.log('  extracting …');
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  // The archive contains a top-level `python/`; strip it so the interpreter
  // lands at runtime/python.exe, which is what resolvePythonCommand expects.
  //
  // **Relative paths, run from the repo root.** GNU tar — which is what Git for
  // Windows puts on PATH — reads an argument containing a colon as `host:path`
  // and tries to open an SSH connection, so `-xzf C:\Zaram\…` fails with
  // "Cannot connect to C: resolve failed". Windows' own bsdtar does not, so
  // which tar answers decides whether the build works. Relative paths have no
  // colon and are unambiguous to both.
  run(
    'tar',
    [
      '-xzf', path.relative(ROOT, archive),
      '-C', path.relative(ROOT, RUNTIME_DIR),
      '--strip-components=1',
    ],
    { cwd: ROOT },
  );

  const python = path.join(RUNTIME_DIR, 'python.exe');
  if (!fs.existsSync(python)) {
    throw new Error(`no interpreter at ${python} after extraction`);
  }

  console.log('\n  installing backend/requirements.txt (base only) …');
  run(python, [
    '-m', 'pip', 'install',
    '--no-warn-script-location',
    '-r', path.join(ROOT, 'backend', 'requirements.txt'),
  ]);

  fs.rmSync(DOWNLOAD_DIR, { recursive: true, force: true });

  const size = dirSize(RUNTIME_DIR);
  console.log(`\nRuntime ready: ${RUNTIME_DIR}`);
  console.log(`Size: ${(size / 1e6).toFixed(0)} MB — this is the installer's floor.`);
  console.log('\nVerify it actually runs before trusting it:');
  console.log('  runtime\\python.exe backend\\main.py');
}

main().catch((err) => {
  console.error(`\n  ${err.message}\n`);
  process.exit(1);
});
