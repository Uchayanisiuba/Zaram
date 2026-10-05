import { describe, expect, it } from 'vitest';

import { STATE_PULSE } from './embodimentPulse';
import { ringColours, SHEEN_SECONDS } from '@/components/orb/LivingOrb';

describe('coding looks like thinking, not like rest — 5 October 2026', () => {
  // The maintainer: "sometimes Zaram doesn't show its states". With the orb as
  // the renderer there is no typing body, so an idle-looking `coding` hid a
  // working reply.
  it('on the pulse every renderer reads', () => {
    expect(STATE_PULSE.coding).toEqual(STATE_PULSE.thinking);
    expect(STATE_PULSE.coding).not.toEqual(STATE_PULSE.idle);
  });

  it('on the orb', () => {
    expect(ringColours('coding')).toEqual(ringColours('thinking'));
    expect(SHEEN_SECONDS.coding).toBeLessThan(SHEEN_SECONDS.idle);
  });
});
