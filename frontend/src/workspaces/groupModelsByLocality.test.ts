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
import { groupModelsByLocality } from './SettingsWorkspace';
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
  };
}

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
