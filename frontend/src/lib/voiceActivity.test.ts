/**
 * When the detector believes somebody started talking, and when it lets go.
 *
 * Every rule in `voiceActivity.ts` is a judgement that decides whether a
 * sentence gets recorded whole, cut in half, or never started — and none of
 * them can be exercised by opening a real microphone in CI. That is the whole
 * reason the state machine is separate from `micStore`, and this file is the
 * return on it.
 *
 * The one asserted hardest is the **raised bar while Zaram is speaking**,
 * because getting it wrong is not a missed word: Zaram interrupts itself,
 * records its own voice, transcribes it, and reads it back as something the
 * user said.
 */
import { describe, expect, it } from 'vitest';

import {
  MAX_UTTERANCE_MS,
  ONSET_MS,
  ONSET_RMS,
  ONSET_RMS_WHILE_SPEAKING,
  SILENCE_RMS,
  TRAILING_SILENCE_MS,
  VoiceActivityDetector,
  rmsOf,
} from './voiceActivity';

/** Walk the detector through a run of equally loud samples, 50 ms apart, and
 *  return every moment it produced. */
function feed(
  detector: VoiceActivityDetector,
  rms: number,
  ms: number,
  from: number,
  zaramSpeaking = false,
): { events: Array<string | null>; until: number } {
  const events: Array<string | null> = [];
  let t = from;
  for (; t < from + ms; t += 50) events.push(detector.push(rms, t, zaramSpeaking));
  return { events, until: t };
}

const QUIET = 0.005;
const TALKING = ONSET_RMS * 2;

describe('deciding that somebody started talking', () => {
  it('says nothing while the room is quiet', () => {
    const d = new VoiceActivityDetector();
    const { events } = feed(d, QUIET, 2000, 0);
    expect(events.every((e) => e === null)).toBe(true);
    expect(d.isSpeaking).toBe(false);
  });

  it('ignores a sound that is loud but brief', () => {
    // A door, a cough, a keyboard. All above the threshold and all shorter than
    // `ONSET_MS`, which is the only thing separating them from a word.
    const d = new VoiceActivityDetector();
    const { events, until } = feed(d, TALKING, ONSET_MS - 50, 0);
    expect(events).not.toContain('onset');
    feed(d, QUIET, 500, until);
    expect(d.isSpeaking).toBe(false);
  });

  it('opens an utterance once the sound has lasted', () => {
    const d = new VoiceActivityDetector();
    const { events } = feed(d, TALKING, ONSET_MS + 200, 0);
    expect(events).toContain('onset');
    expect(d.isSpeaking).toBe(true);
  });

  it('opens it exactly once, not on every loud sample after', () => {
    const d = new VoiceActivityDetector();
    const { events } = feed(d, TALKING, 3000, 0);
    expect(events.filter((e) => e === 'onset')).toHaveLength(1);
  });
});

describe('deciding that they stopped', () => {
  it('survives the pause between clauses', () => {
    const d = new VoiceActivityDetector();
    const opened = feed(d, TALKING, ONSET_MS + 100, 0);
    // A gap shorter than the trailing silence is a breath, not an ending.
    const gap = feed(d, QUIET, TRAILING_SILENCE_MS - 200, opened.until);
    expect(gap.events).not.toContain('end');
    expect(d.isSpeaking).toBe(true);
  });

  it('ends the utterance after a real pause', () => {
    const d = new VoiceActivityDetector();
    const opened = feed(d, TALKING, ONSET_MS + 100, 0);
    const { events } = feed(d, QUIET, TRAILING_SILENCE_MS + 200, opened.until);
    expect(events).toContain('end');
    expect(d.isSpeaking).toBe(false);
  });

  it('does not chatter at the boundary between the two thresholds', () => {
    // The reason `SILENCE_RMS` sits below `ONSET_RMS` rather than equalling it.
    // With one threshold, a voice sitting at it opens and closes an utterance
    // every few samples — chopping a sentence into fragments at exactly the
    // volume most people speak at.
    const d = new VoiceActivityDetector();
    const opened = feed(d, TALKING, ONSET_MS + 100, 0);
    const between = (ONSET_RMS + SILENCE_RMS) / 2;
    const { events } = feed(d, between, 3000, opened.until);
    expect(events).not.toContain('end');
  });

  it('stops on its own rather than recording forever', () => {
    // A stuck microphone or a noisy room must not post minutes of audio in one
    // request.
    const d = new VoiceActivityDetector();
    const opened = feed(d, TALKING, ONSET_MS + 100, 0);
    const { events } = feed(d, TALKING, MAX_UTTERANCE_MS + 500, opened.until);
    expect(events).toContain('end');
  });
});

describe('while Zaram is speaking', () => {
  it('does not treat its own voice as the user cutting in', () => {
    // Ordinary speech volume, with the echo canceller having left some of
    // Zaram behind. Believing this is the user is the failure that makes Zaram
    // interrupt itself and then answer its own transcript.
    const d = new VoiceActivityDetector();
    const { events } = feed(d, TALKING, 3000, 0, true);
    expect(events).not.toContain('onset');
  });

  it('still hears somebody who actually cuts in', () => {
    // The feature. Louder than the raised bar, for longer than the onset
    // duration.
    const d = new VoiceActivityDetector();
    const { events } = feed(d, ONSET_RMS_WHILE_SPEAKING * 1.5, ONSET_MS + 200, 0, true);
    expect(events).toContain('onset');
  });

  it('does not need a shout to finish a sentence it needed one to start', () => {
    // The raised bar applies to *starting* only. If it applied throughout,
    // barge-in would record the first syllable and drop the rest of the
    // sentence the moment the user returned to a normal volume.
    const d = new VoiceActivityDetector();
    const opened = feed(d, ONSET_RMS_WHILE_SPEAKING * 1.5, ONSET_MS + 100, 0, true);
    const { events } = feed(d, TALKING, 2000, opened.until, true);
    expect(events).not.toContain('end');
    expect(d.isSpeaking).toBe(true);
  });

  it('asks for more evidence than it does in silence', () => {
    // Stated as a relation rather than as two literals, so tuning the constant
    // after listening in a real room cannot silently invert the guarantee.
    expect(ONSET_RMS_WHILE_SPEAKING).toBeGreaterThan(ONSET_RMS);
    expect(SILENCE_RMS).toBeLessThan(ONSET_RMS);
  });
});

describe('leaving the mode', () => {
  it('forgets an utterance in progress', () => {
    // Otherwise the next session opens with a half-finished utterance and ends
    // it on the first quiet sample, posting silence.
    const d = new VoiceActivityDetector();
    feed(d, TALKING, ONSET_MS + 100, 0);
    expect(d.isSpeaking).toBe(true);

    d.reset();
    expect(d.isSpeaking).toBe(false);
    const { events } = feed(d, QUIET, 2000, 5000);
    expect(events).not.toContain('end');
  });
});

describe('how loud a buffer is', () => {
  it('is zero for silence', () => {
    expect(rmsOf(new Float32Array(512))).toBe(0);
  });

  it('is not swayed by one loud sample', () => {
    // RMS rather than peak, and this is the difference: a click reaches full
    // scale in a single sample, and a peak reading would call that speech.
    const click = new Float32Array(1024);
    click[0] = 1;
    expect(rmsOf(click)).toBeLessThan(ONSET_RMS);
  });

  it('rises with sustained loudness', () => {
    const tone = new Float32Array(1024).fill(0.2);
    expect(rmsOf(tone)).toBeCloseTo(0.2, 5);
  });

  it('is zero rather than NaN for an empty buffer', () => {
    expect(rmsOf(new Float32Array(0))).toBe(0);
  });
});
