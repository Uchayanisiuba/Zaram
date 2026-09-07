/**
 * When somebody started talking, and when they stopped.
 *
 * Pulled out of `micStore` as a pure state machine over loudness readings,
 * because the alternative is a decision that can only be exercised by opening a
 * real microphone. Every rule below — the hysteresis, the two durations, the
 * raised bar while Zaram is speaking — is a judgement that will be wrong the
 * first time and has to be adjustable and assertable without a soundcard.
 *
 * **The numbers here are starting points and not measurements, and this file
 * says so rather than implying otherwise.** `CLAUDE.md` is blunt about what a
 * number without its conditions is worth: nothing. These were chosen from the
 * shape of the problem — room noise sits an order of magnitude under speech, a
 * door closing is loud and brief, a clause-ending pause is under a second — and
 * the one that genuinely cannot be reasoned into place is
 * `ONSET_RMS_WHILE_SPEAKING`, which depends on the room, the speakers and how
 * well the browser's echo canceller is doing. It is named separately for
 * exactly that reason: it is the constant to turn after listening.
 *
 * **Why a raised bar rather than a mute.** While Zaram is speaking, the
 * microphone hears Zaram. `getUserMedia` is asked for echo cancellation, which
 * is the real defence, but it is a best effort and it is not ours — so the
 * detector asks for more evidence before it believes the user has cut in.
 * Closing the microphone instead would make barge-in impossible, which is the
 * feature; ignoring the problem would make Zaram interrupt itself, hear its own
 * transcription, and answer it.
 */

/** Loudness at which speech is believed to have started, in RMS of the
 *  normalised waveform. Room tone and a fan sit well under this. */
export const ONSET_RMS = 0.04;

/** The same, while Zaram is speaking, so the canceller's residue does not read
 *  as the user cutting in. The one constant to turn after listening in a real
 *  room — see the note above. */
export const ONSET_RMS_WHILE_SPEAKING = 0.1;

/** Loudness under which the room counts as quiet. Deliberately below `ONSET_RMS`
 *  rather than equal to it: a single threshold chatters at the boundary, which
 *  would chop a sentence into fragments at exactly the volume most people
 *  speak. */
export const SILENCE_RMS = 0.02;

/** How long it has to stay loud before it is speech. A door, a cough and a
 *  keyboard are all loud and all shorter than this. */
export const ONSET_MS = 120;

/** How long it has to stay quiet before the utterance is over. Long enough to
 *  survive the pause between clauses, short enough that the reply does not feel
 *  like it is waiting for permission. */
export const TRAILING_SILENCE_MS = 900;

/** A hard stop, so a stuck-open microphone or a noisy room cannot record
 *  forever and then post minutes of audio in one request. */
export const MAX_UTTERANCE_MS = 30_000;

export type VoiceActivityEvent = 'onset' | 'end';

/**
 * Feed it loudness, get back the two moments that matter.
 *
 * Deliberately not an event emitter and deliberately not holding a timer: it is
 * handed the clock on every call, so a test can walk it through two seconds in
 * six lines and the caller decides how often to sample.
 */
export class VoiceActivityDetector {
  /** Whether an utterance is in progress. */
  private speaking = false;
  /** When the current run of loud-enough samples began, or null. */
  private loudSince: number | null = null;
  /** When the current run of quiet samples began, or null. */
  private quietSince: number | null = null;
  /** When the utterance in progress began. */
  private startedAt = 0;

  /** Whether an utterance is currently open. Read by the caller to decide
   *  whether a recorder should be running. */
  get isSpeaking(): boolean {
    return this.speaking;
  }

  /**
   * One loudness reading.
   *
   * @param rms       loudness of this sample, 0..1
   * @param nowMs     a monotonic clock in milliseconds
   * @param zaramSpeaking whether Zaram's own voice is playing, which raises the
   *                  bar for believing the user has started talking
   * @returns the moment this reading produced, or null for "nothing changed"
   */
  push(rms: number, nowMs: number, zaramSpeaking = false): VoiceActivityEvent | null {
    if (!this.speaking) {
      // The raised bar applies **only to starting**. Once the user is talking,
      // the ordinary silence threshold ends the utterance — an utterance that
      // needed a shout to begin must not also need one to continue, or the
      // second half of the sentence is dropped.
      const bar = zaramSpeaking ? ONSET_RMS_WHILE_SPEAKING : ONSET_RMS;
      if (rms < bar) {
        this.loudSince = null;
        return null;
      }
      if (this.loudSince === null) this.loudSince = nowMs;
      if (nowMs - this.loudSince < ONSET_MS) return null;

      this.speaking = true;
      this.startedAt = nowMs;
      this.loudSince = null;
      this.quietSince = null;
      return 'onset';
    }

    if (nowMs - this.startedAt >= MAX_UTTERANCE_MS) return this.end();

    if (rms > SILENCE_RMS) {
      this.quietSince = null;
      return null;
    }
    if (this.quietSince === null) this.quietSince = nowMs;
    if (nowMs - this.quietSince < TRAILING_SILENCE_MS) return null;
    return this.end();
  }

  /** Abandon whatever is in progress. Used when the mode is switched off, so a
   *  half-open utterance does not survive into the next session and end
   *  immediately on the first quiet sample. */
  reset(): void {
    this.speaking = false;
    this.loudSince = null;
    this.quietSince = null;
    this.startedAt = 0;
  }

  private end(): VoiceActivityEvent {
    this.reset();
    return 'end';
  }
}

/**
 * Loudness of one buffer of samples, as RMS.
 *
 * RMS rather than peak, because peak is whatever the loudest single sample was
 * and a click reaches full scale in one sample. RMS is what "how loud does this
 * sound" means, and it is what the thresholds above were reasoned about.
 */
export function rmsOf(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
  return Math.sqrt(sum / samples.length);
}
