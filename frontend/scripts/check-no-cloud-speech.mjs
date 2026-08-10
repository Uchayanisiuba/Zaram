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

/** Lines that open a block comment, conservatively.
 *
 *  A block comment is only recognised when its opener starts the line. That is
 *  narrower than JavaScript's real grammar and deliberately so: an opener
 *  inside a string literal mid-line would otherwise begin a comment region that
 *  never ends, and every line after it would go unscanned. The whole value of
 *  this script is that it cannot be talked out of looking, so where the two
 *  available errors are "flag a comment" and "miss a use", it takes the first.
 *
 *  Anchored at the line start covers what actually occurs: JSDoc headers and
 *  the banners this codebase writes above every module. */
const BLOCK_OPEN = /^\s*\/\*/;

/** Scan one file's text. Exported shape so the self-test below can drive it
 *  with fixtures — a guard whose logic changed and was believed on inspection
 *  is a guard nobody has checked. `check-visemes.mjs` was mutation-tested
 *  before being trusted; this is the same debt, paid in the same currency. */
export function scanText(text, { rel = 'fixture.ts', inQuarantine = false } = {}) {
  const out = [];
  let inBlockComment = false;

  text.split('\n').forEach((line, i) => {
    // Comments discuss this API by name — including this script's own
    // documentation elsewhere — and banning the word in prose would make the
    // rule unexplainable in the codebase that enforces it.
    //
    // Stripping only single-line comments was not enough: a module explaining
    // *why* it does thirty lines of MediaRecorder plumbing rather than three
    // lines of the banned API was itself reported, on a line that is prose.
    // That is the check disagreeing with its own docstring, and the fix is to
    // track the block rather than to stop explaining.
    let scannable = line;
    if (inBlockComment) {
      const close = line.indexOf('*/');
      if (close === -1) return;
      inBlockComment = false;
      scannable = line.slice(close + 2);
    }
    // Same-line pairs first, so an opener is only left over when it genuinely
    // runs on to the next line.
    scannable = scannable.replace(/\/\*.*?\*\//g, '');
    if (BLOCK_OPEN.test(scannable) && !scannable.includes('*/')) {
      inBlockComment = true;
      scannable = scannable.replace(/\/\*.*$/, '');
    }

    const code = scannable.replace(/\/\/.*$/, '');

    if (!inQuarantine && CLOUD_SPEECH.test(code)) {
      out.push(
        `${rel}:${i + 1} uses the Web Speech API, which streams microphone ` +
          `audio to Google.\n      ${line.trim()}`,
      );
    }
    const legacy = code.match(LEGACY_IMPORT);
    if (!inQuarantine && legacy) {
      out.push(
        `${rel}:${i + 1} imports from the quarantine: ${legacy[1]}\n` +
          `      legacy/ holds cloud speech recognition. Reaching into it ` +
          `makes that reachable.`,
      );
    }
  });

  return out;
}

/** Does the scanner still catch the thing it exists to catch?
 *
 *  Every case here is a real way the check could have been broken by the
 *  block-comment tracking, and each one was run and observed to fail before the
 *  tracking existed or after it was deliberately broken. A guard that has only
 *  ever been seen to pass has not been tested — it has been *watched*.
 */
function selfTest() {
  const cases = [
    ['a bare construction', 'const r = new webkitSpeechRecognition();', 1],
    ['the unprefixed spelling', 'const R = window.SpeechRecognition;', 1],
    ['a grammar list', 'const g = new SpeechGrammarList();', 1],
    ['an import from the quarantine', "import X from '@/legacy/panels/ChatInterface';", 1],
    ['prose in a line comment', '// webkitSpeechRecognition is banned here', 0],
    [
      'prose in a block comment',
      '/**\n * We do not use webkitSpeechRecognition.\n */\nexport const ok = 1;',
      0,
    ],
    [
      'code after a block comment closes — the regression this tracking could cause',
      '/**\n * Prose.\n */\nconst r = new webkitSpeechRecognition();',
      1,
    ],
    [
      'code on the same line a block comment closes',
      '/* prose */ const r = new webkitSpeechRecognition();',
      1,
    ],
    [
      'an unterminated block comment must not swallow the rest of the file',
      'const s = "/*";\nconst r = new webkitSpeechRecognition();',
      1,
    ],
  ];

  const failures = [];
  for (const [name, source, expected] of cases) {
    const found = scanText(source).length;
    if (found !== expected) {
      failures.push(`  - ${name}: expected ${expected} finding(s), got ${found}`);
    }
  }
  if (failures.length) {
    console.error('\ncheck-no-cloud-speech self-test FAILED:\n');
    console.error(failures.join('\n'));
    console.error('\nThe scanner no longer detects what it exists to detect.\n');
    process.exit(1);
  }
  console.log(`check-no-cloud-speech: self-test clean — ${cases.length} cases.`);
}

selfTest();

const findings = [];

for (const file of await walk(SRC)) {
  const rel = path.relative(SRC, file).split(path.sep).join('/');
  findings.push(
    ...scanText(await readFile(file, 'utf8'), {
      rel,
      inQuarantine: rel.startsWith(`${QUARANTINE}/`),
    }),
  );
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
