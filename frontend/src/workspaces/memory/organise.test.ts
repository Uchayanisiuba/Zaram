/**
 * The cuts Memory offers, and the one that must never cry wolf.
 *
 * The valuable assertion in this file is the *fading* cut. It is offered to the
 * user as "these will be forgotten", which is a claim about their own data with
 * an action attached — so a pinned fact appearing in it, or a durable one, is
 * not a cosmetic slip. It is Zaram telling somebody they are about to lose
 * something they are not.
 */
import { describe, expect, it } from 'vitest';

import type { MemoryRecord } from '@/services/memoryClient';

import {
  comparator,
  filterCounts,
  group,
  matchesFilter,
  scopeLabel,
  scopesPresent,
} from './organise';

function fact(over: Partial<MemoryRecord> & { id: string }): MemoryRecord {
  return {
    content: over.id,
    memory_type: 'fact',
    created_at: 1_000,
    last_accessed: 1_000,
    access_count: 0,
    importance: 0.5,
    source: 'chat',
    tags: [],
    session_id: null,
    metadata: {},
    ...over,
  } as MemoryRecord;
}

describe('the fading cut', () => {
  it('finds what the next pass would forget', () => {
    const rows = [fact({ id: 'a', standing: 'fading' }), fact({ id: 'b', standing: 'durable' })];
    expect(rows.filter((r) => matchesFilter(r, 'fading')).map((r) => r.id)).toEqual(['a']);
  });

  it('never includes a pinned fact, whatever its standing says', () => {
    // Pinned is exempt from fading. Offering one under "these will be
    // forgotten" is a false alarm about the user's own data — the one failure
    // on this surface that costs trust rather than time.
    const pinned = fact({ id: 'p', standing: 'fading', pinned: true });
    expect(matchesFilter(pinned, 'fading')).toBe(false);
  });

  it('does not include a fact whose standing was never recorded', () => {
    // Absent is not fading. Treating an unset field as the alarming value is
    // the invented-value rule with the sign reversed.
    expect(matchesFilter(fact({ id: 'x' }), 'fading')).toBe(false);
  });
});

describe('the counts on the chips', () => {
  it('are live, so an empty cut says so before it is clicked', () => {
    const rows = [
      fact({ id: 'a', standing: 'fading' }),
      fact({ id: 'b', pinned: true }),
      fact({ id: 'c', superseded_by: 'd' }),
      fact({ id: 'd' }),
    ];
    expect(filterCounts(rows)).toEqual({ all: 4, fading: 1, pinned: 1, corrected: 1 });
  });

  it('counts nothing as nothing rather than as unknown', () => {
    expect(filterCounts([])).toEqual({ all: 0, fading: 0, pinned: 0, corrected: 0 });
  });
});

describe('scope, which is rule 7i in the interface', () => {
  it('calls the global scope something a person would say about themselves', () => {
    // Not "global". Nobody describes their own preferences that way, and
    // `CLAUDE.md` keeps internal vocabulary out of the primary path.
    expect(scopeLabel('global')).toBe('About you');
    expect(scopeLabel(undefined)).toBe('About you');
  });

  it('shows a project by its own name, unprettified', () => {
    // The user's string. A slug turned into a title is a value nobody entered.
    expect(scopeLabel('project:north_wind-2026')).toBe('north_wind-2026');
  });

  it('puts what is about you first, then projects by name', () => {
    // Global leads because it is the one every machine has, and because it is
    // the side of the multiplayer boundary that is never shareable.
    const rows = [
      fact({ id: 'a', scope: 'project:zed' }),
      fact({ id: 'b', scope: 'global' }),
      fact({ id: 'c', scope: 'project:acme' }),
      fact({ id: 'd', scope: 'project:acme' }),
    ];
    expect(scopesPresent(rows)).toEqual([
      { scope: 'global', label: 'About you', count: 1 },
      { scope: 'project:acme', label: 'acme', count: 2 },
      { scope: 'project:zed', label: 'zed', count: 1 },
    ]);
  });

  it('treats a missing scope as global rather than as a fourth thing', () => {
    expect(scopesPresent([fact({ id: 'a' })])[0].scope).toBe('global');
  });
});

describe('ordering', () => {
  it('sorts least-recalled by age within the ties', () => {
    // A pile of never-recalled facts all reading 0 is not an ordering. The
    // useful question inside it is which have sat unused longest — decay
    // reaches those first.
    const rows = [
      fact({ id: 'newer', access_count: 0, created_at: 900 }),
      fact({ id: 'older', access_count: 0, created_at: 100 }),
      fact({ id: 'used', access_count: 5, created_at: 50 }),
    ].sort(comparator('forgotten'));
    expect(rows.map((r) => r.id)).toEqual(['older', 'newer', 'used']);
  });

  it('sorts most-recalled first', () => {
    const rows = [
      fact({ id: 'rare', access_count: 1 }),
      fact({ id: 'often', access_count: 9 }),
    ].sort(comparator('recalled'));
    expect(rows.map((r) => r.id)).toEqual(['often', 'rare']);
  });

  it('does not reorder the caller’s array', () => {
    const rows = [fact({ id: 'b', created_at: 2 }), fact({ id: 'a', created_at: 9 })];
    group(rows, 'none', 'newest');
    expect(rows.map((r) => r.id)).toEqual(['b', 'a']);
  });
});

describe('grouping', () => {
  it('orders standing by what needs attention, not by alphabet', () => {
    // The first group is the one with an action attached.
    const rows = [
      fact({ id: 'a', standing: 'durable' }),
      fact({ id: 'b', standing: 'fading' }),
      fact({ id: 'c', standing: 'provisional' }),
    ];
    expect(group(rows, 'standing', 'newest').map((g) => g.key)).toEqual([
      'fading',
      'provisional',
      'durable',
    ]);
  });

  it('says what each standing means rather than printing the field', () => {
    const groups = group([fact({ id: 'a', standing: 'fading' })], 'standing', 'newest');
    expect(groups[0].label).toMatch(/would forget/i);
  });

  it('names a standing it has no words for rather than dropping it', () => {
    const groups = group([fact({ id: 'a' })], 'standing', 'newest');
    expect(groups).toHaveLength(1);
    expect(groups[0].records.map((r) => r.id)).toEqual(['a']);
  });

  it('emits no empty groups', () => {
    expect(group([], 'scope', 'newest')).toEqual([]);
    expect(group([], 'none', 'newest')).toEqual([]);
  });

  it('returns one unlabelled group when grouping is off', () => {
    const groups = group([fact({ id: 'a' }), fact({ id: 'b' })], 'none', 'newest');
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe('');
  });

  it('sorts inside each group, not only across them', () => {
    const rows = [
      fact({ id: 'low', scope: 'global', access_count: 1 }),
      fact({ id: 'high', scope: 'global', access_count: 8 }),
    ];
    expect(group(rows, 'scope', 'recalled')[0].records.map((r) => r.id)).toEqual(['high', 'low']);
  });
});
