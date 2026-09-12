/**
 * Who owns what on the orb, and what nobody can clobber.
 *
 * Two defects, one field, and the second was caused by fixing the first.
 *
 * 19 August 2026: `ChatSurface` wrote `idle` the moment generation finished
 * while speech was still playing, so the avatar's mouth never opened. The fix
 * was a guard, `preserveSpeaking`, refusing every chat state while a clip
 * played.
 *
 * 12 September 2026: that guard meant a fence opening mid-sentence could not
 * turn the orb to `coding`, and when the clip ended speech stood down to
 * `idle` in the middle of a reply that was still streaming — the state cycled
 * thinking → speaking → idle → coding → speaking. The maintainer's words: "it
 * doesn't go and stay in the coding state".
 *
 * The store now holds `activity` (chat's) and `speaking` (speech's) and
 * composes them. These tests drive the real store, because the guarantee is
 * about what the two setters can and cannot reach.
 */

import { describe, it, expect, beforeEach } from 'vitest';

import { chatActivity } from './orbActivity';
import { composeOrbState, useOrbStore } from '@/stores/orbStore';

beforeEach(() => {
  useOrbStore.getState().setSpeaking(false);
  useOrbStore.getState().setActivity('idle');
});

describe('composeOrbState', () => {
  it('draws speech over whatever the system is doing', () => {
    expect(composeOrbState('coding', true)).toBe('speaking');
    expect(composeOrbState('thinking', true)).toBe('speaking');
    expect(composeOrbState('idle', true)).toBe('speaking');
  });

  it('draws the activity when nothing is being said', () => {
    for (const activity of ['idle', 'thinking', 'coding', 'listening', 'swapping'] as const) {
      expect(composeOrbState(activity, false)).toBe(activity);
    }
  });
});

describe('speech owns the speaking state', () => {
  it('a finished stream does not silence a clip that is still playing', () => {
    // Exactly the sequence that failed on 19 August: generation ends, audio continues.
    useOrbStore.getState().setSpeaking(true);
    useOrbStore.getState().setActivity(chatActivity(false));
    expect(useOrbStore.getState().orbState).toBe('speaking');
  });

  it('a starting stream does not interrupt it either', () => {
    useOrbStore.getState().setSpeaking(true);
    useOrbStore.getState().setActivity(chatActivity(true));
    expect(useOrbStore.getState().orbState).toBe('speaking');
  });
});

describe('chat owns the activity, and speech cannot reach it', () => {
  it('coding survives a clip starting and ending — the 12 September regression', () => {
    useOrbStore.getState().setActivity('coding');
    useOrbStore.getState().setSpeaking(true);
    expect(useOrbStore.getState().orbState).toBe('speaking');
    useOrbStore.getState().setSpeaking(false);
    // Speech stood down; the reply is still streaming code. Not idle.
    expect(useOrbStore.getState().orbState).toBe('coding');
    expect(useOrbStore.getState().activity).toBe('coding');
  });

  it('a fence opening while a clip plays is recorded and drawn when the clip ends', () => {
    useOrbStore.getState().setActivity('thinking');
    useOrbStore.getState().setSpeaking(true);
    useOrbStore.getState().setActivity('coding'); // the fence opened mid-sentence
    expect(useOrbStore.getState().orbState).toBe('speaking');
    useOrbStore.getState().setSpeaking(false);
    expect(useOrbStore.getState().orbState).toBe('coding');
  });

  it('is thinking while the request is in flight, idle once it is not', () => {
    useOrbStore.getState().setActivity(chatActivity(true));
    expect(useOrbStore.getState().orbState).toBe('thinking');
    useOrbStore.getState().setActivity(chatActivity(false));
    expect(useOrbStore.getState().orbState).toBe('idle');
  });
});

describe('the old single setter still routes to the right owner', () => {
  it("'speaking' sets the speech field and leaves the activity alone", () => {
    useOrbStore.getState().setActivity('coding');
    useOrbStore.getState().setOrbState('speaking');
    expect(useOrbStore.getState().speaking).toBe(true);
    expect(useOrbStore.getState().activity).toBe('coding');
  });

  it('anything else sets the activity and leaves the mouth alone', () => {
    useOrbStore.getState().setSpeaking(true);
    useOrbStore.getState().setOrbState('swapping');
    expect(useOrbStore.getState().activity).toBe('swapping');
    expect(useOrbStore.getState().speaking).toBe(true);
    expect(useOrbStore.getState().orbState).toBe('speaking');
  });
});
