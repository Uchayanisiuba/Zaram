/**
 * Who owns `speaking`.
 *
 * The defect these are written against: `ChatSurface` wrote `idle` the moment
 * generation finished, and speech had already set `speaking` and was still
 * playing. Speech starts on the first sentence that will not change again and
 * outlives the stream *by design*, so the two collided on every reply — and
 * because the rim light is the same colour for `thinking` and `speaking`, the
 * only symptom was an avatar whose mouth never opened.
 *
 * The first test is the regression. The rest exist so the guard cannot be
 * satisfied by a function that simply never changes anything.
 */

import { describe, it, expect } from 'vitest';

import { preserveSpeaking, chatActivity } from './orbActivity';

describe('speech owns the speaking state', () => {
  it('a finished stream does not silence a clip that is still playing', () => {
    // Exactly the sequence that failed: generation ends, audio continues.
    expect(preserveSpeaking('speaking', chatActivity(false))).toBe('speaking');
  });

  it('a starting stream does not interrupt it either', () => {
    expect(preserveSpeaking('speaking', chatActivity(true))).toBe('speaking');
  });
});

describe('it still reports chat activity', () => {
  it('is thinking while the request is in flight', () => {
    expect(preserveSpeaking('idle', chatActivity(true))).toBe('thinking');
  });

  it('is idle once it is not', () => {
    expect(preserveSpeaking('thinking', chatActivity(false))).toBe('idle');
  });

  it('replaces every state except speaking', () => {
    // A guard that preserved anything it happened to find would pass the two
    // tests above and quietly freeze the orb on `swapping` or `listening`.
    for (const current of ['idle', 'thinking', 'listening', 'swapping', 'warming'] as const) {
      expect(preserveSpeaking(current, chatActivity(true))).toBe('thinking');
    }
  });
});
