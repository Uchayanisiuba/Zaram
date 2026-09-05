/**
 * The dialog that decides what leaves.
 *
 * The backend already proves the hard half — that an edit is what gets logged
 * *and* what goes on the wire, asserted by comparing all three. None of that
 * helps if the interface posts back something other than what the user
 * approved, so this grades the one thing only this end can get wrong: the
 * distance between the chips a user struck and the body that is sent.
 *
 * The failure being guarded against is specific and quiet. A dialog that shows
 * a fact, lets the user remove it, and then posts the original body is worse
 * than no dialog at all, because the user believes the removal happened. It
 * would pass any test that only checked the chip disappeared from the screen.
 * So every assertion here ends at the request body, not at the DOM.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ConfirmSendDialog from './ConfirmSendDialog';
import type { PendingEgress } from '@/services/egressClient';

afterEach(cleanup);

const DAY_RATE = 'their day rate is 450,000 naira';
const PAYS_LATE = 'Northwind pays 30 days late';

function systemPrompt(): string {
  return [
    'You are Zaram.',
    '',
    '=== WHAT YOU REMEMBER ABOUT THIS USER ===',
    'These are facts from earlier exchanges, retrieved from local memory.',
    '',
    `[M1] (2026-08-11) ${DAY_RATE}`,
    `[M2] (2026-08-09) ${PAYS_LATE}`,
    '',
    'INSTRUCTIONS:',
    '- Use these memories when they are relevant to the question.',
    '='.repeat(42),
    '',
  ].join('\n');
}

function body(): string {
  return JSON.stringify({
    model: 'gpt-4o-mini',
    messages: [
      { role: 'system', content: systemPrompt() },
      { role: 'user', content: 'draft the follow-up' },
    ],
  });
}

function pending(overrides: Partial<PendingEgress> = {}): PendingEgress {
  const requestBody = overrides.body ?? body();
  return {
    id: 'abc123',
    host: 'api.openai.com',
    method: 'POST',
    url: 'https://api.openai.com/v1/chat/completions',
    body: requestBody,
    literalText: `https://api.openai.com/v1/chat/completions\n\n${requestBody}`,
    byteCount: requestBody.length,
    source: 'chat',
    createdAt: 1_754_900_000,
    ...overrides,
  };
}

/** A dialog wired to one waiting question, with the decision captured. */
function mount(item: PendingEgress | null = pending()) {
  const decide = vi.fn().mockResolvedValue(true);
  const source = vi.fn().mockResolvedValue(item ? [item] : []);
  render(<ConfirmSendDialog source={source} decide={decide} pollMs={10_000} />);
  return { decide, source };
}

/** What the second argument of the decision says will be sent. */
function sentBody(decide: ReturnType<typeof vi.fn>): string | undefined {
  return decide.mock.calls[0]?.[2];
}

describe('when something is waiting', () => {
  it('names the destination and says nothing has left yet', async () => {
    mount();
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /send this to api\.openai\.com/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/nothing has left your machine yet/i)).toBeInTheDocument();
  });

  it('shows each remembered fact as its own control', async () => {
    mount();
    expect(await screen.findByRole('button', { name: new RegExp(DAY_RATE) })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: new RegExp(PAYS_LATE) })).toBeInTheDocument();
  });

  it('renders nothing at all when nothing is waiting', async () => {
    mount(null);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});

describe('what actually gets sent', () => {
  it('sends no body when the user changed nothing', async () => {
    const { decide } = mount();
    await screen.findByRole('dialog');

    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    // Undefined rather than the same string back: an untouched request keeps
    // its original bytes instead of being re-serialised into an equivalent.
    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', true, undefined));
  });

  it('drops a struck fact from the body it posts', async () => {
    const { decide } = mount();
    await screen.findByRole('dialog');

    await userEvent.click(screen.getByRole('button', { name: new RegExp(DAY_RATE) }));
    await userEvent.click(screen.getByRole('button', { name: /send without 1 fact/i }));

    await waitFor(() => expect(decide).toHaveBeenCalled());
    const sent = sentBody(decide);
    expect(sent, 'the dialog sent no edited body').toBeDefined();
    expect(sent).not.toContain(DAY_RATE);
    expect(sent, 'a fact the user kept was dropped too').toContain(PAYS_LATE);
    expect(sent, 'the question itself was lost').toContain('draft the follow-up');
  });

  it('puts a fact back when it is struck twice', async () => {
    const { decide } = mount();
    await screen.findByRole('dialog');

    const chip = screen.getByRole('button', { name: new RegExp(DAY_RATE) });
    await userEvent.click(chip);
    await userEvent.click(screen.getByRole('button', { name: new RegExp(DAY_RATE) }));
    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', true, undefined));
  });

  it('refusing sends no body, whatever was struck', async () => {
    const { decide } = mount();
    await screen.findByRole('dialog');

    await userEvent.click(screen.getByRole('button', { name: new RegExp(DAY_RATE) }));
    await userEvent.click(screen.getByRole('button', { name: /don’t send/i }));

    // There is no such thing as editing something you are not sending, and the
    // backend would ignore it — but sending one at all invites the reading
    // that a refusal could carry an approved body.
    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', false, undefined));
  });

  it('escape refuses rather than dismissing', async () => {
    const { decide } = mount();
    await screen.findByRole('dialog');

    await userEvent.keyboard('{Escape}');

    // Closing without answering would leave a thread parked until it timed
    // out, while the user believed they had cancelled — which they had.
    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', false, undefined));
  });
});

describe('the literal text', () => {
  it('can be revealed, and shows the exact bytes', async () => {
    mount();
    await screen.findByRole('dialog');

    await userEvent.click(screen.getByRole('button', { name: /show exactly what is sent/i }));

    const shown = await screen.findByTestId('literal-text');
    expect(shown).toHaveTextContent('api.openai.com/v1/chat/completions');
    expect(shown.textContent).toContain(DAY_RATE);
  });

  it('stops showing a fact the user struck', async () => {
    mount();
    await screen.findByRole('dialog');

    await userEvent.click(screen.getByRole('button', { name: /show exactly what is sent/i }));
    await userEvent.click(screen.getByRole('button', { name: new RegExp(DAY_RATE) }));

    // The preview is the check on the chips. If it kept showing a struck fact
    // the user would have no way to tell which of the two views was lying.
    await waitFor(() =>
      expect(screen.getByTestId('literal-text').textContent).not.toContain(DAY_RATE),
    );
    expect(screen.getByTestId('literal-text').textContent).toContain(PAYS_LATE);
  });
});

describe('a request the dialog cannot read', () => {
  it('still offers the decision, with no chips', async () => {
    const { decide } = mount(pending({ body: 'not json at all' }));
    await screen.findByRole('dialog');

    // No invented chips. A user who believed they removed something from a
    // body this could not parse would be worse off than one who was never
    // offered the removal.
    expect(screen.queryByText(/things zaram remembered/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', true, undefined));
  });
});
