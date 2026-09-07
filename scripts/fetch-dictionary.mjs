#!/usr/bin/env node
'use strict';

/**
 * Fetch the spell-check dictionary once, so Zaram never fetches one again.
 *
 * **This is a build step, not a runtime path, and the difference is the point.**
 * Chromium's own behaviour is to fetch a Hunspell `.bdic` from Google's CDN the
 * first time a spellcheckable field is focused — silently, on every user's
 * machine, carrying their address, invisible to `EgressGate` because it never
 * passes through the backend. `electron/spellcheck.js` fuses that. This script
 * is how the file gets here instead: run once, by the maintainer, on a machine
 * that has already chosen to talk to the internet, and the result is committed
 * so that nobody who installs Zaram makes the request at all.
 *
 *     node scripts/fetch-dictionary.mjs
 *
 * **The version in the filename does not have to match Electron's.** Chromium
 * asks for `<lang>-<version>.bdic` and the version tracks its own format
 * revision, so pinning one here would break on an Electron upgrade in a way
 * nothing would notice until a user reported no squiggles. Zaram serves this
 * file for whatever name is asked, over loopback — see `startDictionaryServer`
 * — so the name below is a download detail and never a contract.
 *
 * Licence: the en-US dictionary Chromium ships is built from SCOWL, under a
 * permissive MIT/BSD-style licence. Not copyleft, so nothing here conflicts
 * with `CLAUDE.md`'s no-AGPL rule. The licence text travels beside the file.
 */

import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(HERE, '..', 'electron', 'assets', 'dictionaries');

/** Chromium's own dictionary host — the one the runtime is fused against. */
const BASE = 'https://redirector.gvt1.com/edgedl/chrome/dict/';

/**
 * Format revisions to try, newest first.
 *
 * Chromium bumps this when the BDICT format changes, and old revisions stay
 * served. Trying rather than pinning is deliberate: a 404 here is a clear
 * failure at build time, where a wrong guess baked into the app would be a
 * silent absence of spell check on a stranger's machine.
 */
const VERSIONS = ['10-1', '9-0', '8-0', '3-0'];

const LANGUAGE = 'en-US';

/** Below this it is an error page; above it, not a dictionary. */
const PLAUSIBLE_BYTES = [200_000, 8_000_000];

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const tried = [];
  for (const version of VERSIONS) {
    const name = `${LANGUAGE}-${version}.bdic`;
    const url = `${BASE}${name}`;
    let response;
    try {
      response = await fetch(url);
    } catch (error) {
      tried.push(`${name}: ${String(error)}`);
      continue;
    }
    if (!response.ok) {
      tried.push(`${name}: HTTP ${response.status}`);
      continue;
    }

    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length < PLAUSIBLE_BYTES[0] || bytes.length > PLAUSIBLE_BYTES[1]) {
      // A 200 carrying an error page is the failure this catches. Writing it
      // would leave a file that `dictionaryStatus` reports as present and that
      // Chromium refuses to parse, which is the worst of both.
      tried.push(`${name}: ${bytes.length} bytes, not a dictionary`);
      continue;
    }

    const target = path.join(OUT_DIR, name);
    fs.writeFileSync(target, bytes);
    const digest = createHash('sha256').update(bytes).digest('hex');

    console.log(`fetched  ${name}`);
    console.log(`from     ${url}`);
    console.log(`size     ${(bytes.length / 1024).toFixed(0)} KB`);
    console.log(`sha256   ${digest}`);
    console.log(`into     ${path.relative(path.join(HERE, '..'), target)}`);
    console.log('');
    console.log('Commit it. Zaram serves this file over loopback for whatever');
    console.log('name Chromium asks for, so no user ever makes this request.');
    console.log('');
    console.log('The proof is a red underline under a misspelled word in the');
    console.log('composer — a file on disk is not evidence that anything parsed it.');
    return;
  }

  console.error('No dictionary could be fetched. Tried:');
  for (const line of tried) console.error(`  ${line}`);
  process.exitCode = 1;
}

main();
