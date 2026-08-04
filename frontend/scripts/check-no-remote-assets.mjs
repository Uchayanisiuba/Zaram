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
 * Allowed: links a human clicks, which open in their browser and are their
 * decision — not something the page fetches on its own. Anything matching a
 * pattern above is still reported even if it appears here.
 */
const COMMENT_OR_DOC = /^\s*(?:\/\/|\*|\/\*|#|<!--)/;

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
    const lines = text.split('\n');
    for (const { re, what } of PATTERNS) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        const line = text.slice(0, m.index).split('\n').length;
        // A URL inside a comment is documentation, not a request.
        if (COMMENT_OR_DOC.test(lines[line - 1] ?? '')) continue;
        findings.push({
          file: path.relative(path.resolve(ROOT, '..'), file).replace(/\\/g, '/'),
          line,
          what,
          text: (lines[line - 1] ?? '').trim().slice(0, 110),
        });
      }
    }
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
