/**
 * What the empty conversation actually renders, on a machine where some things
 * are ready and some are not.
 *
 * The unlit case was watched on the real screen on 15 September 2026 with the
 * engine down — three rows, no dot lit, each carrying its own setup. This file
 * is the other half: the lit row, which needs a backend that can answer, and
 * which belongs in the suite rather than in one look at a running product.
 *
 * The dot is a claim about this machine. The two failures worth guarding are a
 * dot lit by something nobody measured, and a "Start" on a row that cannot
 * start — both of which tell somebody a capability is there when it is not.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

vi.mock('@/services/obligationsClient', () => ({
  fetchObligations: vi.fn(async () => []),
  countObligations: vi.fn(() => ({ open: 0, overdue: 0 })),
}));
vi.mock('@/services/ingestClient', () => ({ fetchSources: vi.fn(async () => []) }));
vi.mock('@/services/readinessClient', () => ({ fetchReadiness: vi.fn(async () => ({ canChat: false })) }));
vi.mock('@/services/toolsClient', () => ({ fetchServers: vi.fn(async () => []) }));
vi.mock('@/services/conversationsClient', () => ({ fetchConversations: vi.fn(async () => []) }));
vi.mock('@/services/plansClient', () => ({ listUnfinished: vi.fn(async () => ({ plans: [], finished: [], kept_for_days: 7 })) }));

import { fetchSources } from '@/services/ingestClient';
import { fetchReadiness } from '@/services/readinessClient';
import { fetchServers } from '@/services/toolsClient';
import { listUnfinished } from '@/services/plansClient';
import EmptyConversation from './EmptyConversation';

const lit = () =>
  [...document.querySelectorAll('[data-testid="starter-task"]')].filter((li) => (li as HTMLElement).dataset.ready === 'true');

beforeEach(() => {
  vi.mocked(fetchSources).mockResolvedValue([] as never);
  vi.mocked(fetchReadiness).mockResolvedValue({ canChat: false } as never);
  vi.mocked(fetchServers).mockResolvedValue([] as never);
  globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ projects: [] }) })) as never;
});

describe('EmptyConversation', () => {
  it('lights a row and offers Start once its requirement is measurably met', async () => {
    vi.mocked(fetchReadiness).mockResolvedValue({ canChat: true } as never);

    render(<EmptyConversation onPick={vi.fn()} />);

    // Two of the first three need only a model: the document, and coding a
    // project, which since F1 needs no tool attached in advance.
    await waitFor(() => expect(lit()).toHaveLength(2));
    expect(screen.getAllByText('Start →').length).toBeGreaterThan(0);
  });

  it('leaves every dot unlit when nothing could be read, and shows the setup instead', async () => {
    // The engine-down case, which is what a fresh install looks like too.
    vi.mocked(fetchReadiness).mockRejectedValue(new Error('offline'));
    vi.mocked(fetchSources).mockRejectedValue(new Error('offline'));
    vi.mocked(fetchServers).mockRejectedValue(new Error('offline'));

    render(<EmptyConversation onPick={vi.fn()} />);

    await waitFor(() => expect(document.querySelectorAll('[data-testid="starter-task"]')).toHaveLength(3));
    expect(lit()).toHaveLength(0);
    // A failed fetch must never light a dot; the row says what to do instead.
    expect(screen.getByText(/Point Zaram at a folder/)).toBeTruthy();
    expect(screen.queryByText('Start →')).toBeNull();
  });

  it('puts a ready task in the composer, and sends an unready one to its setup', async () => {
    vi.mocked(fetchReadiness).mockResolvedValue({ canChat: true } as never);
    const onPick = vi.fn();
    const onNavigate = vi.fn();

    render(<EmptyConversation onPick={onPick} onNavigate={onNavigate} />);

    await waitFor(() => expect(lit()).toHaveLength(2));

    fireEvent.click(lit()[0].querySelector('button')!);
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onNavigate).not.toHaveBeenCalled();

    const unready = [...document.querySelectorAll('[data-testid="starter-task"]')].find(
      (li) => (li as HTMLElement).dataset.ready === 'false',
    )!;
    fireEvent.click(unready.querySelector('button')!);
    // The setup is the row's meaning when it is not ready — it must not drop a
    // prompt into the composer that cannot run.
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it('shows the outcome under every row, not the feature name', async () => {
    render(<EmptyConversation onPick={vi.fn()} />);
    await waitFor(() => expect(document.querySelectorAll('[data-testid="starter-task"]')).toHaveLength(3));
    expect(screen.getByText(/A document in Work, written from your words/)).toBeTruthy();
  });
});

describe('the rest of what Zaram does', () => {
  it('sits behind one line and unfolds to all of them', async () => {
    render(<EmptyConversation onPick={vi.fn()} />);

    await waitFor(() => expect(document.querySelectorAll('[data-testid="starter-task"]')).toHaveLength(3));
    const more = screen.getByTestId('starter-more');
    expect(more.textContent).toContain('4 more');

    fireEvent.click(more);
    await waitFor(() => expect(document.querySelectorAll('[data-testid="starter-task"]')).toHaveLength(7));
    expect(screen.getByText(/Turn web search on/)).toBeTruthy();
    expect(screen.getByText(/Attach your mail/)).toBeTruthy();
    expect(screen.getByText(/Attach GitHub/)).toBeTruthy();
  });
});

describe('the row about what is unfinished', () => {
  const now = () => Date.now() / 1000;
  const seed = (plans: object[]) => {
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ projects: [{ id: 'ride-share', name: 'Ride Share', facts: 0 }] }),
    })) as never;
    vi.mocked(listUnfinished).mockResolvedValue({ plans, finished: [], kept_for_days: 7 } as never);
  };
  const task = (id: string, over: object = {}) => ({
    id,
    question: `question ${id}`,
    project_id: 'ride-share',
    finished: false,
    steps: [],
    items: [],
    created_at: now() - 1000,
    updated_at: now() - 60,
    ...over,
  });

  it('is first, names the project, and with one task just does it', async () => {
    seed([task('plan-1')]);
    const onPick = vi.fn();
    render(<EmptyConversation onPick={onPick} />);

    const row = await screen.findByText('What are the unfinished tasks in Ride Share?');
    expect(document.querySelector('[data-testid="grounded-prompt"]')).toBe(row.closest('button'));
    expect(screen.getByText(/1 unfinished task · last touched today/)).toBeTruthy();

    fireEvent.click(row);
    expect(screen.queryByTestId('waiting-tasks')).toBeNull();
    expect(onPick).toHaveBeenCalledTimes(1);
    const [prompt, action] = onPick.mock.calls[0];
    expect(prompt).toBe('What are the unfinished tasks in Ride Share?');
    expect(action.kind).toBe('continue-tasks');
    expect(action.tasks.map((t: { id: string }) => t.id)).toEqual(['plan-1']);
  });

  it('with several, lays them all out first and runs nothing until one is chosen', async () => {
    seed([
      task('new', { created_at: now() - 100, items: [{ text: 'a', status: 'done' }, { text: 'b', status: 'todo' }] }),
      task('old', { created_at: now() - 900 }),
    ]);
    const onPick = vi.fn();
    render(<EmptyConversation onPick={onPick} />);

    fireEvent.click(await screen.findByText('What are the unfinished tasks in Ride Share?'));

    expect(onPick).not.toHaveBeenCalled();
    const rows = screen.getAllByTestId('waiting-task').map((li) => li.textContent);
    // Oldest first, with how far each got -- or that it never was planned.
    expect(rows[0]).toContain('question old');
    expect(rows[0]).toContain('not planned yet');
    expect(rows[1]).toContain('question new');
    expect(rows[1]).toContain('1 of 2 done');

    fireEvent.click(screen.getByTestId('run-all-tasks'));
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onPick.mock.calls[0][1].tasks.map((t: { id: string }) => t.id)).toEqual(['old', 'new']);
  });

  it('can run just one of several', async () => {
    seed([task('old', { created_at: now() - 900 }), task('new', { created_at: now() - 100 })]);
    const onPick = vi.fn();
    render(<EmptyConversation onPick={onPick} />);

    fireEvent.click(await screen.findByText('What are the unfinished tasks in Ride Share?'));
    fireEvent.click(screen.getAllByTestId('run-one-task')[1]);

    expect(onPick.mock.calls[0][1].tasks.map((t: { id: string }) => t.id)).toEqual(['new']);
  });

  it('is absent when nothing is unfinished', async () => {
    render(<EmptyConversation onPick={vi.fn()} />);
    await waitFor(() => expect(document.querySelectorAll('[data-testid="starter-task"]').length).toBeGreaterThan(0));
    expect(screen.queryByText(/unfinished tasks in/)).toBeNull();
  });
});
