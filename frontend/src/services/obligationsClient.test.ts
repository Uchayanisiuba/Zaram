/**
 * @vitest-environment node
 *
 * Obligations transport — the four things only this end can get wrong.
 *
 * Node rather than jsdom: this is fetch and arithmetic, not the DOM.
 *
 * None of these assert that a function was called. They assert the things
 * whose failure would be silent and would look like something else:
 *
 * - **A correction that sends more than the user changed.** The backend treats
 *   an absent field as "leave it alone", so posting the whole record back
 *   turns a date correction into a correction of the amount as well — and the
 *   supersession chain would record the user as having confirmed a figure they
 *   never looked at.
 * - **A day count that is off by one for half the day.** `daysUntil` subtracts
 *   calendar dates, not instants. Taken naively, "due today" becomes "1 day
 *   late" at some point every evening, on the row that most needs to be right.
 * - **`questions` dropped from the listing.** Silently losing them makes a
 *   partially-read document look cleanly read.
 * - **A count that disagrees with the list it labels.** `countObligations` is
 *   the one implementation both callers use, so what it counts is worth
 *   pinning down — particularly that a date it cannot read is not reported as
 *   late.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';

import {
  answerObligationQuestion,
  correctObligation,
  countObligations,
  daysUntil,
  documentName,
  dueLabel,
  fetchObligations,
  type Obligation,
  type ObligationListing,
} from './obligationsClient';

afterEach(() => vi.unstubAllGlobals());

/** Every request `fetch` was called with.
 *
 *  A `Response` body can be read once, so the reply is built per call rather
 *  than shared — otherwise the second request in a test fails with "body has
 *  already been read", which looks like a client defect and is not. */
function capture(reply: () => Response) {
  const calls: { url: string; init: RequestInit | undefined }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return reply();
    }),
  );
  return calls;
}

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

function obligation(over: Partial<Obligation> = {}): Obligation {
  return {
    id: 'obl_1',
    kind: 'payment',
    summary: 'Payment of GBP 1,200.00 due',
    due: '2026-09-01',
    source_clause: { text: 'A deposit of GBP 1,200 is due by 1 September 2026.', start: 0, end: 49 },
    source_document_id: 'C:\\docs\\northwind-sow.txt',
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

describe('correctObligation', () => {
  it('sends only the fields the user changed', async () => {
    const calls = capture(() => ok(obligation({ id: 'obl_2', due: '2026-10-09' })));

    await correctObligation('obl_1', { due: '2026-10-09' });

    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ due: '2026-10-09' });
  });

  it('never sends the source clause, whatever it is handed', async () => {
    const calls = capture(() => ok(obligation()));

    // The type forbids it; a plain object at a call site does not.
    await correctObligation('obl_1', {
      due: '2026-10-09',
      ...({ source_clause: { text: 'rewritten', start: 0, end: 9 } } as object),
    });

    const body = JSON.parse(String(calls[0].init?.body)) as Record<string, unknown>;
    expect(body).not.toHaveProperty('source_clause');
  });
});

describe('fetchObligations', () => {
  it('carries the questions as well as the commitments', async () => {
    const listing: ObligationListing = {
      obligations: [obligation()],
      questions: [
        {
          id: 'unr_1',
          kind: 'payment',
          clause: { text: 'Payment terms: 30 days from the invoice date.', start: 0, end: 44 },
          reason: 'no_anchor_date',
          question: 'When was it issued?',
          document_id: 'C:\\docs\\northwind-sow.txt',
          scope: 'global',
          created_at: 1_787_709_509,
        },
      ],
    };
    capture(() => ok(listing));

    const result = await fetchObligations();

    expect(result.questions).toHaveLength(1);
    expect(result.questions[0].question).toBe('When was it issued?');
  });

  it('asks for the closed ones only when told to', async () => {
    const calls = capture(() => ok({ obligations: [], questions: [] }));

    await fetchObligations();
    await fetchObligations({ includeClosed: true });

    expect(calls[0].url).toBe('/obligations');
    expect(calls[1].url).toBe('/obligations?include_closed=true');
  });
});

describe('answerObligationQuestion', () => {
  it('raises the backend sentence rather than the status when the anchor did not settle it', async () => {
    const detail =
      'That date did not resolve the clause, so it has been left as a question ' +
      'rather than closed on a guess.';
    capture(
      () =>
        new Response(JSON.stringify({ detail }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
    );

    await expect(answerObligationQuestion('unr_1', '2026-08-15')).rejects.toThrow(detail);
  });
});

describe('daysUntil', () => {
  // The evening case. Both sides reduce to a calendar date first, so the
  // answer does not change as the clock moves through the day.
  it('is zero all day on the due date', () => {
    expect(daysUntil('2026-09-01', new Date(2026, 8, 1, 0, 1))).toBe(0);
    expect(daysUntil('2026-09-01', new Date(2026, 8, 1, 23, 59))).toBe(0);
  });

  it('is negative once the day has passed', () => {
    expect(daysUntil('2026-09-01', new Date(2026, 8, 2, 0, 1))).toBe(-1);
  });

  it('crosses a daylight-saving boundary without drifting', () => {
    // Whatever the local zone, these are 30 calendar days apart.
    expect(daysUntil('2026-04-01', new Date(2026, 2, 2))).toBe(30);
    expect(daysUntil('2026-11-01', new Date(2026, 9, 2))).toBe(30);
  });

  it('answers null rather than a number for something that is not a date', () => {
    expect(daysUntil('not a date')).toBeNull();
    expect(daysUntil('2026-9-1')).toBeNull();
  });
});

describe('dueLabel', () => {
  it('says late in days, so the row does not have to be read as a date', () => {
    expect(dueLabel('2026-08-12', new Date(2026, 7, 26))).toBe('14 days late');
    expect(dueLabel('2026-08-25', new Date(2026, 7, 26))).toBe('1 day late');
    expect(dueLabel('2026-08-26', new Date(2026, 7, 26))).toBe('today');
    expect(dueLabel('2026-08-27', new Date(2026, 7, 26))).toBe('tomorrow');
  });

  it('stops paraphrasing once the absolute date is the more useful one', () => {
    expect(dueLabel('2026-10-02', new Date(2026, 7, 26))).toBeNull();
  });
});

describe('countObligations', () => {
  const now = new Date(2026, 7, 26);

  it('counts only what is live, so a correction does not double', () => {
    const counts = countObligations(
      {
        obligations: [
          obligation({ id: 'a', superseded_by: 'b' }),
          obligation({ id: 'b' }),
          obligation({ id: 'c', status: 'met' }),
          obligation({ id: 'd', status: 'dismissed' }),
        ],
        questions: [],
      },
      now,
    );
    expect(counts.open).toBe(1);
  });

  it('reports a date it cannot read as not late', () => {
    const counts = countObligations(
      { obligations: [obligation({ due: 'sometime' })], questions: [] },
      now,
    );
    expect(counts.overdue).toBe(0);
  });

  it('counts a date already passed as late', () => {
    const counts = countObligations(
      { obligations: [obligation({ due: '2026-08-12' })], questions: [] },
      now,
    );
    expect(counts.overdue).toBe(1);
  });
});

describe('documentName', () => {
  it('shows the file, not the path it happens to live at', () => {
    expect(documentName('C:\\Users\\a\\uploads\\northwind-sow.txt')).toBe('northwind-sow.txt');
    expect(documentName('/home/a/uploads/northwind-sow.txt')).toBe('northwind-sow.txt');
  });

  it('leaves an id that is not a path alone', () => {
    expect(documentName('src-b9115d70092e')).toBe('src-b9115d70092e');
  });
});
