/**
 * A notice that offers to take you somewhere has to actually take you there.
 *
 * **This shipped broken and nothing noticed.** `ChatSurface` wired the card's
 * `onOpen` to `useConversationStore.setActiveNode`, and `activeNode` has no
 * reader outside `src/legacy/`, which is not mounted. So "Open Settings →"
 * set a field and returned. Reported by the maintainer on 28 August 2026, who
 * clicked it and nothing happened.
 *
 * `npm run check:reachability` cannot see that defect, and it is worth being
 * precise about why: the export *was* used. The call went somewhere. It simply
 * had no effect, which is a shape no import graph can distinguish from working
 * code.
 *
 * **Be clear about what these tests do and do not catch.** This card was never
 * the broken part — it has always called `onOpen` with the right node, and
 * every case below would have passed on the day the bug was reported. What
 * they pin is the card's own contract: which node each action resolves to, and
 * that a notice naming no destination offers no button.
 *
 * The *wiring* is guarded somewhere else and deliberately not here.
 * `ChatSurface` now takes `navigate` as a **required** prop typed
 * `(id: WorkspaceId) => void`, so there is no store to quietly point it at and
 * `tsc` fails at the call site if nothing is passed. A compile error is a
 * better guard than a test for that class of mistake, because the mistake was
 * never a wrong value — it was a call that went nowhere.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import NoticeCard from './NoticeCard';
import type { ChatNotice } from '@/stores/chatStore';

const notice = (over: Partial<ChatNotice> = {}): ChatNotice =>
  ({
    content: 'Web search is off, so this answer comes only from what the model knows.',
    kind: 'search',
    action: 'settings',
    ...over,
  }) as ChatNotice;

describe('the action goes somewhere', () => {
  it('hands the destination node to the caller', () => {
    const navigate = vi.fn();
    render(<NoticeCard notice={notice()} onOpen={navigate} />);

    fireEvent.click(screen.getByTestId('notice-action'));

    // The node, not the action key. They happen to match for `settings` and
    // deliberately do not for others — see `DESTINATIONS`.
    expect(navigate).toHaveBeenCalledWith('settings');
  });

  it('sends a knowledge notice to Knowledge, not to Settings', () => {
    const navigate = vi.fn();
    render(
      <NoticeCard
        notice={notice({ action: 'knowledge', content: 'A file gave nothing back.' })}
        onOpen={navigate}
      />,
    );

    fireEvent.click(screen.getByTestId('notice-action'));

    expect(navigate).toHaveBeenCalledWith('knowledge');
  });

  it('offers no action when the notice names no destination', () => {
    const navigate = vi.fn();
    render(
      <NoticeCard
        notice={notice({ action: '', content: 'Answered inside your Investing domain.' })}
        onOpen={navigate}
      />,
    );

    // A notice about the user's own choice is a statement, not a prompt. A
    // button here would be the amber-triangle mistake in a different form.
    expect(screen.queryByTestId('notice-action')).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('renders the notice without an action when no handler was given', () => {
    render(<NoticeCard notice={notice()} />);

    // The text still has to arrive. A missing handler must not swallow the
    // disclosure along with the button.
    expect(screen.getByTestId('chat-notice')).toBeTruthy();
    expect(screen.queryByTestId('notice-action')).toBeNull();
  });
});

describe('continuing a task that ran out of room', () => {
  const stopped = () =>
    notice({
      kind: 'tool_loop',
      action: 'continue',
      content:
        'Zaram stopped after 3 tool calls — what it read has filled the 4,915 ' +
        'tokens this question can spend on reading.',
    });

  it('offers Continue and calls back when it is pressed', () => {
    const onContinue = vi.fn();
    render(<NoticeCard notice={stopped()} onContinue={onContinue} />);

    fireEvent.click(screen.getByTestId('notice-continue'));

    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it('is not a warning', () => {
    // Nothing went wrong: the model spent the allowance it was given. An amber
    // triangle here trains the warning away for the notices that need one.
    render(<NoticeCard notice={stopped()} onContinue={vi.fn()} />);

    expect(screen.getByTestId('chat-notice').getAttribute('data-kind')).toBe('tool_loop');
  });

  it('offers nothing when the handler is absent', () => {
    // A card rendered without the wiring must still deliver the sentence. The
    // disclosure is the part that cannot be optional.
    render(<NoticeCard notice={stopped()} />);

    expect(screen.getByTestId('chat-notice')).toBeTruthy();
    expect(screen.queryByTestId('notice-continue')).toBeNull();
  });

  it('does not offer Continue on a notice that is not about a stopped loop', () => {
    render(<NoticeCard notice={notice()} onContinue={vi.fn()} />);

    expect(screen.queryByTestId('notice-continue')).toBeNull();
  });
});
