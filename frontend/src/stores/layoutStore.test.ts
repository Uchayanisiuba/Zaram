/**
 * The stored layout, when the defaults change underneath it.
 *
 * A persisted value beats a constant, always. So lowering `RAIL_DEFAULT`
 * changes nothing for anyone who has opened the app before — the change ships,
 * the rail stays wide, and it reads as an edit that did not take. That is the
 * failure this migration exists to prevent, and it is invisible on a fresh
 * profile, which is where it gets tested by accident.
 *
 * Driven in the browser first: an entry at `version: 0` migrates and a
 * version-less one does not, because zustand gates on
 * `typeof stored.version === 'number'`. Real entries always carry a version, so
 * the reachable case is the one asserted hardest.
 */
import { describe, it, expect } from 'vitest';
import { migrateLayout, RAIL_DEFAULT } from './layoutStore';

const stored = (railWidth: number) => ({
  chatFraction: 0.45,
  chatFractionWorkspace: 0.28,
  railWidth,
});

describe('the layout migration', () => {
  it('drops a rail width stored before the default narrowed', () => {
    const migrated = migrateLayout(stored(440), 0) as Record<string, unknown>;

    // Absent, not overwritten with the new number: zustand merges the result
    // over current state, so a missing key *is* how the default takes effect.
    // Writing 260 here would pin the migration to a constant that is free to
    // change again.
    expect('railWidth' in migrated).toBe(false);
  });

  it('keeps the conversation widths, which nobody asked to reset', () => {
    const migrated = migrateLayout(stored(440), 0) as Record<string, unknown>;

    expect(migrated.chatFraction).toBe(0.45);
    expect(migrated.chatFractionWorkspace).toBe(0.28);
  });

  it('leaves a current entry alone', () => {
    const current = stored(300);

    // Someone who dragged the rail to 300 after this shipped keeps 300. A
    // migration that ran every load would quietly undo their choice on every
    // reload, which is worse than never having run.
    expect(migrateLayout(current, 1)).toBe(current);
  });

  it('narrows the rail to something its own labels fit in', () => {
    // The number is a judgement, but the direction is not: the rail must not be
    // wider than the content it holds. 440 left a band of empty rail as wide as
    // the labels beside it.
    expect(RAIL_DEFAULT).toBeLessThan(440);
  });
});
