/**
 * No `target="_blank"` in the live frontend tree.
 *
 * `electron/main.js` `hardenWindow` denies every window-open and every
 * off-app navigation — deliberately, so the renderer cannot wander. The
 * consequence is that a plain `<a target="_blank">` does nothing when pressed
 * inside the packaged app, and four of them had shipped by 20 September 2026:
 * the GitHub issues link on *Report a problem*, *Where to get a key* under a
 * cloud provider, *running at* on the app card, and every link inside the
 * manual. Each was green in every test, because jsdom opens anything.
 *
 * External links go through `lib/openInBrowser.ts` — the shell bridge, with
 * `window.open` as the development fallback — and this scan is what stops a
 * fifth one arriving the obvious way. Same shape as `check-no-cloud-speech.mjs`;
 * the quarantined `legacy/` tree is skipped for the same reason.
 *
 *   node scripts/check-no-dead-links.mjs
 */
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

const SRC = path.resolve('src');
const QUARANTINE = 'legacy';
const DEAD = /target\s*=\s*["'{]\s*['"]?_blank/;

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full)));
    else if (/\.(tsx|ts|jsx|js)$/.test(entry.name)) out.push(full);
  }
  return out;
}

export function scanText(text, { rel = 'fixture.tsx' } = {}) {
  const out = [];
  text.split('\n').forEach((line, i) => {
    const code = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '');
    // Prose in a block comment may name the attribute — this file's own
    // docstring does. Only a line that looks like JSX or a string literal
    // counts: an `=` attribute, or a query selector in a test.
    if (DEAD.test(code) && !/^\s*\*/.test(line) && !/querySelector|expect\(/.test(code)) {
      out.push(`${rel}:${i + 1} is a target="_blank" link, which the packaged app denies.\n      ${line.trim()}`);
    }
  });
  return out;
}

const SELF_TEST = `<a href={u} target="_blank" rel="noreferrer">x</a>`;
if (scanText(SELF_TEST).length !== 1) {
  console.error('check-no-dead-links: the scanner no longer catches the thing it exists to catch.');
  process.exit(2);
}

const files = await walk(SRC);
const findings = [];
for (const file of files) {
  const rel = path.relative(SRC, file).split(path.sep).join('/');
  if (rel.startsWith(QUARANTINE + '/')) continue;
  if (/\.test\.(tsx?|jsx?)$/.test(rel)) continue;
  findings.push(...scanText(await readFile(file, 'utf8'), { rel }));
}

if (findings.length) {
  console.error('check-no-dead-links: external links must go through lib/openInBrowser.ts:\n');
  for (const f of findings) console.error('  ' + f);
  process.exit(1);
}
console.log(`check-no-dead-links: clean — no target="_blank" in ${files.length} live modules; every external link goes through the shell bridge.`);
