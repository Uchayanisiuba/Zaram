/**
 * Doubt renders chat.
 *
 * The gate has three inputs and only one of them may take the composer away.
 * The two that must not are the ones a later reader is likely to collapse —
 * "the probe failed, so nothing is set up" is a reasonable-sounding inference
 * and it is wrong: a failed fetch says nothing about whether a model is
 * installed, and acting on it would put an invented claim on the one screen a
 * new user judges the product by.
 */
import { describe, it, expect } from 'vitest';

import { setupToOffer, type ReadinessProbe } from './useReadiness';
import type { ReadinessReport } from '@/services/readinessClient';

const report = (canChat: boolean): ReadinessReport => ({
  readiness: canChat ? 'ready' : 'no_engine',
  summary: 'a line for the user',
  canChat,
  offers: [],
  stillWorks: [],
});

describe('deciding whether to offer setup instead of a composer', () => {
  it('offers it when the backend says chat cannot work', () => {
    const probe: ReadinessProbe = { status: 'known', report: report(false) };

    expect(setupToOffer(probe)).toBe(probe.report);
  });

  it('leaves the composer alone when chat works', () => {
    expect(setupToOffer({ status: 'known', report: report(true) })).toBeNull();
  });

  it('leaves the composer alone while the answer is still in flight', () => {
    // A first-run screen that flashes up for 200ms on every open is worse than
    // one that arrives a moment late.
    expect(setupToOffer({ status: 'checking' })).toBeNull();
  });

  it('leaves the composer alone when the backend could not be asked', () => {
    // The orb reports a dead backend. Rendering "you have no model" because a
    // fetch failed would be a claim nothing measured.
    expect(setupToOffer({ status: 'unavailable' })).toBeNull();
  });
});
