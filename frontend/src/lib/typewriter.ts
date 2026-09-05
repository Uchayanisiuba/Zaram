/**
 * Reveal streamed text at a steady cadence instead of in the bursts it arrives in.
 *
 * **The text already streams; what it does not do is *read* like it.** Tokens
 * come off a local model in clumps — several words at once, then a pause while
 * the next batch decodes — so the reply lands in visible jerks. Asked for on
 * 19 August 2026, with Claude named as the reference, and Claude's trick is not
 * that it streams sooner: it is that the *render* cadence is decoupled from the
 * *arrival* cadence, so the eye gets a smooth line of type while the network
 * underneath is as lumpy as it likes.
 *
 * Two things this must not do, and they are the reasons it is a function.
 *
 * **It must never become a delay.** The store's `streamingText` stays the truth
 * and everything else keeps reading it — most importantly `pushSpeech`, which
 * queues the first sentence that will not change again while the model is still
 * writing the third. Speech is driven by what the model has *said*, never by
 * what the screen has finished *drawing*, or the maintainer's "as quickly as
 * possible without delay" would be undone by an animation. In practice the
 * display stays well ahead of the voice anyway: this lags by a fraction of a
 * second and synthesis takes most of one per sentence.
 *
 * **It must never lose the end of a reply.** A fixed characters-per-second
 * reveal falls further behind the longer the answer is, and would still be
 * typing after the model had finished, the speech had stopped and the next
 * question had been asked. So the rate is the *larger* of a floor and a share
 * of the backlog: it types steadily when tokens trickle and accelerates when
 * they burst, which is what makes it converge rather than accumulate.
 *
 * `CLAUDE.md` puts a budget on motion. This spends it on the one surface used
 * every single time, and spends nothing at all for a reader who has asked the
 * operating system for less — see `revealAll`.
 */

/** Slowest it will ever type, so a trickle of tokens still looks alive. */
export const MIN_CHARS_PER_SECOND = 45;

/**
 * Share of the outstanding backlog consumed per second.
 *
 * This is what stops the animation becoming a queue. At 6, a 50-character
 * backlog drains at ~300 characters a second and a 400-character one at
 * ~2400 — so a burst is caught up inside a couple of frames while a steady
 * dribble still reads as typing.
 */
export const CATCH_UP_PER_SECOND = 6;

export interface RevealOptions {
  minCharsPerSecond?: number;
  catchUpPerSecond?: number;
}

/**
 * How many characters should be visible after `elapsedMs` more have passed.
 *
 * Pure, monotonic and clamped: it never goes backwards, never overshoots the
 * text that actually exists, and always advances by at least one character when
 * there is anything to show — a sub-pixel rate that rounds to zero would stall
 * forever at 60 frames a second.
 */
export function nextRevealed(
  revealed: number,
  target: number,
  elapsedMs: number,
  options: RevealOptions = {},
): number {
  const min = options.minCharsPerSecond ?? MIN_CHARS_PER_SECOND;
  const catchUp = options.catchUpPerSecond ?? CATCH_UP_PER_SECOND;

  // Text is replaced, not only appended, when a new reply starts. Snapping back
  // is correct: the previous answer is committed to the transcript by then, and
  // continuing to type it into the streaming slot would show it twice.
  if (target <= revealed) return target;
  if (elapsedMs <= 0) return revealed;

  const backlog = target - revealed;
  const perSecond = Math.max(min, backlog * catchUp);
  const step = Math.max(1, Math.round((perSecond * elapsedMs) / 1000));
  return Math.min(target, revealed + step);
}

/**
 * Whether to skip the animation entirely.
 *
 * Reduced motion is a stated preference, not a hint, and typing is exactly the
 * decorative motion it is about. `done` covers the other case: once the stream
 * has closed there is nothing left to smooth, and holding text back from a
 * finished reply would be animation for its own sake.
 */
export function revealAll(prefersReducedMotion: boolean, done: boolean): boolean {
  return prefersReducedMotion || done;
}
