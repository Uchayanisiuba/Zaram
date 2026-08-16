/**
 * Refuse to package the user's own data.
 *
 * `electron-builder.yml` used to include the backend as one glob with a few
 * exclusions after it, and the exclusions were wrong in the only direction
 * that matters. `!backend/.venv` does not match `backend/venv`, which is what
 * the directory is called on a working machine — 376 MB. And nothing at all
 * excluded `spine.db`, `egress.db`, `artifacts.db`, `projects.db`,
 * `egress-policy.json` or `backend/generated/`: the maintainer's memory, their
 * append-only record of everything that has ever left their machine, their
 * generated invoices, and their per-host privacy rules. Every one of those
 * files is on disk right now, and every one matched the include glob.
 *
 * Shipping them to a stranger is the precise failure this product exists to
 * prevent, and nothing would have said so.
 *
 * The config is an allow-list now, and `backend/tests/test_installer_payload.py`
 * asserts it stays one. That test runs in the suite and uses `fnmatch`, which
 * is an approximation of the real matcher; **this is the gate that uses the
 * real one.** It reads the actual config and applies the same `minimatch`
 * electron-builder depends on, immediately before packaging, and exits non-zero
 * rather than letting a build proceed.
 *
 * Runs as part of `npm run build:desktop`. Failing the build is the point: a
 * warning printed into a build log is a thing nobody reads until afterwards,
 * and afterwards is too late for a file that has already been published.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';
// minimatch 5 is CommonJS, so the named export is not reachable from ESM.
import minimatchPkg from 'minimatch';

const minimatch = minimatchPkg.minimatch ?? minimatchPkg;

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** Anything matching these must never reach an installer. */
const FORBIDDEN = [
  { pattern: /\.(db|db-wal|db-shm|sqlite|sqlite3)$/i, why: 'a database — the Spine, the egress log, artifacts or projects' },
  { pattern: /(^|\/)venv\//i, why: 'a virtualenv' },
  { pattern: /(^|\/)\.venv\//i, why: 'a virtualenv' },
  { pattern: /(^|\/)generated\//i, why: 'a document the user generated' },
  { pattern: /egress-policy\.json$/i, why: "the user's per-host privacy rules" },
  { pattern: /\.(docx|xlsx|pptx|pdf)$/i, why: 'a user document' },
  { pattern: /(^|\/)uploads\//i, why: 'a file the user ingested' },
];

const MATCH = { dot: true };
const PRUNE = new Set(['node_modules', '__pycache__']);

function readConfig() {
  const file = path.join(ROOT, 'electron-builder.yml');
  const cfg = yaml.load(fs.readFileSync(file, 'utf8'));
  const entries = (cfg.files ?? []).map(String);
  return {
    includes: entries.filter((e) => !e.startsWith('!')),
    excludes: entries.filter((e) => e.startsWith('!')).map((e) => e.slice(1)),
    asar: cfg.asar !== false,
    asarUnpack: (cfg.asarUnpack ?? []).map(String),
  };
}

/** True when `rel`, or any directory above it, matches one of `patterns`. */
function matches(rel, patterns) {
  const parts = rel.split('/');
  for (const p of patterns) {
    if (minimatch(rel, p, MATCH)) return true;
    for (let i = 1; i < parts.length; i += 1) {
      if (minimatch(parts.slice(0, i).join('/'), p, MATCH)) return true;
    }
  }
  return false;
}

function walk(dir, out) {
  let items;
  try {
    items = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const item of items) {
    const full = path.join(dir, item.name);
    const rel = path.relative(ROOT, full).split(path.sep).join('/');
    if (item.isDirectory()) {
      if (PRUNE.has(item.name)) continue;
      out.dirs.push(rel);
      walk(full, out);
    } else {
      out.files.push(rel);
    }
  }
}

const { includes, excludes, asar, asarUnpack } = readConfig();

// The backend must be reachable by a process that is not Electron.
//
// This check exists because the previous one could not see the defect it was
// written to prevent. It graded what the globs *include*, and the backend was
// included — sealed inside `app.asar`, where the main process reads it happily
// and the spawned `python.exe` cannot reach it at all. The installer built,
// the payload was correct, and the product could not start on any machine
// without a checkout of this repo.
//
// An archive is fine for JavaScript that Electron itself loads. It is never
// fine for something handed to another program.
if (asar && !asarUnpack.some((p) => minimatch('backend/main.py', p, MATCH))) {
  console.error(
    '\n  The backend would be sealed inside app.asar.\n' +
      '  Electron can read an asar; a spawned python.exe cannot — it fails\n' +
      '  with ENOENT on the working directory and blames the interpreter.\n' +
      '  Add `asarUnpack: ["backend/**"]` to electron-builder.yml.\n',
  );
  process.exit(1);
}

if (includes.includes('backend')) {
  console.error(
    '\n  electron-builder.yml includes the whole backend directory.\n' +
      '  That is what made every database and generated document a default.\n' +
      '  List what the backend needs instead — see the comment in that file.\n',
  );
  process.exit(1);
}

const tree = { files: [], dirs: [] };
walk(path.join(ROOT, 'backend'), tree);

const carried = tree.files.filter((f) => matches(f, includes) && !matches(f, excludes));
const offenders = [];
for (const file of carried) {
  for (const { pattern, why } of FORBIDDEN) {
    if (pattern.test(file)) {
      offenders.push({ file, why });
      break;
    }
  }
}

const bytes = carried.reduce((total, f) => {
  try {
    return total + fs.statSync(path.join(ROOT, f)).size;
  } catch {
    return total;
  }
}, 0);

if (offenders.length > 0) {
  console.error(`\n  The installer would carry ${offenders.length} file(s) that must never ship:\n`);
  for (const { file, why } of offenders.slice(0, 25)) {
    console.error(`    ${file}\n      ${why}`);
  }
  if (offenders.length > 25) console.error(`    …and ${offenders.length - 25} more`);
  console.error('\n  Add an exclusion to electron-builder.yml, or move the file out of backend/.\n');
  process.exit(1);
}

console.log(
  `check:payload — backend contributes ${carried.length} files, ` +
    `${(bytes / 1e6).toFixed(1)} MB, and no user data.`,
);
