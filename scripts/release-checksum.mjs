/**
 * Print the SHA-256 of a built installer, and the exact lines to paste into
 * site/site.js so the download page can be switched on.
 *
 * The checksum on the site exists because the build is not code-signed. A digest
 * a user can verify is the honest substitute for a certificate, and it is worth
 * nothing if it was retyped by hand — so it is computed here from the file that
 * will actually be uploaded, never copied from a previous run.
 *
 *   node scripts/release-checksum.mjs
 *   node scripts/release-checksum.mjs dist-electron/Zaram-0.1.0-x64.exe
 */
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'dist-electron');

/** The NSIS installer, not the portable build: it is what the site links to. */
function findInstaller() {
  const given = process.argv[2];
  if (given) {
    const p = path.resolve(ROOT, given);
    if (!fs.existsSync(p)) {
      console.error(`\n  Not found: ${p}\n`);
      process.exit(1);
    }
    return p;
  }
  if (!fs.existsSync(OUT)) {
    console.error(`\n  No dist-electron/. Run: npm run build:desktop\n`);
    process.exit(1);
  }
  const found = fs
    .readdirSync(OUT)
    .filter((f) => /^Zaram-\d[\w.]*-\w+\.exe$/.test(f) && !f.includes('Portable'));
  if (found.length === 0) {
    console.error(`\n  No installer in dist-electron/. Run: npm run build:desktop\n`);
    process.exit(1);
  }
  // Newest wins, so a stale build from last month cannot be published by accident.
  found.sort(
    (a, b) => fs.statSync(path.join(OUT, b)).mtimeMs - fs.statSync(path.join(OUT, a)).mtimeMs,
  );
  return path.join(OUT, found[0]);
}

function sha256(file) {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256');
    createReadStream(file)
      .on('error', reject)
      .on('data', (chunk) => hash.update(chunk))
      .on('end', () => resolve(hash.digest('hex')));
  });
}

const file = findInstaller();
const stat = fs.statSync(file);
const digest = await sha256(file);
const name = path.basename(file);
const version = (name.match(/^Zaram-([\d.]+)-/) || [, '?'])[1];
const sizeMb = Math.round(stat.size / 1024 / 1024);
const ageHours = (Date.now() - stat.mtimeMs) / 36e5;

console.log(`
  file      ${name}
  size      ${sizeMb} MB
  built     ${stat.mtime.toISOString()}${ageHours > 48 ? '   <-- over two days old; rebuild?' : ''}
  sha256    ${digest}

  Paste into site/site.js:

    version: "${version}",
    sizeMb:  ${sizeMb},
    sha256:  "${digest}",

  Then, once you have installed this exact file on a machine that is not this
  one, set releaseLive: true.
`);
