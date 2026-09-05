/**
 * The model picker groups by where a model runs.
 *
 * The assertion that earns this file is the third one: `CapabilityLocality`
 * has four members (`local | cloud | hybrid | remote_device`) and the obvious
 * implementation -- "local, else cloud" -- files a hybrid model under a
 * guarantee nobody checked, or drops it from the picker entirely. Both are
 * worse than showing it under an honest heading, and neither would be caught
 * by a test that only exercises the two common cases.
 */
import { describe, expect, it } from 'vitest';
import { describeFit, groupModelsByLocality } from './SettingsWorkspace';
import type { DiscoveredModel } from '@/services/settingsClient';

function model(id: string, locality: string): DiscoveredModel {
  return {
    id,
    displayName: id,
    provider: 'test',
    locality,
    dataPolicy: null,
    selectableByDefault: true,
    category: 'chat',
    fitsResident: null,
    sizeBytes: null,
    residentCostBytes: null,
    residentBudgetBytes: null,
  };
}

const GB = 1024 ** 3;

/** A local model with a size, and a machine with a budget. */
function sized(
  id: string,
  sizeBytes: number | null,
  residentBudgetBytes: number | null,
  fitsResident: boolean | null,
): DiscoveredModel {
  return { ...model(id, 'local'), sizeBytes, residentBudgetBytes, fitsResident };
}

/**
 * The picker says a model will be slow *before* it is chosen.
 *
 * Measured 27 August 2026: an 18.2 GB model chosen on a 12 GB card produced no
 * warning at any point, then a read timeout naming a URL. The verdict existed
 * the whole time -- `model_fits_resident` computed it and only auto-selection
 * ever read it.
 */
describe('describeFit', () => {
  it('names both numbers, so the reason can be acted on', () => {
    const text = describeFit(sized('gemma4:26b', 18.2 * GB, 9.1 * GB, false));

    expect(text).toContain('18.2 GB');
    expect(text).toContain('9.1 GB');
  });

  it('says nothing about a model that fits', () => {
    expect(describeFit(sized('qwen2.5-coder:7b', 4.7 * GB, 9.1 * GB, true))).toBeNull();
  });

  it('says nothing when the question could not be answered', () => {
    // Metal and DirectML report no capacity. Greying out every model on a Mac
    // would be worse than staying quiet, and `null` is not a quiet no.
    expect(describeFit(sized('anything', 8 * GB, null, null))).toBeNull();
  });

  it('quotes what the model claims on the card, not its weights', () => {
    // The verdict is decided on weights *plus the model's own KV cache*, so
    // the sentence has to quote the same quantity. Quoting the on-disk size
    // was correct only while the cache allowance was held back from the budget
    // rather than charged to the model; since it moved, this row would have
    // read "10.0 GB, and this machine has about 11.7 GB" beside a verdict of
    // too large, and argued with itself in front of the user.
    const text = describeFit({
      ...sized('spills', 10 * GB, 11.7 * GB, false),
      residentCostBytes: 12 * GB,
    });

    expect(text).toContain('12.0 GB');
    expect(text).not.toContain('10.0 GB');
  });

  it('falls back to the on-disk size when no cost is reported', () => {
    // No OpenAI-compatible server reports a memory figure, so the cost is
    // `null` for every model one of them serves. Half a sentence beats none.
    const text = describeFit(sized('tabby-model', 18.2 * GB, 11.7 * GB, false));

    expect(text).toContain('18.2 GB');
  });

  it('still says the short true thing when the numbers are missing', () => {
    // Graded as not fitting, but without both figures there is no comparison
    // to write. An empty "0.0 GB, and this machine has 0.0 GB" would be worse
    // than a plain sentence.
    const text = describeFit(sized('mystery', null, null, false));

    expect(text).toBe('larger than this machine can hold');
  });
});

describe('groupModelsByLocality', () => {
  it('separates local from cloud', () => {
    const groups = groupModelsByLocality([
      model('qwen-exl3', 'local'),
      model('nemotron', 'cloud'),
      model('gemma', 'local'),
    ]);

    expect(groups.map((g) => g.key)).toEqual(['local', 'cloud']);
    expect(groups[0].models.map((m) => m.id)).toEqual(['qwen-exl3', 'gemma']);
    expect(groups[1].models.map((m) => m.id)).toEqual(['nemotron']);
  });

  it('puts local first, because that is the product default and not a ranking', () => {
    const groups = groupModelsByLocality([
      model('cloud-one', 'cloud'),
      model('local-one', 'local'),
    ]);
    expect(groups[0].key).toBe('local');
  });

  it('never drops a model whose locality is neither local nor cloud', () => {
    const groups = groupModelsByLocality([
      model('local-one', 'local'),
      model('hybrid-one', 'hybrid'),
      model('remote-one', 'remote_device'),
      model('mystery', 'something-nobody-has-added-yet'),
    ]);

    const listed = groups.flatMap((g) => g.models.map((m) => m.id));
    expect(listed).toHaveLength(4);
    expect(listed).toContain('hybrid-one');
    expect(listed).toContain('remote-one');
    expect(listed).toContain('mystery');
  });

  it('does not claim a locality it cannot vouch for', () => {
    const groups = groupModelsByLocality([model('hybrid-one', 'hybrid')]);
    const other = groups.find((g) => g.key === 'other');

    expect(other).toBeDefined();
    // The heading must not assert either guarantee.
    expect(other?.label).not.toMatch(/nothing is sent/i);
    expect(other?.label).not.toMatch(/leaves this device/i);
  });

  it('omits a heading that would have no models under it', () => {
    const groups = groupModelsByLocality([model('only-local', 'local')]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('local');
  });
});
