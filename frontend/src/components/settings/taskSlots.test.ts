/**
 * What the per-task picker may offer, and what it must not.
 *
 * The interesting assertions here are all about the line between a
 * **capability** and a **preference** — `CLAUDE.md` calls confusing the two
 * this codebase's most expensive recurring bug, and a picker is a new place
 * for it to happen in both directions: filtering on a preference hides models
 * the user is entitled to choose, and offering past a capability lets them
 * express a setting that can only ever fail.
 */
import { describe, expect, it } from 'vitest';

import type { DiscoveredModel } from '@/services/settingsClient';

import { TASK_SLOT_COPY, displayAssigned, eligibleForSlot } from './taskSlots';

function model(overrides: Partial<DiscoveredModel> & { id: string }): DiscoveredModel {
  return {
    displayName: overrides.id,
    provider: 'ollama',
    locality: 'local',
    dataPolicy: 'never_leaves_device',
    selectableByDefault: true,
    fitsResident: true,
    sizeBytes: null,
    residentBudgetBytes: null,
    residentCostBytes: null,
    category: 'llm',
    supportsVision: false,
    specialisation: '',
    supportsEmbedding: false,
    ...overrides,
  };
}

const seer = model({ id: 'seer', supportsVision: true });
const wordy = model({ id: 'wordy' });
const coder = model({ id: 'coder', specialisation: 'code' });
const embedder = model({ id: 'bge-m3', category: 'embedding' });

describe('what each slot may be assigned', () => {
  it('offers only models that can see for the vision slot', () => {
    // A capability. A model that cannot see is not a worse answer about a
    // screenshot, it is not an answer — so it is removed rather than warned
    // about, which is the same shape `select_model_for_task` uses.
    expect(eligibleForSlot([seer, wordy, coder], 'vision').map((m) => m.id)).toEqual(['seer']);
  });

  it('offers every model for the coding slot, specialists included', () => {
    // A preference. Filtering here would hide every general model on a machine
    // with no coding model, leaving an empty picker indistinguishable from
    // "nothing installed".
    expect(eligibleForSlot([seer, wordy, coder], 'code').map((m) => m.id)).toEqual([
      'seer',
      'wordy',
      'coder',
    ]);
  });

  it('never offers an embedder, in any slot', () => {
    // Ollama answers `/api/generate` for `bge-m3` with a 400, so offering it
    // is offering a choice whose only outcome is a failed reply.
    for (const slot of Object.keys(TASK_SLOT_COPY)) {
      expect(eligibleForSlot([embedder, seer], slot).map((m) => m.id)).not.toContain('bge-m3');
    }
  });

  it('offers nothing for a slot it has no copy for', () => {
    // A backend that grows a third slot before this file has words for it
    // renders no row, rather than an untitled one with a picker under it.
    expect(eligibleForSlot([seer, wordy], 'long_document')).toEqual([]);
  });

  it('has copy for every slot it will render, and each says what it does', () => {
    for (const [slot, copy] of Object.entries(TASK_SLOT_COPY)) {
      expect(copy.label, slot).toBeTruthy();
      expect(copy.detail.length, slot).toBeGreaterThan(40);
      // Not "none". An unassigned slot is not "no model" — it is the general
      // choice still standing, and saying "none" would read as a capability
      // the user has switched off.
      expect(copy.unassigned.toLowerCase(), slot).not.toBe('none');
    }
  });
});

describe('the name shown for an assignment', () => {
  it('resolves a catalogue id to the name used everywhere else', () => {
    const catalogued = model({ id: 'ollama:qwen3-coder-30b-32k', displayName: 'qwen3-coder-30b-32k' });
    expect(displayAssigned([catalogued], 'ollama:qwen3-coder-30b-32k')).toBe(
      'qwen3-coder-30b-32k',
    );
  });

  it('shows a name the catalogue cannot place unchanged', () => {
    // The user typed it, it is what will be sent, and the backend refuses it
    // by name at dispatch. Blanking it here leaves them looking at an empty
    // row wondering what they set.
    expect(displayAssigned([seer], 'anthropic/claude-sonnet-4.5')).toBe(
      'anthropic/claude-sonnet-4.5',
    );
  });

  it('shows the stored value when discovery has not run', () => {
    expect(displayAssigned(null, 'ollama:seer')).toBe('ollama:seer');
  });
});
