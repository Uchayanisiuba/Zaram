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

import { fetchSources } from '@/services/ingestClient';
import { fetchReadiness } from '@/services/readinessClient';
import { fetchServers } from '@/services/toolsClient';
import EmptyConversation from './EmptyConversation';

const lit = () =>
  [...document.querySelectorAll('[data-testid="starter-task"]')].filter((li) => (li as HTMLElement).dataset.ready === 'true');

beforeEach(() => {
  vi.mocked(fetchSources).mockResolvedValue([] as never);
  vi.mocked(fetchReadiness).mockResolvedValue({ canChat: false } as never);
  vi.mocked(fetchServers).mockResolvedValue([] as never);
  global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ projects: [] }) })) as never;
});

describe('EmptyConversation', () => {
  it('lights a row and offers Start once its requirement is measurably met', async () => {
    vi.mocked(fetchReadiness).mockResolvedValue({ canChat: true } as never);

    render(<EmptyConversation onPick={vi.fn()} />);

    await waitFor(() => expect(lit()).toHaveLength(1));
    expect(screen.getByText('Start →')).toBeTruthy();
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

    await waitFor(() => expect(lit()).toHaveLength(1));

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
