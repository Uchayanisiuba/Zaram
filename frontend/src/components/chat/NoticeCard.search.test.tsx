/**
 * The search notice offers to search, rather than pointing at a settings screen.
 *
 * Rule 7h: *"Offer at the moment of doubt; never make the user choose in
 * advance."* The notice was arriving at exactly the right moment — mid-answer,
 * saying this one may be stale — with a link to Settings. Nobody goes to
 * Settings. They read the stale answer, and what the disclosure has taught them
 * is that Zaram is worse than the browser tab already open.
 *
 * Two things are asserted that a friendlier version would drop:
 *
 * * **The cost is on the card, not behind it.** Turning search on means the
 *   question itself leaves the machine. That sentence sits under the button
 *   where it cannot be missed, in the same posture `CloudKeyForm` takes with a
 *   provider's data policy.
 * * **The offer appears only where it is true.** A notice about a file that
 *   could not be read must not grow a "search the web" button, and the search
 *   notice must not keep the Settings link as well — two actions on a card this
 *   size is a choice, and the point of the offer is that there isn't one.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import NoticeCard from './NoticeCard';
import type { ChatNotice } from '@/stores/chatStore';

const SEARCH: ChatNotice = {
  content:
    'This looks like it needs current information. Web search is off, so this ' +
    'answer comes only from what the model already knows.',
  kind: 'search',
  action: 'settings',
};

const INGEST: ChatNotice = {
  content: 'brief.pdf gave nothing back.',
  kind: 'ingest',
  action: 'knowledge',
};

afterEach(cleanup);

describe('the offer', () => {
  it('is a button that searches, not a link to a screen', async () => {
    const onEnableSearch = vi.fn().mockResolvedValue(undefined);
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={onEnableSearch} />);

    await userEvent.click(screen.getByTestId('notice-enable-search'));

    expect(onEnableSearch).toHaveBeenCalledOnce();
  });

  it('replaces the settings link rather than sitting beside it', () => {
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={vi.fn()} />);

    expect(screen.queryByTestId('notice-action')).toBeNull();
  });

  it('says the question leaves the machine, before it is pressed', () => {
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={vi.fn()} />);

    expect(screen.getByText(/goes to a search engine/i)).toBeTruthy();
  });

  it('says the destination is permitted from now on, not just this once', () => {
    /** The press does two things — turns search on *and* permits the search
     *  engine — and the first version disclosed only the first while doing
     *  only the first, which is why the search then came back empty. Rule 7j
     *  makes the grant right; this makes it stated. */
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={vi.fn()} />);

    expect(screen.getByText(/allowed from now on/i)).toBeTruthy();
    expect(screen.getByText(/revoke it in Settings/i)).toBeTruthy();
  });

  it('goes back to its normal label once it has run', async () => {
    /** The card lives in the transcript, so it is still on screen after the
     *  retry. Without the reset it sat reading "Turning it on…" for the rest
     *  of the session, over a question already answered again. */
    const onEnableSearch = vi.fn().mockResolvedValue(undefined);
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={onEnableSearch} />);

    await userEvent.click(screen.getByTestId('notice-enable-search'));

    await waitFor(() =>
      expect(screen.getByTestId('notice-enable-search').textContent).toContain(
        'Search the web and try again',
      ),
    );
  });

  it('says so when it could not be turned on', async () => {
    /** A control that appears to work and does not is worse than one that
     *  admits it failed — and the remedy names where the switch actually is. */
    const onEnableSearch = vi.fn().mockRejectedValue(new Error('offline'));
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} onEnableSearch={onEnableSearch} />);

    await userEvent.click(screen.getByTestId('notice-enable-search'));

    await waitFor(() =>
      expect(screen.getByText(/could not turn search on/i)).toBeTruthy(),
    );
  });
});

describe('where the offer does not belong', () => {
  it('is absent on a notice about something else', () => {
    render(<NoticeCard notice={INGEST} onOpen={vi.fn()} onEnableSearch={vi.fn()} />);

    expect(screen.queryByTestId('notice-enable-search')).toBeNull();
    expect(screen.getByTestId('notice-action')).toBeTruthy();
  });

  it('falls back to the settings link when no handler is given', () => {
    /** Every existing caller, and every test that renders a notice alone. */
    render(<NoticeCard notice={SEARCH} onOpen={vi.fn()} />);

    expect(screen.queryByTestId('notice-enable-search')).toBeNull();
    expect(screen.getByTestId('notice-action')).toBeTruthy();
  });
});
