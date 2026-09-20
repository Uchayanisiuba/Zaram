/**
 * What ran on its own, under Activity — coworker step 4.
 *
 * Nothing at all when nothing runs on its own; otherwise the runs newest
 * first, each saying how it ended, and *open* taking the person to the
 * conversation the run made. A paused trigger is said here too, because
 * Activity is where the person looks for what needs them.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';

const fetchTriggers = vi.fn();
const resume = vi.fn();

vi.mock('@/services/triggersClient', async () => {
  const real = await vi.importActual<typeof import('@/services/triggersClient')>('@/services/triggersClient');
  return { ...real, fetchTriggers: (...a: unknown[]) => fetchTriggers(...a) };
});
vi.mock('@/stores/chatStore', () => ({
  useChatStore: (selector: (s: { resumeConversation: typeof resume }) => unknown) =>
    selector({ resumeConversation: resume }),
}));

import { RunsSection } from './RunsSection';

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
  nextRunAt: null,
  heldInARow: 0,
  pausedReason: '',
  ...over,
});

const run = (over: Record<string, unknown> = {}) => ({
  id: 'r1',
  triggerId: 't1',
  startedAt: 1_789_910_022,
  finishedAt: 1_789_910_045,
  outcome: 'done',
  conversationId: 'conv_1',
  question: "The month's picture.",
  obligationId: '',
  note: '',
  ...over,
});

beforeEach(() => {
  fetchTriggers.mockResolvedValue({ triggers: [trigger()], runs: [run()] });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ran on its own', () => {
  it('renders nothing when nothing has run', async () => {
    fetchTriggers.mockResolvedValue({ triggers: [], runs: [] });
    const { container } = render(<RunsSection />);
    await waitFor(() => expect(fetchTriggers).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });

  it('lists a run and opens the conversation it made', async () => {
    const onOpen = vi.fn();
    render(<RunsSection onOpenConversation={onOpen} />);
    const row = await screen.findByTestId('run-row');
    expect(row.textContent).toContain("The month's picture.");
    expect(row.getAttribute('data-outcome')).toBe('done');

    fireEvent.click(screen.getByTestId('run-open'));

    expect(onOpen).toHaveBeenCalled();
    expect(resume).toHaveBeenCalledWith('conv_1');
  });

  it('a held run says what it stopped at, and a paused trigger says so', async () => {
    fetchTriggers.mockResolvedValue({
      triggers: [trigger({ pausedReason: 'Paused: the last 3 runs each stopped at something that needed you.' })],
      runs: [run({ outcome: 'held', note: 'held at email/send: needs you' })],
    });
    render(<RunsSection />);
    const row = await screen.findByTestId('run-row');
    expect(row.textContent).toContain('held at email/send');
    expect(screen.getByTestId('run-paused').textContent).toContain('Paused: the last 3 runs');
  });

  it('an obligations run is named by the obligation, not the prompt', async () => {
    fetchTriggers.mockResolvedValue({
      triggers: [trigger({ kind: 'obligations', question: '' })],
      runs: [
        run({
          obligationId: 'ob-1',
          question: 'An obligation is coming up: Northwind invoice 0042, due 2026-09-25. Draft the reply…',
        }),
      ],
    });
    render(<RunsSection />);
    const row = await screen.findByTestId('run-row');
    expect(row.textContent).toContain('Northwind invoice 0042, due 2026-09-25');
    expect(row.textContent).not.toContain('An obligation is coming up');
  });
});
