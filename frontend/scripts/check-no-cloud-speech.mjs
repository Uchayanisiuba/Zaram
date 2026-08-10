/**
 * No cloud speech recognition in the live frontend tree.
 *
 * The sibling of `check-no-remote-assets.mjs`, for the same reason and against
 * a worse leak. That file bans remote *asset* URLs because the browser fetches
 * them itself and no backend gate can see it. The Web Speech API is the same
 * mechanism carrying far more sensitive cargo: in Chrome,
 * `webkitSpeechRecognition` streams the user's microphone audio to Google's
 * servers. Not a transcript — the audio.
 *
 * For a product whose claim is that nothing leaves the device without an
 * explicit per-item policy, that is the single worst thing that could be in the
 * bundle, and it is three lines of code away at all times because it is the
 * obvious way to add voice input.
 *
 * `frontend/src/legacy/panels/ChatInterface.tsx` already contains it. That is
 * tolerable *only* while nothing in the live tree reaches it, so this script
 * checks both halves:
 *
 *   1. no live-tree module names SpeechRecognition
 *   2. no live-tree module imports from `legacy/`
 *
 * The second is the one that matters, and it is the lesson the DuckDuckGo fix
 * cost: `test_egress_chokepoint.py` exempted a module as "dormant" while the
 * test suite called it on every run, because the guard checked reachability at
 * boot rather than reachability in fact. An exemption justified by dormancy is
 * worth exactly as much as the check that dormancy is real. So this asserts the
 * quarantine instead of describing it.
 *
 *   node scripts/check-no-cloud-speech.mjs
 *
 * Exits non-zero on a finding, so it gates the build.
 *
 * When local STT lands (faster-whisper, on-device), this stays. Local speech
 * needs no exemption here — it never constructs a SpeechRecognition object.
 * If cloud speech is ever offered deliberately, it goes through the egress gate
 * with a per-item policy and a log entry, and this file gains one allowlisted
 * path with the reason written next to it — never a blanket removal.
 */
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

const SRC = path.resolve('src');
/** Quarantined. Preserved for reference, reachable from nothing. */
const QUARANTINE = 'legacy';

/** The API itself, however it is spelled. */
const CLOUD_SPEECH = /\b(webkitSpeechRecognition|SpeechRecognition|SpeechGrammarList)\b/;
/** Any import that crosses back into the quarantine. */
const LEGACY_IMPORT = /(?:from|import)\s*\(?\s*['"]([^'"]*\blegacy\/[^'"]*)['"]/;

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full)));
    else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const findings = [];

for (const file of await walk(SRC)) {
  const rel = path.relative(SRC, file).split(path.sep).join('/');
  const inQuarantine = rel.startsWith(`${QUARANTINE}/`);
  const text = await readFile(file, 'utf8');

  text.split('\n').forEach((line, i) => {
    // Comments discuss this API by name — including this script's own
    // documentation elsewhere — and banning the word in prose would make the
    // rule unexplainable in the codebase that enforces it.
    const code = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '');

    if (!inQuarantine && CLOUD_SPEECH.test(code)) {
      findings.push(
        `${rel}:${i + 1} uses the Web Speech API, which streams microphone ` +
          `audio to Google.\n      ${line.trim()}`,
      );
    }
    const legacy = code.match(LEGACY_IMPORT);
    if (!inQuarantine && legacy) {
      findings.push(
        `${rel}:${i + 1} imports from the quarantine: ${legacy[1]}\n` +
          `      legacy/ holds cloud speech recognition. Reaching into it ` +
          `makes that reachable.`,
      );
    }
  });
}

if (findings.length) {
  console.error('\nCloud speech recognition is reachable from the live tree:\n');
  for (const f of findings) console.error(`  - ${f}\n`);
  console.error(
    'Microphone audio sent to a third party cannot be logged by any gate,\n' +
      'which is why this is banned outright rather than governed.\n',
  );
  process.exit(1);
}

console.log('check-no-cloud-speech: clean — no cloud speech reachable from the live tree.');
