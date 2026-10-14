#!/usr/bin/env node
/**
 * Prove the build knows which release it is.
 *
 *   node scripts/check-release-stamp.mjs v0.1.0-alpha.8
 *
 * Reads `package.json` out of the packaged `app.asar` and fails unless
 * `zaramRelease` is that tag. Without the stamp the update check has nothing to
 * compare against and says it cannot tell -- a build that ships that way can
 * never be told about the next one, and nothing else would notice: the installer
 * runs, the app starts, and only the people who needed the update find out.
 * `scripts/build-installer.mjs` writes it; this reads it back from the artefact.
 */
import { createRequire } from 'node:module';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

export function stampOf(asarPath, asar = require('@electron/asar')) {
  const raw = asar.extractFile(asarPath, 'package.json').toString('utf8');
  return JSON.parse(raw).zaramRelease ?? null;
}

const expected = process.argv[2];
if (process.argv[1]?.endsWith('check-release-stamp.mjs')) {
  if (!expected) {
    console.error('usage: node scripts/check-release-stamp.mjs <tag>');
    process.exit(2);
  }
  const asarPath = path.join(ROOT, 'dist-electron', 'win-unpacked', 'resources', 'app.asar');
  let found;
  try {
    found = stampOf(asarPath);
  } catch (err) {
    console.error(`check-release-stamp: could not read ${asarPath}: ${err.message}`);
    process.exit(1);
  }
  if (found !== expected) {
    console.error(`check-release-stamp: the build says ${found === null ? 'nothing' : `"${found}"`}, expected "${expected}". It could never be told about a newer release.`);
    process.exit(1);
  }
  console.log(`check-release-stamp: the packaged build is stamped ${found}.`);
}
