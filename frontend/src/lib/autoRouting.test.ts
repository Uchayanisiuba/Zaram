/**
 * When Auto is a real choice, and when it is a button that cannot change
 * anything.
 *
 * Asked for on 7 September 2026. Until now all three modes were always live,
 * and on a machine with one chat model that is a control over hardcoded data —
 * press any of the three and the same model answers, because there is nothing
 * else for it to answer instead.
 */
import { describe, expect, it } from 'vitest';

import { autoAvailability } from './autoRouting';
import type { DiscoveredModel } from '@/services/settingsClient';

const model = (over: Partial<DiscoveredModel> = {}): DiscoveredModel =>
  ({
    id: 'qwen3-14b-16k',
    displayName: 'Qwen3 14B',
    provider: 'ollama',
    locality: 'local',
    dataPolicy: 'private',
    selectableByDefault: true,
    fitsResident: true,
    category: 'llm',
    ...over,
  }) as DiscoveredModel;

describe('when Auto has a choice to make', () => {
  it('is usable with two local models', () => {
    const result = autoAvailability([model(), model({ id: 'gemma4-26b-32k' })], false);
    expect(result.usable).toBe(true);
    expect(result.candidates).toBe(2);
  });

  it('counts a cloud model once the device may send', () => {
    const models = [model(), model({ id: 'gpt', locality: 'cloud' })];
    expect(autoAvailability(models, true).usable).toBe(true);
    // Connected but nothing may leave: it is not a candidate, and Auto is back
    // to one option. Counting it would light the control up on a machine where
    // it still cannot do anything.
    expect(autoAvailability(models, false).usable).toBe(false);
  });

  it('does not count a model Zaram may not pick on its own', () => {
    // `selectable_by_default` stops Zaram routing to a free tier that trains on
    // the user's work without being asked. The user can still choose it by name
    // from the list — that is a different act.
    const models = [model(), model({ id: 'free-tier', selectableByDefault: false })];
    expect(autoAvailability(models, true).usable).toBe(false);
  });

  it('ignores anything that is not a chat model', () => {
    // Ollama answers `/api/generate` for `bge-m3` with a 400, so an embedder is
    // not a route Auto could ever take.
    const models = [model(), model({ id: 'bge-m3', category: 'embedding' })];
    expect(autoAvailability(models, false).usable).toBe(false);
  });
});

describe('what it says when it cannot', () => {
  it('names one model as the reason, not a failure', () => {
    const result = autoAvailability([model()], false);
    expect(result.usable).toBe(false);
    expect(result.reason).toMatch(/[Oo]nly one model/);
  });

  it('distinguishes nothing installed from nothing permitted', () => {
    // Different problems with different fixes — the same distinction the cloud
    // tooltip already draws between "no provider connected" and "nothing may
    // leave yet".
    expect(autoAvailability([], false).reason).toMatch(/installed/);
    expect(
      autoAvailability([model({ selectableByDefault: false })], false).reason,
    ).toMatch(/Settings|choose one/);
  });

  it('survives no models having loaded yet', () => {
    expect(autoAvailability(null, false).usable).toBe(false);
    expect(autoAvailability(undefined, true).candidates).toBe(0);
  });
});
