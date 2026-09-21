#!/usr/bin/env node
/**
 * The release page, written in the site's voice.
 *
 * GitHub's page cannot be restyled, but the notes are most of what a person
 * sees when the download link lands them there — and until 21 September 2026
 * they were four lines of prose and an auto-generated commit list. This
 * prints the notes for one tag: the site's banner, what the build brought,
 * how to install past SmartScreen, how to verify the file, and how to send
 * feedback without an account. The release workflow pipes it into the
 * release body; run by hand it updates a release that already exists.
 *
 *   node scripts/release-notes.mjs <tag> <sha256> <size-mib>           # print
 *   node scripts/release-notes.mjs <tag> <sha256> <size-mib> --apply   # gh release edit
 *
 * `--apply` shells out to `gh`, which is the maintainer's own credential.
 * Nothing here contacts the network otherwise.
 */
import { execFileSync } from 'node:child_process';

const [tag, sha, size, flag] = process.argv.slice(2);
if (!tag || !sha || !size) {
  console.error('usage: node scripts/release-notes.mjs <tag> <sha256> <size-mib> [--apply]');
  process.exit(2);
}

const version = tag.replace(/^v/, '').replace(/-.*$/, '');
const site = 'https://uchayanisiuba.github.io/Zaram';
const repo = 'https://github.com/Uchayanisiuba/Zaram';

/** What each build brought, in the site's own words — the same list the
 *  Milestones panel carries. Add the next tag above the last. */
const BROUGHT = {
  'v0.1.0-alpha.2': [
    '**You can watch it work.** A row for every step — a file read, a search, a tool called — between the paragraphs, in the order it happened. Each row opens to what that step read, changed and sent, or *"Nothing left this device for this step"*, read from the log.',
    '**Thinking on/off**, beside the routing choice. Off is a few tenths of a second to the first word instead of several; the answer is usually the same for ordinary questions.',
    '**A model that can call tools chooses its own.** You do not name the tool; Zaram still asks before anything changes or leaves.',
    '**Name a folder and it opens.** Say where something is and Zaram offers, with one button, to open it as a coding project and ask again.',
    '**Work that runs on its own** — a question on a schedule, or one run per obligation coming due, drafting the message that should go out. The first thing that needs your say-so stops it; nothing unattended can approve itself or send anything.',
    '**The graphics card comes back.** *Release the card* unloads what every local server can unload, and closing Zaram does the same on its way out.',
    '**Send feedback** from Settings → Help, to a form that needs no account.',
  ],
  'v0.1.0-alpha.1': [
    'The first installer: memory with sources, the egress log, documents, code projects, the manual under Help.',
  ],
};

const brought = BROUGHT[tag] ?? [];

const lines = [
  `<p align="center"><a href="${site}"><img src="${site}/img/og.png" width="720" alt="Zaram — the memory and control layer for people who use more than one AI"></a></p>`,
  '',
  `**Windows, x64, ${size} MiB. An alpha, unsigned.** Every AI you use, in one place — that remembers you. Change the model, keep the memory. A model on your own machine answers first, free and private; add your own keys when you want more reach, and every byte that leaves is logged.`,
  '',
  ...(brought.length
    ? ['## What this build brought', '', ...brought.map((b) => `- ${b}`), '']
    : []),
  '## Install',
  '',
  `1. Download **\`Zaram-${version}-x64.exe\`** below (or the portable build, which needs no install).`,
  '2. Windows SmartScreen will say *"Windows protected your PC"*. That is expected for a build with no signing certificate — press **More info → Run anyway**.',
  '3. Zaram starts with whatever you have. Best with [Ollama](https://ollama.com) and one local model; a cloud key is optional and framed that way inside.',
  '',
  '## Verify the file',
  '',
  'The SHA-256 of the installer, also in `SHA256SUMS.txt` below:',
  '',
  '```',
  sha,
  '```',
  '',
  'In PowerShell, before you run it:',
  '',
  '```powershell',
  `Get-FileHash .\\Zaram-${version}-x64.exe -Algorithm SHA256`,
  '```',
  '',
  '## When something goes wrong',
  '',
  `In an alpha something will. **Settings → Help → Report a problem** copies a short report — version, hardware, the models found, what left the machine, and nothing else: no conversation, no document names, no keys. **Send feedback** next to it opens [a form](${site}/#feedback) that needs no account; paste the report there with what you expected and what happened instead. An [issue](${repo}/issues) works too.`,
  '',
  `[What Zaram is](${site}) · [Milestones](${site}/#milestones) · [Source](${repo}) — source-available, all rights reserved; read every line, the claim is that you can.`,
];

const body = lines.join('\n');

if (flag === '--apply') {
  execFileSync('gh', ['release', 'edit', tag, '--notes-file', '-'], { input: body, stdio: ['pipe', 'inherit', 'inherit'] });
  console.error(`release notes applied to ${tag}`);
} else {
  process.stdout.write(body + '\n');
}
