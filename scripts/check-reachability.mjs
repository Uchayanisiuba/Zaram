/**
 * Nothing complete, tested and unreachable.
 *
 * This repository's signature failure, fourteen times over: a subsystem that
 * is finished, commented, covered by passing tests, and reached by nothing.
 * Parts of Zaram were built with Kilo Code and Trae, which are good at
 * producing a plausible whole and have no way to check that anything calls it,
 * so the failure is structural rather than careless and vigilance has not
 * scaled. This turns "somebody has to notice" into "the build says so".
 *
 * **Two checks, because one would not have helped much.** Reviewing the six
 * found on 18 August alone:
 *
 *   orchestrator/           unimported module        <- check A
 *   /character routes       no frontend caller       <- check B
 *   ingest service_api      no frontend caller       <- check B
 *   EmbodimentSpikeControls imported and mounted     <- neither; it was reachable
 *   _hybrid blend           dead branch in a live fn <- neither
 *   noteEgress              unused export            <- neither
 *
 * So A alone catches one of six. B catches the pattern that actually recurs
 * here — a backend endpoint finished ahead of the interface and then forgotten
 * — which is what "configurable, not usable" has meant every time. Neither
 * catches a dead branch or an unused export, and this file does not pretend
 * to: those need different instruments, and claiming coverage a check does not
 * have is the exact defect that let Ctrl+S be deleted for weeks by a guard
 * named for Save that tested c/v/x/a/z.
 *
 * **Reports, never deletes.** Unreachable is evidence, not a verdict: a route
 * may be waiting on an interface that is genuinely next, and `core/pairing.py`
 * is deliberately complete-and-uncalled. Both lists take an allowlist with a
 * reason, and an allowlist entry is a claim someone made on purpose.
 *
 *   node scripts/check-reachability.mjs           report, exit 0
 *   node scripts/check-reachability.mjs --strict  exit 1 on any finding
 *
 * Not wired into `check:all` as a gate yet — see the note at the bottom.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const STRICT = process.argv.includes('--strict');

/* ------------------------------------------------------------------ walking */

const SKIP_DIRS = new Set([
  'node_modules', 'venv', '__pycache__', '.git', 'dist', 'dist-electron',
  'build', 'legacy', '.vite', 'coverage',
]);

function walk(dir, test, out = []) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(full, test, out);
    } else if (test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const rel = (p) => path.relative(ROOT, p).split(path.sep).join('/');
const read = (p) => fs.readFileSync(p, 'utf8');

/** A test file, by this repo's conventions in both languages. */
const isTest = (p) => /(^|\/)tests?\//.test(rel(p)) || /\.test\.[tj]sx?$|^test_|_test\.py$/.test(path.basename(p));

/* -------------------------------------------------- A. unimported modules */

/**
 * Entry points and deliberate exceptions.
 *
 * Every line is a claim with a reason attached, because an allowlist without
 * one becomes a place to silence findings.
 */
const MODULE_ALLOW = new Map([
  ['backend/main.py', 'the backend entry point'],
  ['backend/conftest.py', 'pytest loads it by name'],
  ['frontend/src/main.tsx', 'the Vite entry point'],
  ['frontend/src/ambient.tsx', 'the ambient surface entry point'],
  ['backend/core/pairing.py', 'complete and uncalled on purpose — the credential a second device needs, waiting on sync'],
]);

/** Import statements only — never free text, so a mention in a comment cannot
 *  make dead code look live. That direction of error is the dangerous one. */
function pythonImports(source, fromFile) {
  const found = new Set();
  // Relative to `backend/`, which is pytest's rootdir and the import root, so
  // `backend/knowledge/x.py` is the module `knowledge.x`. Resolving relative
  // imports against the repo root instead produced `backend.knowledge.x`,
  // which matched no module name and reported 183 live modules as dead — a
  // guard nobody would have read twice.
  const pkg = path.dirname(rel(fromFile)).replace(/^backend\/?/, '').split('/').filter(Boolean);

  // `from x import a, b as c` -> ['a', 'b']. A name imported from a package is
  // a submodule as often as it is a symbol: `from artifacts import extract` and
  // `from . import _reader` both name a *module*, and reading only the part
  // before `import` is what reported five live modules as dead. Adding `x.a`
  // for every name over-approximates whenever a symbol shares a sibling
  // module's name, and that is the safe direction — a missed find costs a line
  // of report, a wrong find costs somebody deleting something load-bearing.
  const importedNames = (clause) =>
    clause
      .replace(/[()\\]/g, ' ')
      .split(',')
      .map((part) => part.trim().split(/\s+as\s+/)[0].trim())
      .filter((name) => /^[A-Za-z_]\w*$/.test(name));

  // Split on `\r?\n`, not `\n`. Every Python file in this checkout is CRLF, so
  // splitting on `\n` alone leaves a `\r` at the end of every line — and JS `.`
  // does not match `\r`, so a pattern anchored with `$` matches nothing at all.
  // That turned this check from 25 findings into 59, all of the new ones alive.
  for (const line of source.split(/\r?\n/)) {
    // Absolute: `from a.b import c` / `import a.b`
    let m = /^\s*from\s+([A-Za-z_][\w.]*)\s+import\b(.*)$/.exec(line);
    if (m) {
      found.add(m[1]);
      for (const name of importedNames(m[2])) found.add(`${m[1]}.${name}`);
    } else {
      m = /^\s*import\s+([A-Za-z_][\w.]*)/.exec(line);
      if (m) found.add(m[1]);
    }

    // Relative: `from .retrieval import X` / `from ..core import Y` /
    // `from . import _reader`
    const r = /^\s*from\s+(\.+)([\w.]*)\s+import\b(.*)$/.exec(line);
    if (r) {
      const up = r[1].length - 1;
      const base = pkg.slice(0, pkg.length - up);
      const prefix = [...base, ...(r[2] ? r[2].split('.') : [])];
      found.add(prefix.join('.'));
      for (const name of importedNames(r[3])) found.add([...prefix, name].join('.'));
    }

    // Late/dynamic: `__import__("knowledge.protocol", fromlist=[...])`, which
    // this codebase genuinely uses — knowledge/runtime.py does it twice.
    for (const d of source.matchAll(/__import__\(\s*["']([\w.]+)["']/g)) found.add(d[1]);
    // `importlib.import_module("x.y")`
    for (const d of source.matchAll(/import_module\(\s*["']([\w.]+)["']/g)) found.add(d[1]);
  }
  return found;
}

function checkPythonModules() {
  const files = walk(path.join(ROOT, 'backend'), (n) => n.endsWith('.py'))
    .filter((f) => !rel(f).startsWith('backend/venv/'));

  // Every dotted name any non-test module imports.
  const imported = new Set();
  for (const f of files) {
    if (isTest(f)) continue;
    for (const name of pythonImports(read(f), f)) {
      imported.add(name);
      // `from a.b.c import d` also reaches `a.b` and `a`.
      const parts = name.split('.');
      for (let i = 1; i < parts.length; i += 1) imported.add(parts.slice(0, i).join('.'));
    }
  }

  const findings = [];
  for (const f of files) {
    const r = rel(f);
    if (isTest(f) || MODULE_ALLOW.has(r) || path.basename(f) === '__init__.py') continue;

    // backend/knowledge/domains.py -> knowledge.domains
    const dotted = r.replace(/^backend\//, '').replace(/\.py$/, '').split('/').join('.');
    if (!imported.has(dotted)) findings.push({ file: r, name: dotted });
  }
  return findings;
}

/* -------------------------------------------- B. routes nothing calls */

/**
 * Routes the interface is not expected to call.
 *
 * `/health` and `/readiness` are called, but these are the ones a reviewer
 * will otherwise re-derive every time.
 */
const ROUTE_ALLOW = new Map([
  ['/docs', 'FastAPI serves it'],
  ['/openapi.json', 'FastAPI serves it'],
  ['/redoc', 'FastAPI serves it'],
]);

function backendRoutes() {
  const files = walk(path.join(ROOT, 'backend'), (n) => n.endsWith('.py'))
    .filter((f) => !rel(f).startsWith('backend/venv/') && !isTest(f));

  const routes = [];
  for (const f of files) {
    for (const m of read(f).matchAll(/@app\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']/g)) {
      routes.push({ method: m[1].toUpperCase(), pathSpec: m[2], file: rel(f) });
    }
  }
  return routes;
}

/** Every URL literal the frontend and desktop shells mention. */
function frontendUrlText() {
  const dirs = ['frontend/src', 'electron', 'desktop/src', 'packages'];
  let text = '';
  for (const d of dirs) {
    const abs = path.join(ROOT, d);
    if (!fs.existsSync(abs)) continue;
    for (const f of walk(abs, (n) => /\.(ts|tsx|js|jsx|mjs)$/.test(n))) {
      if (isTest(f)) continue;
      text += `\n${read(f)}`;
    }
  }
  // The dev proxy names backend prefixes too; a route it forwards is reachable.
  const proxy = path.join(ROOT, 'frontend/vite.config.js');
  if (fs.existsSync(proxy)) text += `\n${read(proxy)}`;
  return text;
}

function checkRoutes() {
  const routes = backendRoutes();
  const haystack = frontendUrlText();
  const findings = [];

  for (const route of routes) {
    if (ROUTE_ALLOW.has(route.pathSpec)) continue;

    // `/knowledge/domains/{domain_id}/sources/{source_id}` is called as a
    // template, so match on the longest literal prefix before the first
    // parameter. A caller of the prefix is evidence the family is reachable.
    const literal = route.pathSpec.split('{')[0].replace(/\/$/, '');
    if (!literal || literal === '/') continue;
    if (!haystack.includes(literal)) {
      findings.push({ ...route, literal });
    }
  }
  return findings;
}

/* ------------------------------------------------------- exported for tests */

/**
 * `pythonImports` is exported so `test/reachability.test.js` can assert the
 * forms it must recognise. A checker with no test of its own has now been
 * wrong twice — once resolving relative imports against the repo root, and
 * once failing on CRLF — and both times the output looked plausible enough to
 * act on. This one reports what a person will delete; it does not get to be
 * the only unverified thing in the build.
 */
export { pythonImports };

/* ------------------------------------------------------------------ report */

function report() {
  const modules = checkPythonModules();
  const routes = checkRoutes();

  const line = (s = '') => process.stdout.write(`${s}\n`);

  line('');
  line('Reachability — what is finished and reached by nothing');
  line('='.repeat(60));

  line('');
  line(`A. Python modules no other module imports  (${modules.length})`);
  if (modules.length === 0) line('   none');
  for (const m of modules) line(`   ${m.file}`);

  line('');
  line(`B. Backend routes no frontend file mentions  (${routes.length})`);
  if (routes.length === 0) line('   none');
  for (const r of routes) line(`   ${r.method.padEnd(6)} ${r.pathSpec}   (${r.file})`);

  line('');
  line('Neither check sees a dead branch inside a live function, an unused');
  line('export, or a component that is mounted but should not be. Those need');
  line('different instruments; this file does not claim them.');
  line('');

  return modules.length + routes.length;
}

// Only when run as a command. Importing this file must not print a report or
// exit the process — the test does exactly that.
const invokedDirectly =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (invokedDirectly) {
  const total = report();
  if (STRICT && total > 0) {
    process.stdout.write(
      `FAIL: ${total} unreachable item(s). Wire it, allowlist it with a reason, or delete it.\n`,
    );
    process.exit(1);
  }
  process.exit(0);
}
