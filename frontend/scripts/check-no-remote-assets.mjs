/**
 * No remote asset URLs in frontend code.
 *
 * The companion to `backend/tests/test_egress_chokepoint.py`, covering the half
 * of Rule 3 that a Python gate structurally cannot.
 *
 * The gate intercepts requests Zaram's backend makes. It cannot see a request
 * the *browser* makes on behalf of a stylesheet, an <img>, a <script>, an
 * iframe or a renderer `fetch`. Those leave the machine with no possibility of
 * being logged, by any gate, ever. So they are banned outright rather than
 * governed — the ban is what makes Rule 3 true instead of aspirational.
 *
 * This is not hypothetical. `index.css` opened with three
 * `@import url('https://fonts.googleapis.com/...')` lines that fired on every
 * launch, before any UI rendered and before any consent existed. Nobody noticed
 * for months because there was nowhere for it to show up.
 *
 *   node scripts/check-no-remote-assets.mjs
 *
 * Exits non-zero on a finding, so it can gate a build.
 */
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const SCAN_DIRS = ['src', 'index.html', '../electron', '../desktop/src'];
const SKIP = new Set(['node_modules', 'dist', '.vite', 'build', 'legacy']);
const EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.css', '.scss', '.html']);

/**
 * Remote references that would cause the browser to fetch something.
 *
 * Deliberately catches the scheme rather than a host allowlist: there is no
 * such thing as a trusted CDN here, because the objection is not to the
 * destination but to the request being invisible.
 */
const PATTERNS = [
  { re: /@import\s+url\(\s*['"]?https?:\/\//gi, what: 'CSS @import from a remote URL' },
  { re: /url\(\s*['"]?https?:\/\//gi, what: 'CSS url() pointing at a remote asset' },
  { re: /<(?:img|script|link|iframe|video|audio|source)\b[^>]*\b(?:src|href)\s*=\s*['"]https?:\/\//gi, what: 'remote src/href in markup' },
  { re: /\b(?:src|href)\s*=\s*\{?\s*['"`]https?:\/\//gi, what: 'remote src/href in JSX' },
  { re: /\bnew\s+FontFace\s*\(\s*[^)]*https?:\/\//gi, what: 'FontFace loaded from a remote URL' },
];

/**
 * Which lines are comment, so a URL written in prose is not reported as a
 * request. Documentation has to be able to name the thing it forbids — this
 * file's own header quotes the `fonts.googleapis.com` import that motivated it.
 *
 * **This replaced a one-line heuristic that had a real hole.** The old test was
 * `/^\s*(?:\/\/|\*|\/\*|#|<!--)/` — any line *starting with* `*` counted as a
 * comment continuation and was skipped. But `*` is also the CSS universal
 * selector, so
 *
 *     * { background: url('https://cdn.example/x.png') }
 *
 * was silently ignored in every stylesheet and every CSS-in-JS template
 * literal. That is the dangerous direction for a guard to be wrong in: it
 * misses a real request rather than flagging a comment. A `*` line is now
 * treated as comment only when a block comment is actually open.
 *
 * Block detection is deliberately conservative — the opener must start the line.
 * A `/*` inside a string mid-line would otherwise open a region that never
 * closes, and every line after it would go unscanned.
 *
 * Trailing comments are not stripped, on purpose: `https://` contains `//`, so
 * anything that strips from the first `//` mangles the very URLs being looked
 * for. A line that *starts* with a comment marker is a comment; a URL sitting
 * after code on the same line is reported, which is the safe way to be wrong.
 */
const LINE_COMMENT = /^\s*(?:\/\/|#|<!--)/;
const BLOCK_OPEN = /^\s*\/\*/;

function commentLines(text) {
  const inComment = new Set();
  let open = false;
  text.split('\n').forEach((line, i) => {
    const lineNo = i + 1;
    if (open) {
      inComment.add(lineNo);
      if (line.includes('*/')) open = false;
      return;
    }
    if (LINE_COMMENT.test(line)) {
      inComment.add(lineNo);
      return;
    }
    if (BLOCK_OPEN.test(line)) {
      inComment.add(lineNo);
      if (!line.includes('*/')) open = true;
    }
  });
  return inComment;
}

/** Scan one file's text. Exported shape so the self-test can drive it. */
export function scanText(text, rel = 'fixture.css') {
  const out = [];
  const lines = text.split('\n');
  const comments = commentLines(text);

  // One remote URL is one finding, however many patterns match it. The patterns
  // deliberately overlap — `@import url('https://…')` matches both the @import
  // rule and the generic `url()`, and an `<img src="https://…">` matches both
  // the markup and JSX rules — so without this, every finding was reported
  // twice and the "N remote asset reference(s)" headline was double the truth.
  // Found by the self-test below on its first run.
  //
  // Keyed on where the *scheme* sits in the file, not on the line: two
  // different remote URLs on one line are still two findings.
  const seen = new Set();

  for (const { re, what } of PATTERNS) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      const line = text.slice(0, m.index).split('\n').length;
      if (comments.has(line)) continue;
      const schemeAt = m.index + m[0].search(/https?:\/\//);
      if (seen.has(schemeAt)) continue;
      seen.add(schemeAt);
      out.push({
        file: rel,
        line,
        what,
        text: (lines[line - 1] ?? '').trim().slice(0, 110),
      });
    }
  }
  return out;
}

/**
 * Does the scanner still catch what it exists to catch?
 *
 * Checked in rather than run once by hand, because a guard whose logic changed
 * and was believed on inspection is a guard nobody has verified. Each case was
 * observed failing against a deliberately broken scanner.
 */
function selfTest() {
  const cases = [
    ['a remote font import', "@import url('https://fonts.googleapis.com/css2?family=Inter');", 1],
    [
      'the universal selector — the hole the old heuristic had',
      "* { background: url('https://cdn.example/x.png'); }",
      1,
    ],
    ['a remote image in markup', '<img src="https://evil.example/x.png">', 1],
    ['a remote src in JSX', 'const a = <img src="https://evil.example/x.png" />;', 1],
    ['a URL in a line comment', "// see https://fonts.googleapis.com for why not", 0],
    [
      'a URL in a block comment',
      "/**\n * We banned @import url('https://fonts.googleapis.com/x').\n */\nexport const ok = 1;",
      0,
    ],
    [
      'code after a block comment closes — the regression this tracking could cause',
      "/**\n * Prose.\n */\n@import url('https://fonts.googleapis.com/x');",
      1,
    ],
    [
      'an unterminated block opener in a string must not swallow the file',
      'const s = "/*";\n@import url(\'https://fonts.googleapis.com/x\');',
      1,
    ],
    ['a local asset', "@import url('./fonts/inter.css');", 0],
  ];

  const failures = [];
  for (const [name, source, expected] of cases) {
    const found = scanText(source).length;
    if (found !== expected) {
      failures.push(`  - ${name}: expected ${expected} finding(s), got ${found}`);
    }
  }
  if (failures.length) {
    console.error('\ncheck-no-remote-assets self-test FAILED:\n');
    console.error(failures.join('\n'));
    console.error('\nThe scanner no longer detects what it exists to detect.\n');
    process.exit(1);
  }
  console.log(`check-no-remote-assets: self-test clean — ${cases.length} cases.`);
}

async function* walk(dir) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return; // optional path (electron/, desktop/) may not exist
  }
  for (const e of entries) {
    if (SKIP.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(full);
    else if (EXTS.has(path.extname(e.name))) yield full;
  }
}

selfTest();

const findings = [];

for (const target of SCAN_DIRS) {
  const abs = path.resolve(ROOT, target);
  const files = [];
  if (path.extname(abs)) files.push(abs);
  else for await (const f of walk(abs)) files.push(f);

  for (const file of files) {
    let text;
    try {
      text = await readFile(file, 'utf8');
    } catch {
      continue;
    }
    const rel = path.relative(path.resolve(ROOT, '..'), file).replace(/\\/g, '/');
    findings.push(...scanText(text, rel));
  }
}

if (findings.length) {
  console.error(
    `\n${findings.length} remote asset reference(s). These leave the machine ` +
      `where the egress gate cannot see them:\n`,
  );
  for (const f of findings) {
    console.error(`  ${f.file}:${f.line} — ${f.what}`);
    console.error(`    ${f.text}\n`);
  }
  console.error(
    'Ship the asset in the bundle instead. See the no-remote-assets rule in\n' +
      'CLAUDE.md; the egress gate covers Python-originated requests only.\n',
  );
  process.exit(1);
}

console.log('No remote asset references. Everything the page loads ships in the bundle.');
