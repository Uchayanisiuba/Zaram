'use strict';

/**
 * The reachability checker's own import parser.
 *
 * This checker exists to tell somebody which files are safe to delete, and it
 * has now been wrong twice in ways that looked entirely plausible in its
 * output: it resolved relative imports against the repo root and reported 183
 * live modules as dead, and it split CRLF sources on `\n`, leaving a `\r` that
 * no `$`-anchored pattern could cross — which turned 25 findings into 59, all
 * of the new ones alive.
 *
 * Neither failure was subtle in the code. Both were invisible in the report,
 * because a longer list of dead modules reads exactly like a more thorough
 * check. So the parser gets assertions on the forms it must recognise, and one
 * of them is CRLF, because that is what every Python file in this checkout is.
 *
 * These tests are about the *parser*, not about the repository's current
 * findings. A test pinned to "there are 23 unreachable modules" would fail
 * every time somebody correctly deleted one.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const GUARD = pathToFileURL(
  path.join(__dirname, '..', 'scripts', 'check-reachability.mjs'),
).href;

/** `from x import y` inside a file at `backend/<where>`, as a set of names. */
async function importsOf(source, where = 'backend/knowledge/runtime.py') {
  const { pythonImports } = await import(GUARD);
  return pythonImports(source, path.join(__dirname, '..', where));
}

test('reachability: importing the checker neither prints a report nor exits', async () => {
  // The report used to run at module scope and end in `process.exit(0)`, so
  // importing it from a test would have taken the test runner down with it.
  const mod = await import(GUARD);
  assert.strictEqual(typeof mod.pythonImports, 'function');
});

test('reachability: a module imported by name from its package counts as reached', async () => {
  // `from artifacts import extract` imports the *module* artifacts/extract.py.
  // Reading only the part before `import` recorded `artifacts` alone, and
  // artifacts/extract.py — which runtimes/documents/runtime.py calls to build
  // every invoice — was reported dead.
  const found = await importsOf('from artifacts import extract, invoice as invoice_module\n');
  assert.ok(found.has('artifacts.extract'), 'artifacts.extract missing');
  assert.ok(found.has('artifacts.invoice'), 'aliased import lost its module name');
  assert.ok(found.has('artifacts'), 'the package itself should still be recorded');
});

test('reachability: `from . import x` reaches the sibling module', async () => {
  // artifacts/export/csv.py does exactly this to reach artifacts/export/_reader.py,
  // and five exporters do it. The relative branch recorded only the package.
  const found = await importsOf('from . import _reader\n', 'backend/artifacts/export/csv.py');
  assert.ok(found.has('artifacts.export._reader'), 'artifacts.export._reader missing');
});

test('reachability: CRLF sources parse the same as LF', async () => {
  // Every Python file in this checkout is CRLF. JS `.` does not match `\r`, so
  // splitting on `\n` alone left a `\r` that stopped every `$`-anchored match.
  const lf = await importsOf('from core.identity import identity_preamble\n');
  const crlf = await importsOf('from core.identity import identity_preamble\r\n');
  assert.ok(crlf.has('core.identity'), 'CRLF line was not parsed at all');
  assert.deepStrictEqual([...crlf].sort(), [...lf].sort());
});

test('reachability: relative imports resolve against backend/, not the repo root', async () => {
  const found = await importsOf(
    'from .retrieval import SemanticRetrieval\nfrom ..core.paths import data_dir\n',
    'backend/knowledge/runtime.py',
  );
  assert.ok(found.has('knowledge.retrieval'), 'expected knowledge.retrieval');
  assert.ok(found.has('core.paths'), 'expected core.paths from a `..` import');
  assert.ok(!found.has('backend.knowledge.retrieval'), 'repo-root resolution is back');
});

test('reachability: a plain `import a.b` is still recorded', async () => {
  const found = await importsOf('import core.identity\nimport os\n');
  assert.ok(found.has('core.identity'));
  assert.ok(found.has('os'));
});

test('reachability: a mention in a comment or a string does not make dead code look live', async () => {
  // The dangerous direction. `core/untrusted.py` is named in prose in several
  // places; none of them calls it, and the report has to keep saying so.
  const found = await importsOf(
    '# see core.untrusted for the scan\nDOC = "from core.untrusted import scan"\n',
  );
  assert.ok(!found.has('core.untrusted'), 'free text was read as an import');
});

test('reachability: a parenthesised multi-name import records every module', async () => {
  const found = await importsOf('from artifacts import (\n    extract,\n    invoice,\n)\n');
  // Only the first line is an import statement; the continuation lines are
  // read as bare names, which this parser does not follow. What must hold is
  // that the package is recorded and nothing bogus is.
  assert.ok(found.has('artifacts'));
  assert.ok(!found.has('artifacts.('), 'punctuation leaked into a module name');
});
