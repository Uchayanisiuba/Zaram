import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTypedText } from './useTypedText';

/**
 * The reveal *arithmetic* is tested in `lib/typewriter.test.ts`. This file tests
 * the thing that arithmetic cannot see: whether the loop driving it ever runs.
 *
 * It exists because the first version of this hook keyed its effect on `text`,
 * so every arriving token tore the effect down and set `last = performance.now()`
 * again. At the next paint, `elapsed` was therefore measured from the most
 * recent *token* — a millisecond or two — rather than from the previous frame.
 * The reveal ran about twelve times slow while tokens were arriving, which is
 * precisely when it is being watched. Measured with the fault reintroduced: **38
 * characters of 1800 after six frames, against 450+ once fixed.**
 *
 * Every test in `typewriter.test.ts` passed throughout, because every one of
 * them calls the pure function directly. That is the same shape as the viseme
 * failure this repository has already paid for: correct mapping, green tests,
 * and a mouth that never moved.
 *
 * **Two earlier versions of this file were themselves vacuous**, which is worth
 * recording because it took reintroducing the fault to find out. The first
 * stubbed `cancelAnimationFrame` as a no-op; the second rerendered with the same
 * string each time, so React skipped the effect and the defect never occurred.
 * Both passed against the broken hook. A test for a regression is not finished
 * until it has been watched to fail.
 */

/** A controllable clock and frame pump, so nothing here depends on real time. */
function frameHarness() {
  let now = 0;
  let nextId = 1;
  const pending = new Map<number, FrameRequestCallback>();

  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    const id = nextId++;
    pending.set(id, cb);
    return id;
  });
  // **`cancelAnimationFrame` must genuinely cancel.** The first version of this
  // harness stubbed it as a no-op, and the whole file then passed against the
  // very bug it was written to catch — because that bug *is* a cancellation, and
  // a harness that cannot cancel cannot observe it. Checked by reintroducing the
  // fault and watching these tests go red.
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    pending.delete(id);
  });
  vi.spyOn(performance, 'now').mockImplementation(() => now);

  return {
    /**
     * Move the clock without painting — what happens while tokens arrive.
     *
     * Without this the harness cannot see the defect at all: if time only ever
     * advanced inside a paint, a `last` timestamp taken during a render would
     * always equal the previous paint's, and the stale-clock bug would be
     * invisible. Checked by reintroducing the fault and watching these go red.
     */
    advance(ms: number) {
      now += ms;
    },
    /** Advance to the next 16 ms paint and run whatever is scheduled for it. */
    tick(frames = 1) {
      for (let i = 0; i < frames; i += 1) {
        now = Math.ceil((now + 1) / 16) * 16;
        const due = [...pending.entries()];
        pending.clear();
        due.forEach(([, cb]) => cb(now));
      }
    },
  };
}

describe('useTypedText', () => {
  let harness: ReturnType<typeof frameHarness>;

  beforeEach(() => {
    harness = frameHarness();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('advances by frames elapsed, not by how often tokens arrived', () => {
    // **The regression, stated precisely.** The first version keyed its effect
    // on `text`, so every token re-ran it and reset `last = performance.now()`.
    // Cancellation was never the problem — frames scheduled repeatedly inside
    // one paint interval still run at the next paint. The *clock* was: at paint
    // time `elapsed` was measured from the most recent token, a millisecond or
    // two, rather than from the previous frame. Dense streaming therefore typed
    // roughly an order of magnitude slower than sparse streaming, and the reveal
    // fell steadily further behind the reply for exactly the models that stream
    // fastest.
    //
    // So the invariant is not "it moves" — it moved either way. It is that the
    // *rate* is a function of frames, and independent of render churn.
    const FRAMES = 6;
    const TOKENS_PER_FRAME = 15;
    const CHARS_PER_TOKEN = 20;
    const total = FRAMES * TOKENS_PER_FRAME * CHARS_PER_TOKEN;
    const body = 'a'.repeat(total);

    // All of it present from the start: one render, then six frames.
    const sparse = renderHook(({ text, done }) => useTypedText(text, done), {
      initialProps: { text: '', done: false },
    });
    sparse.rerender({ text: body, done: false });
    act(() => harness.tick(FRAMES));
    const sparseRevealed = sparse.result.current.length;

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    harness = frameHarness();

    // The same six frames and the same text, arriving as a stream — the string
    // must actually *grow* each time, or React compares the identical value,
    // skips the effect, and the defect cannot occur.
    const dense = renderHook(({ text, done }) => useTypedText(text, done), {
      initialProps: { text: '', done: false },
    });
    let sent = 0;
    for (let frame = 0; frame < FRAMES; frame += 1) {
      for (let token = 0; token < TOKENS_PER_FRAME; token += 1) {
        sent += CHARS_PER_TOKEN;
        harness.advance(1);
        dense.rerender({ text: body.slice(0, sent), done: false });
      }
      act(() => harness.tick(1));
    }
    const denseRevealed = dense.result.current.length;

    expect(sparseRevealed).toBeGreaterThan(0);
    // Streaming can never reveal more than has arrived, so this is not a claim
    // that the two match. It is that arriving *gradually* must not collapse the
    // rate — which is what a timestamp reset per token does, by an order of
    // magnitude.
    expect(denseRevealed).toBeGreaterThan(total / 4);
  });

  it('catches up to the full text once tokens stop', () => {
    const { result, rerender } = renderHook(
      ({ text, done }) => useTypedText(text, done),
      { initialProps: { text: '', done: false } },
    );

    const body = 'The deposit clause is in the second schedule and matters.';
    for (let i = 1; i <= body.length; i += 1) {
      rerender({ text: body.slice(0, i), done: false });
    }

    act(() => harness.tick(60));
    expect(result.current).toBe(body);
  });

  it('reveals progressively rather than all at once', () => {
    const { result, rerender } = renderHook(
      ({ text, done }) => useTypedText(text, done),
      { initialProps: { text: '', done: false } },
    );

    rerender({ text: 'a'.repeat(400), done: false });
    act(() => harness.tick(1));
    const afterOne = result.current.length;

    act(() => harness.tick(1));
    const afterTwo = result.current.length;

    expect(afterOne).toBeGreaterThan(0);
    expect(afterOne).toBeLessThan(400);
    expect(afterTwo).toBeGreaterThan(afterOne);
  });

  it('shows everything the moment the stream closes', () => {
    // Holding text back from a finished reply is animation for its own sake,
    // and would leave the last words unread if the user moved on.
    const { result, rerender } = renderHook(
      ({ text, done }) => useTypedText(text, done),
      { initialProps: { text: '', done: false } },
    );

    rerender({ text: 'a complete answer', done: false });
    act(() => harness.tick(1));
    expect(result.current).not.toBe('a complete answer');

    rerender({ text: 'a complete answer', done: true });
    expect(result.current).toBe('a complete answer');
  });

  it('does not replay the previous reply when a new one takes the slot', () => {
    const { result, rerender } = renderHook(
      ({ text, done }) => useTypedText(text, done),
      { initialProps: { text: '', done: false } },
    );

    rerender({ text: 'the first answer, at some length', done: false });
    act(() => harness.tick(40));
    expect(result.current).toBe('the first answer, at some length');

    // The stream slot is cleared and a new reply starts.
    rerender({ text: '', done: false });
    act(() => harness.tick(1));
    expect(result.current).toBe('');
  });
});
