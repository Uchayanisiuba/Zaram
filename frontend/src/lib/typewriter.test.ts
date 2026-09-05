import { describe, expect, it } from 'vitest';

import {
  CATCH_UP_PER_SECOND,
  MIN_CHARS_PER_SECOND,
  nextRevealed,
  revealAll,
} from './typewriter';

describe('nextRevealed', () => {
  it('advances at the floor rate when nothing is waiting', () => {
    // 100 ms at the minimum rate: a trickle of tokens still reads as typing.
    expect(nextRevealed(0, 1000, 100, { catchUpPerSecond: 0 })).toBe(
      Math.round(MIN_CHARS_PER_SECOND / 10),
    );
  });

  it('accelerates with the backlog, which is what makes it converge', () => {
    const small = nextRevealed(0, 20, 16);
    const large = nextRevealed(0, 2000, 16);
    expect(large).toBeGreaterThan(small);
  });

  it('never overshoots the text that exists', () => {
    expect(nextRevealed(0, 3, 1000)).toBe(3);
    expect(nextRevealed(5, 5, 1000)).toBe(5);
  });

  it('always moves when there is anything left to show', () => {
    // A rate that rounds to zero would stall forever at 60 frames a second.
    expect(nextRevealed(0, 1, 0.001)).toBe(1);
  });

  it('snaps back when a new reply replaces a longer one', () => {
    // Not a rewind: the previous answer is already committed to the transcript,
    // and continuing to type it into the streaming slot would show it twice.
    expect(nextRevealed(400, 0, 16)).toBe(0);
  });

  it('does not advance without elapsed time', () => {
    expect(nextRevealed(10, 100, 0)).toBe(10);
  });

  it('catches up on a burst within a few frames rather than queueing', () => {
    // The failure this guards is a fixed characters-per-second reveal, which
    // falls further behind the longer the answer is and is still typing after
    // the model has stopped, the speech has ended and the next question is in.
    let revealed = 0;
    const target = 1200;
    let frames = 0;
    while (revealed < target && frames < 120) {
      revealed = nextRevealed(revealed, target, 16);
      frames += 1;
    }
    expect(revealed).toBe(target);
    // Measured: 58 frames at 16 ms, so ~0.93 s to absorb a whole paragraph that
    // arrived in one lump. That is the cadence working rather than lagging — the
    // point is to type it, not to blink it into place — and the bound is here to
    // catch it becoming a *queue*, which is what a fixed rate would do: 1200
    // characters at 45/s is twenty-six seconds.
    expect(frames).toBeLessThan(70);
  });

  it('keeps a steady trickle legible rather than instant', () => {
    // The other half of the same rule: catching up must not mean giving up on
    // cadence when tokens genuinely arrive slowly.
    expect(nextRevealed(0, 6, 16)).toBeLessThan(6);
  });

  it('exposes its constants so the cadence is tunable without a rewrite', () => {
    expect(MIN_CHARS_PER_SECOND).toBeGreaterThan(0);
    expect(CATCH_UP_PER_SECOND).toBeGreaterThan(1);
  });
});

describe('revealAll', () => {
  it('skips the animation for reduced motion', () => {
    expect(revealAll(true, false)).toBe(true);
  });

  it('skips it once the stream has closed', () => {
    // Holding text back from a finished reply is animation for its own sake.
    expect(revealAll(false, true)).toBe(true);
  });

  it('animates while a stream is open and motion is allowed', () => {
    expect(revealAll(false, false)).toBe(false);
  });
});
