/**
 * The viseme mapping asserts what it claims.
 *
 * `src/lib/visemes.ts` is pure arithmetic over Kokoro's word timings, and it is
 * the one piece of the lip-sync path with no visible failure mode: a wrong
 * shape looks like a slightly odd mouth, not like a bug, so nothing about
 * watching the avatar would catch it. That is exactly the shape of thing
 * CLAUDE.md says must be asserted rather than eyeballed.
 *
 * Run with Node's native type stripping — no test runner, no new dependency:
 *
 *   node --experimental-strip-types scripts/check-visemes.mjs
 *
 * Exits non-zero on failure, so it gates the build alongside the other checks.
 */
import {
  splitPhonemes,
  visemeFor,
  toVisemeTrack,
  visemeAt,
} from '../src/lib/visemes.ts';

let failures = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    console.error(`  FAIL ${name}\n       expected ${e}\n       actual   ${a}`);
    failures++;
  }
}
function assert(name, cond, detail = '') {
  if (!cond) {
    console.error(`  FAIL ${name}${detail ? `\n       ${detail}` : ''}`);
    failures++;
  }
}

// Multi-codepoint clusters must survive splitting. Matching a single character
// first would turn "aɪ" into "a" plus a stray, which is two shapes where there
// is one sound.
check('diphthong stays whole', splitPhonemes('aɪ'), ['aɪ']);
check('affricate stays whole', splitPhonemes('tʃ'), ['tʃ']);

// Stress marks are notation, not sound. Left in, they become unknown symbols
// and close the mouth mid-vowel.
check('stress marks dropped', splitPhonemes('hˈɑɹbəɹ'), ['h', 'ɑ', 'ɹ', 'b', 'ə', 'ɹ']);

// Bilabials are the one distinction that reads at a glance. "m", "b" and "p"
// are visible as a closed mouth, and getting them wrong is what makes lip sync
// look fake.
check('bilabials close the mouth', ['m', 'b', 'p'].map(visemeFor), ['sil', 'sil', 'sil']);
check('open vowel opens it', visemeFor('ɑ'), 'aa');
check('unknown symbol closes rather than guesses', visemeFor('§'), 'sil');

// Kokoro emits empty phoneme strings for tokens that never become sound.
// A viseme on silence is a mouth moving for a full stop.
check(
  'silent tokens contribute nothing',
  toVisemeTrack([{ text: '.', phonemes: '', start_s: 0.3, end_s: 0.3 }]),
  [],
);

// Phonemes spread across the word's own span, and the track must stay inside
// it — a cue past `end_s` would keep the mouth moving after the word is gone.
const track = toVisemeTrack([
  { text: 'Harbour', phonemes: 'hˈɑɹbəɹ', start_s: 1.0, end_s: 1.6 },
]);
assert('word produces one cue per phoneme', track.length === 6, `got ${track.length}`);
assert('track starts with the word', Math.abs(track[0].start_s - 1.0) < 1e-9);
assert(
  'track ends with the word',
  Math.abs(track[track.length - 1].end_s - 1.6) < 1e-9,
  `ended at ${track[track.length - 1].end_s}`,
);
assert(
  'cues are contiguous and rising',
  track.every((c, i) => c.end_s >= c.start_s && (i === 0 || c.start_s >= track[i - 1].start_s)),
);

// A zero-length word must not divide by zero into NaN, which would silently
// freeze the mouth on whatever shape was last set.
const degenerate = toVisemeTrack([{ text: 'x', phonemes: 'ɑ', start_s: 2, end_s: 2 }]);
assert(
  'zero-length word yields finite cues',
  degenerate.every((c) => Number.isFinite(c.start_s) && Number.isFinite(c.end_s)),
  JSON.stringify(degenerate),
);

// Scrubbing: before, during and after.
check('before the track is silence', visemeAt(track, 0.5), 'sil');
check('after the track is silence', visemeAt(track, 9), 'sil');
assert('inside the track is not silence', visemeAt(track, 1.05) !== 'sil');

if (failures) {
  console.error(`\ncheck-visemes: ${failures} failure(s).\n`);
  process.exit(1);
}
console.log('check-visemes: clean — mapping, spans and scrubbing all assert.');
