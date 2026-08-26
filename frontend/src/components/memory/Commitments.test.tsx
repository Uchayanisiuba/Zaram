/**
 * The commitments surface — the five things about it that are rules.
 *
 * These are not render tests. Each one grades a sentence from `CLAUDE.md` that
 * a plausible-looking screen would break without anything going red:
 *
 * - **Every obligation shows its source clause.** A clause behind a disclosure
 *   is a clause nobody opens, and a date the user reorganises their week
 *   around with the evidence one click away is a date they will trust without
 *   checking. So it must be in the collapsed row.
 * - **A document read incompletely must not look cleanly read.** The questions
 *   come before the commitments, in the document order of the page.
 * - **Never silently create a commitment.** Answering a question sends the
 *   anchor the user typed and nothing else, and the clause is not among the
 *   fields any correction can carry.
 * - **A correction is a decision, not a click.** Saving is refused while
 *   nothing has changed, because an empty correction would still supersede the
 *   original and record the user as having confirmed it.
 * - **Dismissing asks first.** "This was never a commitment" is stored, so a
 *   stray click on the wrong row is not undone by clicking again.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Commitments from './Commitments';
import type { Obligation, ObligationQuestion } from '@/services/obligationsClient';

afterEach(cleanup);

const CLAUSE = 'A deposit of GBP 1,200 is due by 1 September 2026 before work begins.';
const QUESTION_CLAUSE = 'Payment terms: 30 days from the invoice date.';

function obligation(over: Partial<Obligation> = {}): Obligation {
  return {
    id: 'obl_1',
    kind: 'payment',
    summary: 'Payment of GBP 1,200.00 due',
    due: '2026-09-01',
    source_clause: { text: CLAUSE, start: 468, end: 537 },
    source_document_id: 'C:\\Users\\a\\uploads\\northwind-sow.txt',
    direction: 'unknown',
    status: 'open',
    amount: '1200',
    currency: 'GBP',
    scope: 'global',
    confidence: 0.9,
    created_at: 1_787_709_509,
    superseded_by: null,
    superseded_at: null,
    ...over,
  };
}

const question: ObligationQuestion = {
  id: 'unr_1',
  kind: 'payment',
  clause: { text: QUESTION_CLAUSE, start: 421, end: 466 },
  reason: 'no_anchor_date',
  question:
    "This says it falls due 30 days after the document date, but I don't know what " +
    'that date is. When was it issued?',
  document_id: 'C:\\Users\\a\\uploads\\northwind-sow.txt',
  scope: 'global',
  created_at: 1_787_709_509,
};

/** Every request made, and a canned listing for the GETs. */
let calls: { url: string; init: RequestInit | undefined }[];

function serve(listing: { obligations: Obligation[]; questions: ObligationQuestion[] }) {
  calls = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const body = init?.method === 'POST' ? obligation({ id: 'obl_new' }) : listing;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
}

beforeEach(() => {
  serve({ obligations: [obligation()], questions: [question] });
});

afterEach(() => vi.unstubAllGlobals());

const posts = () => calls.filter((c) => c.init?.method === 'POST');

describe('the source clause', () => {
  it('is on the row before anything is expanded', async () => {
    render(<Commitments />);

    // Not `findByText` on the summary — the clause itself, with nothing clicked.
    expect(await screen.findByText(`“${CLAUSE}”`)).toBeTruthy();
  });

  it('names the document it was read from, by file rather than by path', async () => {
    render(<Commitments />);

    // A regex, because the line carries a file icon beside the name and the
    // default matcher grades the element's whole text content.
    expect(await screen.findAllByText(/northwind-sow\.txt/)).not.toHaveLength(0);
    expect(screen.queryByText(/C:\\Users/)).toBeNull();
  });

  it('is not offered as an editable field by the correction form', async () => {
    const user = userEvent.setup();
    render(<Commitments />);

    await user.click(await screen.findByText('Payment of GBP 1,200.00 due'));
    await user.click(await screen.findByRole('button', { name: 'Correct' }));

    // The clause is still shown, and no input holds it.
    expect(screen.getByText(`“${CLAUSE}”`)).toBeTruthy();
    const values = screen
      .getAllByRole('textbox')
      .map((el) => (el as HTMLInputElement).value);
    expect(values).not.toContain(CLAUSE);
  });
});

describe('a document read incompletely', () => {
  it('puts what could not be dated above what could', async () => {
    render(<Commitments />);

    await screen.findByText(`“${QUESTION_CLAUSE}”`);

    const order = Array.from(document.querySelectorAll('li')).map((li) => li.textContent ?? '');
    const askedAt = order.findIndex((t) => t.includes(QUESTION_CLAUSE));
    const datedAt = order.findIndex((t) => t.includes(CLAUSE));

    expect(askedAt).toBeGreaterThanOrEqual(0);
    expect(datedAt).toBeGreaterThanOrEqual(0);
    expect(askedAt).toBeLessThan(datedAt);
  });

  it('shows the question the backend wrote, not a paraphrase of it', async () => {
    render(<Commitments />);

    expect(await screen.findByText(question.question)).toBeTruthy();
  });
});

describe('answering a question', () => {
  it('will not send until a date has been given', async () => {
    render(<Commitments />);

    const button = await screen.findByRole('button', { name: 'Work out the date' });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('sends the anchor to the question, and only the anchor', async () => {
    const user = userEvent.setup();
    render(<Commitments />);

    const input = await screen.findByLabelText('The date this document was issued');
    await user.type(input, '2026-08-15');
    await user.click(screen.getByRole('button', { name: 'Work out the date' }));

    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toBe('/obligations/questions/unr_1/answer');
    expect(JSON.parse(String(posts()[0].init?.body))).toEqual({ anchor: '2026-08-15' });
  });
});

describe('correcting one', () => {
  it('refuses to save while nothing has changed', async () => {
    const user = userEvent.setup();
    render(<Commitments />);

    await user.click(await screen.findByText('Payment of GBP 1,200.00 due'));
    await user.click(screen.getByRole('button', { name: 'Correct' }));

    const save = screen.getByRole('button', { name: /Save correction/ });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    expect(posts()).toHaveLength(0);
  });

  it('offers who-owes-it as one click, because the document cannot say', async () => {
    const user = userEvent.setup();
    render(<Commitments />);

    await user.click(await screen.findByText('Payment of GBP 1,200.00 due'));
    await user.click(screen.getByRole('button', { name: 'Owed to you' }));

    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toBe('/obligations/obl_1/correct');
    expect(JSON.parse(String(posts()[0].init?.body))).toEqual({ direction: 'owed_to_user' });
  });

  it('does not offer the guess once the user has settled it', async () => {
    serve({ obligations: [obligation({ direction: 'owed_to_user' })], questions: [] });
    const user = userEvent.setup();
    render(<Commitments />);

    await user.click(await screen.findByText('Payment of GBP 1,200.00 due'));

    expect(screen.queryByRole('button', { name: 'You owe this' })).toBeNull();
    expect(screen.getByText('Owed to you')).toBeTruthy();
  });
});

describe('dismissing one', () => {
  it('asks before it stores the dismissal', async () => {
    const user = userEvent.setup();
    render(<Commitments />);

    await user.click(await screen.findByText('Payment of GBP 1,200.00 due'));
    await user.click(screen.getByRole('button', { name: 'Not a commitment' }));

    // The first click is the question, not the act.
    expect(posts()).toHaveLength(0);
    expect(screen.getByText(/Say this was never a commitment\?/)).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Not a commitment' }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toBe('/obligations/obl_1/dismiss');
  });
});

describe('what it reports upward', () => {
  it('counts a live commitment and an open question separately', async () => {
    const seen: { open: number; overdue: number; questions: number }[] = [];
    render(<Commitments onCounts={(c) => seen.push(c)} />);

    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen[seen.length - 1]).toEqual({ open: 1, overdue: 0, questions: 1 });
  });

  it('reports zero rather than a stale figure when the load fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('nope', { status: 500 })),
    );
    const seen: { open: number; overdue: number; questions: number }[] = [];
    render(<Commitments onCounts={(c) => seen.push(c)} />);

    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen[seen.length - 1]).toEqual({ open: 0, overdue: 0, questions: 0 });
  });
});

describe('the empty state', () => {
  it('says where commitments come from rather than that there are none', async () => {
    serve({ obligations: [], questions: [] });
    render(<Commitments />);

    expect(await screen.findByText(/Zaram has not found any commitments/)).toBeTruthy();
    expect(screen.getByText(/Knowledge/)).toBeTruthy();
  });
});

describe('a settled row', () => {
  it('is shown, not hidden, so a dismissal can be audited', async () => {
    const user = userEvent.setup();
    serve({
      obligations: [obligation({ status: 'dismissed' })],
      questions: [],
    });
    render(<Commitments />);

    await user.click(await screen.findByRole('button', { name: 'Settled and corrected' }));

    const row = await screen.findByText('Payment of GBP 1,200.00 due');
    expect(within(row.closest('li') as HTMLElement).getByText(/not a commitment/)).toBeTruthy();
  });
});
