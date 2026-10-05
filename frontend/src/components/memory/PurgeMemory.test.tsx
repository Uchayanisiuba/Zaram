/**
 * @vitest-environment jsdom
 *
 * The count is the control.
 *
 * * **Nothing deletes until a count has been read**, and the button that
 *   deletes says the number.
 * * **Changing the question discards the answer to the old one** — a preview
 *   of one range must never authorise the removal of another.
 * * **An unfinished form is not "everything".** A date mode with no date is
 *   not decidable, and turning it into the widest deletion is the one mistake
 *   `rangeFor` exists to not make.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const previewMemoryPurge = vi.fn();
const purgeMemory = vi.fn();

vi.mock('@/services/settingsClient', () => ({
  previewMemoryPurge: (r: unknown) => previewMemoryPurge(r),
  purgeMemory: (r: unknown) => purgeMemory(r),
}));

import PurgeMemory, { rangeFor } from './PurgeMemory';

const summary = (over: Record<string, unknown> = {}) => ({
  matched: 3,
  superseded: 0,
  deleted: 0,
  dryRun: true,
  scopes: ['global', 'project:a'],
  oldest: 1_759_000_000,
  newest: 1_759_500_000,
  ...over,
});

beforeEach(() => {
  previewMemoryPurge.mockReset().mockResolvedValue(summary());
  purgeMemory.mockReset().mockResolvedValue(summary({ deleted: 3, dryRun: false }));
});
afterEach(() => cleanup());

const user = () => userEvent.setup();

describe('rangeFor', () => {
  it('is everything only when asked for everything', () => {
    expect(rangeFor('all', '', '')).toEqual({});
  });

  it('is undecidable, not everything, when a date mode has no date', () => {
    expect(rangeFor('before', '', '')).toBeNull();
    expect(rangeFor('since', '', '')).toBeNull();
    expect(rangeFor('between', '2026-10-01', '')).toBeNull();
  });

  it('puts "before" at the start of the day, so that day survives', () => {
    const start = new Date(2026, 9, 1).getTime() / 1000;
    expect(rangeFor('before', '2026-10-01', '')).toEqual({ before: start });
  });

  it('includes the whole of the day it starts from', () => {
    const start = new Date(2026, 9, 1).getTime() / 1000;
    const range = rangeFor('since', '2026-10-01', '')!;
    expect(range.after).toBeLessThan(start);
    expect(start - range.after!).toBeLessThan(1);
  });

  it('includes both end days in a between range', () => {
    const range = rangeFor('between', '2026-10-01', '2026-10-02')!;
    expect(range.before! - range.after!).toBeGreaterThan(2 * 86_400 - 1);
  });

  it('refuses a swapped pair', () => {
    expect(rangeFor('between', '2026-10-05', '2026-10-01')).toBeNull();
  });
});

describe('the flow', () => {
  async function choose(date = '2026-10-01') {
    render(<PurgeMemory />);
    fireEvent.change(screen.getByTestId('purge-from'), { target: { value: date } });
  }

  it('cannot count until a date is chosen', () => {
    render(<PurgeMemory />);
    expect(screen.getByTestId('purge-count')).toBeDisabled();
  });

  it('shows no delete button before a count', async () => {
    await choose();
    expect(screen.queryByTestId('purge-remove')).toBeNull();
  });

  it('counts without deleting', async () => {
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    expect(await screen.findByTestId('purge-preview')).toHaveTextContent('3 facts');
    expect(previewMemoryPurge).toHaveBeenCalledTimes(1);
    expect(purgeMemory).not.toHaveBeenCalled();
  });

  it('puts the number on the button that deletes', async () => {
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    expect(await screen.findByTestId('purge-remove')).toHaveTextContent('Remove 3 facts');
  });

  it('deletes only after the button is pressed, and reports what went', async () => {
    await choose();
    const u = user();
    await u.click(screen.getByTestId('purge-count'));
    await u.click(await screen.findByTestId('purge-remove'));
    expect(await screen.findByTestId('purge-result')).toHaveTextContent('Removed 3 facts');
    expect(purgeMemory).toHaveBeenCalledTimes(1);
  });

  it('throws the count away when the date changes', async () => {
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    await screen.findByTestId('purge-remove');
    fireEvent.change(screen.getByTestId('purge-from'), { target: { value: '2026-09-01' } });
    await waitFor(() => expect(screen.queryByTestId('purge-remove')).toBeNull());
  });

  it('throws the count away when the mode changes', async () => {
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    await screen.findByTestId('purge-remove');
    fireEvent.change(screen.getByTestId('purge-mode'), { target: { value: 'all' } });
    await waitFor(() => expect(screen.queryByTestId('purge-remove')).toBeNull());
  });

  it('names the earlier versions of corrected facts, apart from the count', async () => {
    previewMemoryPurge.mockResolvedValue(summary({ superseded: 2 }));
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    expect(await screen.findByTestId('purge-preview')).toHaveTextContent(
      '3 facts, from',
    );
    expect(screen.getByTestId('purge-preview')).toHaveTextContent('plus 2 earlier versions of facts you corrected');
    expect(screen.getByTestId('purge-remove')).toHaveTextContent('Remove 3 facts and 2 earlier versions');
  });

  it('still offers the removal when only earlier versions are in range', async () => {
    previewMemoryPurge.mockResolvedValue(summary({ matched: 0, superseded: 1, scopes: [] }));
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    expect(await screen.findByTestId('purge-remove')).toHaveTextContent('Remove 0 facts and 1 earlier version');
  });

  it('says so, and offers nothing to remove, when nothing matches', async () => {
    previewMemoryPurge.mockResolvedValue(summary({ matched: 0, superseded: 0, scopes: [], oldest: null, newest: null }));
    await choose();
    await user().click(screen.getByTestId('purge-count'));
    expect(await screen.findByTestId('purge-preview')).toHaveTextContent('Nothing matches');
    expect(screen.queryByTestId('purge-remove')).toBeNull();
  });

  it('reports a failure and removes nothing', async () => {
    purgeMemory.mockRejectedValue(new Error('Memory runtime not available'));
    await choose();
    const u = user();
    await u.click(screen.getByTestId('purge-count'));
    await u.click(await screen.findByTestId('purge-remove'));
    expect(await screen.findByTestId('purge-error')).toHaveTextContent('Memory runtime not available');
    expect(screen.queryByTestId('purge-result')).toBeNull();
  });
});
