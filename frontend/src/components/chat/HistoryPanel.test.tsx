/**
 * The lip at the left edge, and whether it still opens.
 *
 * Written because the maintainer reported that it had stopped: *"it used to
 * cascade out the conversation history and new chat panel but it's no longer
 * working."* Reading the component found nothing, which is exactly the point
 * at which this repository stops reading and asks the code — the panel is
 * three pieces of state, two timers and a stacking context, and only one of
 * those is visible in a diff.
 *
 * The assertions are about the two gestures the component's own note promises
 * — *"hover peeks; click pins"* — plus the one that is easy to lose silently:
 * that a panel which is closed does not sit invisibly over the control that
 * opens it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import HistoryPanel from './HistoryPanel';

const fetchConversations = vi.fn(async () => []);
const deleteConversation = vi.fn(async () => ({ note: '' }));

vi.mock('@/services/conversationsClient', () => ({
  fetchConversations: (...args: unknown[]) => fetchConversations(...(args as [])),
  deleteConversation: (...args: unknown[]) => deleteConversation(...(args as [])),
}));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchConversations.mockClear();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const user = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

/** The panel, however it is currently spelled. */
const panel = () => screen.getByRole('complementary', { hidden: true });

/** Whether the panel is showing. Read off what actually decides it on screen —
 *  a panel that is `visibility: hidden` is not open however truthy the state
 *  behind it is. */
const isOpen = () => panel().style.visibility === 'visible';

describe('the lip opens the panel', () => {
  it('is closed to begin with', () => {
    render(<HistoryPanel />);
    expect(isOpen()).toBe(false);
  });

  it('pins it on a click', async () => {
    render(<HistoryPanel />);

    await user().click(screen.getByRole('button', { name: /past conversations/i }));

    expect(isOpen()).toBe(true);
  });

  it('peeks on hover, after the delay', async () => {
    render(<HistoryPanel />);
    const lip = screen.getByRole('button', { name: /past conversations/i });

    await user().hover(lip);
    expect(isOpen()).toBe(false); // crossing the edge is not reaching for it

    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(isOpen()).toBe(true);
  });

  it('opens on focus, for a keyboard', async () => {
    render(<HistoryPanel />);

    await act(async () => {
      screen.getByRole('button', { name: /past conversations/i }).focus();
    });

    expect(isOpen()).toBe(true);
  });

  it('shows the new-conversation control once open', async () => {
    render(<HistoryPanel />);

    await user().click(screen.getByRole('button', { name: /past conversations/i }));

    expect(screen.getByRole('button', { name: 'New' })).toBeInTheDocument();
  });

  it('reads the list only once it is open', async () => {
    // An ambient panel that fetches on every page load spends a request on a
    // surface nobody asked for.
    render(<HistoryPanel />);
    expect(fetchConversations).not.toHaveBeenCalled();

    await user().click(screen.getByRole('button', { name: /past conversations/i }));
    expect(fetchConversations).toHaveBeenCalled();
  });
});

describe('the closed panel does not sit over its own control', () => {
  it('is hidden rather than merely transparent', () => {
    // `opacity: 0` alone leaves a 264px-wide element with pointer events
    // covering the left edge — including the 22px lip that opens it. The
    // control would look present, do nothing, and read exactly as "the button
    // stopped working".
    render(<HistoryPanel />);
    expect(panel().style.visibility).toBe('hidden');
  });
});

describe('the lip cannot become invisible', () => {
  /**
   * The regression this file was written for, asserted as the property rather
   * than as the browser behaviour.
   *
   * Measured on the running app: after one open-and-close, a `CSSTransition`
   * on the lip's opacity stalled at `currentTime: 0` and the computed value
   * stayed `0` for the rest of the session while the inline style said `1`. The
   * control remained mounted and hit-testable — an invisible 22px strip at the
   * screen edge, which is unaimable and reads as a button that stopped working.
   *
   * jsdom runs no transitions, so it cannot reproduce a stalled one. What it
   * can hold is the invariant that makes the stall impossible: **whether this
   * control can be seen is never the output of an animation.** A test that
   * chased the mechanism would assert something jsdom does not have; this one
   * asserts the thing the fix actually relies on.
   */
  const lip = () => screen.getByRole('button', { name: /past conversations/i });

  it('does not transition its opacity', () => {
    render(<HistoryPanel />);
    expect(lip().style.transition).not.toMatch(/opacity/);
  });

  it('is fully opaque while closed', () => {
    render(<HistoryPanel />);
    expect(lip().style.opacity).toBe('1');
  });

  it('is fully opaque again the moment the panel closes', async () => {
    render(<HistoryPanel />);

    await user().click(lip());
    expect(lip().style.opacity).toBe('0'); // the panel is over it

    await user().click(screen.getByRole('button', { name: 'Close history' }));
    expect(lip().style.opacity).toBe('1');
  });
});

/**
 * The lip opened the panel and could not close it.
 *
 * `onClick` set `pinned` to true unconditionally, so closing meant finding the
 * X inside the panel. The lip carries `aria-expanded`, which promises a
 * toggle, and the clearest way to meet that promise is the keyboard path: tab
 * to the lip, Enter to open, Enter again and nothing happened at all.
 *
 * Asserted on `aria-expanded` rather than on the panel's presence, because the
 * attribute is the claim being made and it is the one an assistive technology
 * reads.
 */
describe('the lip is a toggle', () => {
  it('opens on the first click and closes on the second', async () => {
    const user = userEvent.setup();
    render(<HistoryPanel />);

    const lip = screen.getByRole('button', { name: /past conversations/i });
    expect(lip).toHaveAttribute('aria-expanded', 'false');

    await user.click(lip);
    expect(lip).toHaveAttribute('aria-expanded', 'true');

    await user.click(lip);
    expect(lip).toHaveAttribute('aria-expanded', 'false');
  });
});
