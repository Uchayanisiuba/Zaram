/**
 * What runs on its own, configured under Settings — coworker step 4.
 *
 * Held here: a trigger is made from a kind, a day, a time and a question;
 * the obligations kind needs no question; a paused trigger says why and
 * offers Turn on; Run now reports how it ended in words; and a list that
 * could not be read is never shown as empty.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';

const fetchTriggers = vi.fn();
const createTrigger = vi.fn();
const setTriggerEnabled = vi.fn();
const deleteTrigger = vi.fn();
const runTriggerNow = vi.fn();

vi.mock('@/services/triggersClient', async () => {
  const real = await vi.importActual<typeof import('@/services/triggersClient')>('@/services/triggersClient');
  return {
    ...real,
    fetchTriggers: (...a: unknown[]) => fetchTriggers(...a),
    createTrigger: (...a: unknown[]) => createTrigger(...a),
    setTriggerEnabled: (...a: unknown[]) => setTriggerEnabled(...a),
    deleteTrigger: (...a: unknown[]) => deleteTrigger(...a),
    runTriggerNow: (...a: unknown[]) => runTriggerNow(...a),
  };
});

import RunsOnItsOwnSection from './RunsOnItsOwnSection';

const Row = ({ label, detail }: { label: string; detail?: React.ReactNode }) => (
  <div data-testid="row">
    {label}
    {detail}
  </div>
);

const trigger = (over: Record<string, unknown> = {}) => ({
  id: 't1',
  question: "The month's picture.",
  kind: 'weekly',
  at: '09:00',
  weekday: 'mon',
  daysAhead: 7,
  projectId: '',
  enabled: true,
  lastRunAt: 0,
  nextRunAt: 1_790_000_000,
  heldInARow: 0,
  pausedReason: '',
  ...over,
});

beforeEach(() => {
  fetchTriggers.mockResolvedValue({ triggers: [], runs: [] });
  createTrigger.mockResolvedValue(trigger());
  setTriggerEnabled.mockResolvedValue(trigger({ enabled: false }));
  deleteTrigger.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('runs on its own', () => {
  it('says what a trigger is when there is none, and never suggests one', async () => {
    render(<RunsOnItsOwnSection Row={Row} />);
    await waitFor(() => expect(screen.getByText(/never approves anything on its own/)).toBeTruthy());
    expect(screen.queryByText(/set up/i)).toBeNull();
  });

  it('never shows an empty list for a fetch that failed', async () => {
    fetchTriggers.mockRejectedValue(new Error('backend away'));
    render(<RunsOnItsOwnSection Row={Row} />);
    await waitFor(() => expect(screen.getByText(/backend away/)).toBeTruthy());
    expect(screen.queryByText(/Nothing yet/)).toBeNull();
  });

  it('makes a weekly trigger from a day, a time and a question', async () => {
    render(<RunsOnItsOwnSection Row={Row} />);
    await screen.findByTestId('trigger-form');
    const add = screen.getByTestId('trigger-add') as HTMLButtonElement;
    expect(add.disabled).toBe(true);

    fireEvent.change(screen.getByTestId('trigger-question'), { target: { value: "The month's picture." } });
    fireEvent.click(screen.getByTestId('trigger-add'));

    await waitFor(() =>
      expect(createTrigger).toHaveBeenCalledWith({
        question: "The month's picture.",
        kind: 'weekly',
        at: '09:00',
        weekday: 'mon',
        daysAhead: 7,
      }),
    );
  });

  it('the obligations kind needs no question', async () => {
    render(<RunsOnItsOwnSection Row={Row} />);
    await screen.findByTestId('trigger-form');
    fireEvent.change(screen.getByTestId('trigger-kind'), { target: { value: 'obligations' } });
    expect(screen.queryByTestId('trigger-question')).toBeNull();
    expect((screen.getByTestId('trigger-add') as HTMLButtonElement).disabled).toBe(false);
  });

  it('lists a trigger with its schedule and next run, and can turn it off', async () => {
    fetchTriggers.mockResolvedValue({ triggers: [trigger()], runs: [] });
    render(<RunsOnItsOwnSection Row={Row} />);
    const row = await screen.findByTestId('trigger-row');
    expect(row.textContent).toContain('Mondays at 09:00');
    expect(row.textContent).toContain('Next:');
    fireEvent.click(screen.getByTestId('trigger-toggle'));
    await waitFor(() => expect(setTriggerEnabled).toHaveBeenCalledWith('t1', false));
  });

  it('a paused trigger says why, and Turn on is the way back', async () => {
    fetchTriggers.mockResolvedValue({
      triggers: [trigger({ pausedReason: 'Paused: the last 3 runs each stopped at something that needed you.' })],
      runs: [],
    });
    render(<RunsOnItsOwnSection Row={Row} />);
    const row = await screen.findByTestId('trigger-row');
    expect(row.getAttribute('data-state')).toBe('warn');
    expect(row.textContent).toContain('Paused: the last 3 runs');
    expect(screen.getByTestId('trigger-toggle').textContent).toBe('Turn on');
  });

  it('Run now says how it ended, in words', async () => {
    fetchTriggers.mockResolvedValue({ triggers: [trigger()], runs: [] });
    runTriggerNow.mockResolvedValue([
      { id: 'r', triggerId: 't1', startedAt: 1, finishedAt: 2, outcome: 'held', conversationId: 'c', question: 'q', obligationId: '', note: 'held at email/send' },
    ]);
    render(<RunsOnItsOwnSection Row={Row} />);
    await screen.findByTestId('trigger-row');
    fireEvent.click(screen.getByTestId('trigger-run-now'));
    await waitFor(() => expect(screen.getByTestId('trigger-said').textContent).toContain('held at email/send'));
  });
});
