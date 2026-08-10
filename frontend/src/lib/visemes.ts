/**
 * IPA phonemes onto the five VRM mouth shapes.
 *
 * `docs/EMBODIMENT-SPIKE.md`: this is **lossy by design** — 40-odd English
 * phonemes onto `aa ih ou ee oh`. That is the standard trade and it looks fine,
 * because a mouth moving plausibly in time beats a mouth moving accurately out
 * of time.
 *
 * Kokoro gives word-level timings with the word's full phoneme string attached.
 * Per-phoneme timings are derivable — `pred_dur` is per-phoneme-token
 * underneath and `join_timestamps` merely aggregates to word boundaries — but
 * that is a backend change. Until then this distributes a word's phonemes
 * evenly across its span, which is an approximation and is named as one here so
 * nobody later reads it as measurement.
 *
 * At ~3 phonemes per word and 150 wpm, even distribution gives roughly 7-8
 * shapes per second, against the ~2.5 that word-level-only would give. That is
 * the difference between a mouth that reads as speech and one that reads as
 * chewing.
 */

/** The five presets every VRM carries. `sil` means a closed mouth. */
export type Viseme = 'aa' | 'ih' | 'ou' | 'ee' | 'oh' | 'sil';

export const VISEMES: Viseme[] = ['aa', 'ih', 'ou', 'ee', 'oh'];

/**
 * Longest-match-first, because IPA diphthongs and affricates are multi-codepoint
 * and matching a single character first would turn `aɪ` into `a` plus a stray.
 */
const TABLE: [string, Viseme][] = [
  // Diphthongs and affricates — before their constituents.
  ['aʊ', 'aa'], ['aɪ', 'aa'], ['eɪ', 'ee'], ['oʊ', 'oh'], ['ɔɪ', 'oh'],
  ['tʃ', 'ih'], ['dʒ', 'ih'],
  // Open vowels.
  ['ɑ', 'aa'], ['a', 'aa'], ['æ', 'aa'], ['ʌ', 'aa'], ['ɐ', 'aa'],
  // Close front.
  ['i', 'ih'], ['ɪ', 'ih'], ['I', 'ih'], ['j', 'ih'],
  // Mid front.
  ['ɛ', 'ee'], ['e', 'ee'], ['E', 'ee'], ['A', 'ee'],
  // Back rounded.
  ['u', 'ou'], ['ʊ', 'ou'], ['w', 'ou'], ['U', 'ou'],
  ['ɔ', 'oh'], ['o', 'oh'], ['O', 'oh'],
  // Central — schwa and r-coloured. A relaxed small opening.
  ['ɝ', 'ee'], ['ɚ', 'ee'], ['ə', 'ee'], ['ɹ', 'ou'], ['ɻ', 'ou'],
  // Bilabials close the mouth completely. This is the one distinction that
  // reads clearly at a glance: "m", "b" and "p" are *visible* as a closed
  // mouth, and getting them wrong is what makes lip sync look fake.
  ['m', 'sil'], ['b', 'sil'], ['p', 'sil'],
  // Everything else is a consonant that barely moves the jaw. A small neutral
  // opening beats forcing them onto a vowel shape.
  ['f', 'ih'], ['v', 'ih'], ['θ', 'ih'], ['ð', 'ih'],
  ['s', 'ih'], ['z', 'ih'], ['ʃ', 'ou'], ['ʒ', 'ou'],
  ['t', 'ih'], ['d', 'ih'], ['n', 'ih'], ['l', 'ee'],
  ['k', 'aa'], ['g', 'aa'], ['ŋ', 'aa'], ['h', 'aa'],
];

/** One phoneme to one shape. Unknown symbols close the mouth rather than
 *  guessing — a wrong shape is more visible than a still one. */
export function visemeFor(phoneme: string): Viseme {
  for (const [ipa, v] of TABLE) if (phoneme.startsWith(ipa)) return v;
  return 'sil';
}

/** Split a phoneme string into units, keeping multi-codepoint clusters whole
 *  and dropping stress marks, which are notation rather than sound. */
export function splitPhonemes(phonemes: string): string[] {
  const cleaned = phonemes.replace(/[ˈˌ.\s]/g, '');
  const out: string[] = [];
  for (let i = 0; i < cleaned.length; ) {
    const two = cleaned.slice(i, i + 2);
    if (TABLE.some(([ipa]) => ipa === two)) {
      out.push(two);
      i += 2;
    } else {
      out.push(cleaned[i]);
      i += 1;
    }
  }
  return out;
}

export interface WordTiming {
  text: string;
  phonemes: string;
  start_s: number;
  end_s: number;
}

export interface VisemeCue {
  viseme: Viseme;
  start_s: number;
  end_s: number;
}

/**
 * Word timings to a viseme track.
 *
 * Words are spread evenly across their own span — see the caveat at the top.
 * A word with no phonemes contributes nothing rather than a default shape,
 * because Kokoro emits empty phoneme strings for tokens that never become
 * sound, and a viseme on silence is a mouth moving for a full stop.
 */
export function toVisemeTrack(timings: WordTiming[]): VisemeCue[] {
  const cues: VisemeCue[] = [];
  for (const w of timings) {
    const units = splitPhonemes(w.phonemes || '');
    if (units.length === 0) continue;
    const span = Math.max(0, w.end_s - w.start_s);
    const each = span / units.length;
    units.forEach((u, i) => {
      cues.push({
        viseme: visemeFor(u),
        start_s: w.start_s + i * each,
        end_s: w.start_s + (i + 1) * each,
      });
    });
  }
  return cues;
}

/** The shape at a given playback moment, or `sil` between cues. Linear scan is
 *  fine: an utterance is tens of cues and this runs once a frame. */
export function visemeAt(track: VisemeCue[], t: number): Viseme {
  for (const c of track) {
    if (t >= c.start_s && t < c.end_s) return c.viseme;
  }
  return 'sil';
}
