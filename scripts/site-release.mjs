/**
 * Switch the site's download on for a built installer — the fields in
 * `site/site.js` that `release-checksum.mjs` prints for pasting, written by
 * the machine that has the file rather than retyped by a person.
 *
 *   node scripts/site-release.mjs dist-electron/Zaram-0.1.0-x64.exe
 *   node scripts/site-release.mjs dist-electron/Zaram-0.1.0-x64.exe --live
 *
 * Sets `version`, `sizeMb` (MiB, what Explorer shows) and `sha256`, so the
 * download link and the checksum point at the file that was uploaded.
 * **It does not switch the page on unless told to.** `site.js` already turns
 * the download into the call to action on `releaseAt` by itself, so the
 * ordinary release leaves `releaseLive` alone and the page flips on the
 * date; the link works for anyone who has it before then. `--live` sets
 * `releaseLive: true` for a release that should be public at once. Nothing
 * else on the page changes; the copy the maintainer wrote stays theirs.
 */
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = path.join(ROOT, 'site', 'site.js');

const live = process.argv.includes('--live');
const tagArg = process.argv.find((a) => a.startsWith('--tag='));
const tag = tagArg ? tagArg.slice('--tag='.length) : '';
const file = process.argv.slice(2).find((a) => !a.startsWith('--'));
if (!file || !fs.existsSync(file)) {
  console.error('\n  usage: node scripts/site-release.mjs <path to Zaram-<version>-x64.exe>\n');
  process.exit(1);
}
const name = path.basename(file);
const match = /^Zaram-(\d[\w.\-]*?)-x64\.exe$/.exec(name);
if (!match) {
  console.error(`\n  ${name} is not named Zaram-<version>-x64.exe\n`);
  process.exit(1);
}
const version = match[1];
const bytes = fs.statSync(file).size;
const sizeMb = Math.round(bytes / (1024 * 1024));
const sha256 = createHash('sha256').update(fs.readFileSync(file)).digest('hex');

let text = fs.readFileSync(SITE, 'utf-8');
const set = (key, value) => {
  const re = new RegExp(`^(\\s*${key}:\\s*)([^,\\n]*)(,?)`, 'm');
  if (!re.test(text)) {
    console.error(`\n  site/site.js has no "${key}:" line\n`);
    process.exit(1);
  }
  text = text.replace(re, `$1${value}$3`);
};
if (live) set('releaseLive', 'true');
set('version', JSON.stringify(version));
set('sizeMb', `${sizeMb}`);
set('sha256', JSON.stringify(sha256));
if (tag) set('releaseTag', JSON.stringify(tag));
fs.writeFileSync(SITE, text);

console.log(`site-release — ${name}: version ${version}${tag ? ` at ${tag}` : ''}, ${sizeMb} MiB, sha256 ${sha256}`);
console.log(live ? 'site/site.js now has releaseLive: true.' : 'releaseLive left as it is; the page opens the download on releaseAt.');
