/**
 * @vitest-environment jsdom
 *
 * Finding a conversation in a list of fifty.
 *
 * Asked for 3 October 2026 from a screenshot of this panel beside Claude's.
 * The screenshot is the whole argument: a flat list grouped by date, reading
 * `hello`, `hello`, `hello`, `it should also accept negatives`, twice.
 * Nothing in it is findable.
 *
 * **The titles are not the thing to fix**, and that is a decision rather than
 * an omission. `title_from`'s reasoning holds — a generated title spends an
 * inference call on a label, on the path the product's speed argument lives
 * on, and invents wording the person never used, so the list becomes
 * searchable by everything except the words they remember typing. The answer
 * to `hello` five times is to search what was *said*, group by the project it
 * was said in, and pin the thread you keep returning to.
 *
 * Its own file rather than additions to `HistoryPanel.test.tsx`, because that
 * one mocks the client down to two functions on purpose — it is about the lip
 * and the timers, and widening its mock would make it carry a concern it was
 * written to exclude.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchConversations = vi.fn();
const searchConversations = vi.fn();
const pinConversation = vi.fn();
const deleteConversation = vi.fn(async () => ({ note: '' }));

vi.mock('@/services/conversationsClient', () => ({
  fetchConversations: (...a: unknown[]) => fetchConversations(...(a as [])),
  searchConversations: (...a: unknown[]) => searchConversations(...(a as [])),
  pinConversation: (...a: unknown[]) => pinConversation(...(a as [])),
  deleteConversation: (...a: unknown[]) => deleteConversation(...(a as [])),
}));

vi.mock('@/stores/projectStore', () => ({
  useProjectStore: (select: (s: unknown) => unknown) =>
    select({
      projects: [
        { id: 'keyline', name: 'Keyline' },
        { id: 'ride-share', name: 'Ride Share' },
      ],
    }),
}));

import HistoryPanel from './HistoryPanel';

function row(over: Record<string, unknown> = {}) {
  return {
    id: 'c1',
    title: 'hello',
    projectId: '',
    createdAt: 1,
    updatedAt: 1,
    messageCount: 2,
    pinned: false,
    ...over,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchConversations.mockReset().mockResolvedValue([]);
  searchConversations.mockReset().mockResolvedValue([]);
  pinConversation.mockReset().mockResolvedValue(row());
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const user = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

/** Open it the way a person does, then let the load settle. */
async function open() {
  render(<HistoryPanel />);
  await user().click(screen.getByRole('button', { name: /past conversations/i }));
  await act(async () => {
    vi.advanceTimersByTime(400);
  });
}

describe('grouping', () => {
  it('groups by project, not by day', async () => {
    fetchConversations.mockResolvedValue([
      row({ id: 'a', title: 'the IK solver', projectId: 'keyline' }),
      row({ id: 'b', title: 'pricing', projectId: 'ride-share' }),
    ]);
    await open();
    expect(screen.getByText('Keyline')).toBeTruthy();
    expect(screen.getByText('Ride Share')).toBeTruthy();
  });

  it('puts the ones in no project last, under Elsewhere', async () => {
    // A quick question must not push a month of project work below the fold.
    fetchConversations.mockResolvedValue([
      row({ id: 'loose', title: 'hello', projectId: '' }),
      row({ id: 'a', title: 'the IK solver', projectId: 'keyline' }),
    ]);
    await open();
    const headings = screen.getAllByText(/Keyline|Elsewhere/);
    expect(headings.map((h) => h.textContent)).toEqual(['Keyline', 'Elsewhere']);
  });

  it('pinned leads, as its own group', async () => {
    fetchConversations.mockResolvedValue([
      row({ id: 'a', title: 'the IK solver', projectId: 'keyline' }),
      row({ id: 'kept', title: 'the long thread', projectId: 'keyline', pinned: true }),
    ]);
    await open();
    const headings = screen.getAllByText(/Pinned|Keyline/);
    expect(headings[0].textContent).toBe('Pinned');
  });

  it('names a project Zaram does not recognise by its id rather than blankly', async () => {
    // A deleted project still has conversations scoped to it, and an empty
    // heading is worse than an ugly one.
    fetchConversations.mockResolvedValue([
      row({ id: 'a', title: 'orphan', projectId: 'gone-away' }),
    ]);
    await open();
    expect(screen.getByText('gone-away')).toBeTruthy();
  });
});

describe('search', () => {
  it('asks the backend, debounced', async () => {
    await open();
    await user().type(screen.getByTestId('history-search'), 'IK solver');
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(searchConversations).toHaveBeenCalled();
    expect(searchConversations.mock.calls[searchConversations.mock.calls.length - 1]?.[0]).toBe('IK solver');
  });

  it('goes back to the plain list when cleared', async () => {
    await open();
    const box = screen.getByTestId('history-search');
    await user().type(box, 'x');
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    fetchConversations.mockClear();
    await user().clear(box);
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(fetchConversations).toHaveBeenCalled();
  });

  it('tells "nothing matched" apart from "nothing exists"', async () => {
    // One is a search to change; the other is a product that has not been
    // used yet. Sharing a sentence makes the first look like the second.
    await open();
    expect(screen.getByText(/Nothing here yet/i)).toBeTruthy();

    await user().type(screen.getByTestId('history-search'), 'zzz');
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByText(/Nothing matched/i)).toBeTruthy();
    expect(screen.queryByText(/Nothing here yet/i)).toBeNull();
  });
});

describe('pinning', () => {
  it('moves the row before the request comes back', async () => {
    // A pin that waits for a round trip before the row moves reads as a
    // press that did nothing.
    let settle: (v: unknown) => void = () => {};
    pinConversation.mockReturnValue(new Promise((r) => (settle = r)));
    fetchConversations.mockResolvedValue([
      row({ id: 'a', title: 'the IK solver', projectId: 'keyline' }),
    ]);
    await open();

    await user().click(screen.getByTestId('pin-a'));
    expect(screen.getByText('Pinned')).toBeTruthy();
    await act(async () => {
      settle(row({ id: 'a', pinned: true }));
    });
  });

  it('puts it back if the request fails', async () => {
    // A list that silently disagrees with the database is worse than one
    // that visibly refused.
    pinConversation.mockRejectedValue(new Error('no'));
    fetchConversations.mockResolvedValue([
      row({ id: 'a', title: 'the IK solver', projectId: 'keyline' }),
    ]);
    await open();

    await user().click(screen.getByTestId('pin-a'));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText('Pinned')).toBeNull();
    expect(screen.getByText(/could not be pinned/i)).toBeTruthy();
  });

  it('sends only the pin, never the title', async () => {
    // A client that resent the title would overwrite one the person had
    // just edited in another window.
    fetchConversations.mockResolvedValue([row({ id: 'a', projectId: 'keyline' })]);
    await open();
    await user().click(screen.getByTestId('pin-a'));
    expect(pinConversation).toHaveBeenCalledWith('a', true);
  });

  it('does not resume the conversation it pins', async () => {
    fetchConversations.mockResolvedValue([row({ id: 'a', projectId: 'keyline' })]);
    await open();
    await user().click(screen.getByTestId('pin-a'));
    // Resuming would have closed the panel; the search box is the witness
    // that it is still open.
    expect(screen.getByTestId('history-search')).toBeTruthy();
  });
});
