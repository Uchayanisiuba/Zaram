/**
 * Obligations transport — the commitments Zaram read out of the user's own
 * documents, and the questions it could not answer about them.
 *
 * Field names are the backend's, for the reason `artifactsClient.ts` gives: a
 * mapping layer is a second vocabulary and a place for the two to disagree
 * quietly. That matters more here than anywhere else in the product, because
 * the thing being carried is a date somebody will plan their week around.
 *
 * **`questions` is not a secondary payload.** `GET /obligations` returns both
 * lists in one response, and a client that reads only the first half would
 * make Zaram look as though it had read a document cleanly when in fact it had
 * found a commitment it could not date. Dropping those silently is the exact
 * failure `obligations/contracts.py` was written to prevent, arriving one
 * layer up — so `fetchObligations` returns both and the type makes the second
 * one impossible to forget.
 *
 * **No correction here rewrites the clause.** The backend's
 * `ObligationCorrection` deliberately has no `source_clause` field, and this
 * mirrors it: a correction says Zaram read the sentence wrongly, not that the
 * sentence was different. The clause is the evidence, and evidence a user can
 * edit is not evidence.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What sort of commitment it is. Each value changes what could be done about
 *  it — a payment can be chased, an expiry cannot. */
export type ObligationKind = 'payment' | 'deliverable' | 'expiry' | 'renewal';

/** Who owes whom. `unknown` is the common case and is not a failure: the
 *  sentence reads identically on an invoice sent and one received, so the
 *  extractor refuses to guess rather than tell a freelancer they owe money
 *  they are in fact owed. It is the field the user most often sets. */
export type ObligationDirection = 'owed_by_user' | 'owed_to_user' | 'unknown';

export type ObligationStatus = 'open' | 'met' | 'dismissed';

/** Why a clause that clearly states a commitment did not become one. */
export type UnresolvedReason =
  | 'no_anchor_date'
  | 'ambiguous_date'
  | 'impossible_date';

export interface Clause {
  text: string;
  /** Character offsets into the extracted text. `-1` when unknown. Kept
   *  alongside `text` because a re-parse can move them, and a citation that
   *  silently points at the wrong sentence is worse than one that cannot be
   *  located. `text` is what is shown. */
  start: number;
  end: number;
}

export interface Obligation {
  id: string;
  kind: ObligationKind;
  /** One line, as a person would say it. Not the clause. */
  summary: string;
  /** ISO date. Always absolute — a relative term is resolved against an anchor
   *  before an obligation exists, or it stays a question instead. */
  due: string;
  source_clause: Clause;
  /** How the ingest layer identifies the document. Today that is a filesystem
   *  path, which is why the interface shows its last segment rather than
   *  inventing a title for it. */
  source_document_id: string;
  direction: ObligationDirection;
  status: ObligationStatus;
  /** A decimal string, never a number. JSON has one numeric type and it is a
   *  double, so `0.1` arrives as 0.1000000000000000055 — the same reasoning
   *  the invoice line items already follow. `null` means the clause named no
   *  amount, which is not zero. */
  amount: string | null;
  currency: string;
  /** Rule 7i: `global`, or `project:<id>`. */
  scope: string;
  /** 0..1, and it orders what the user reviews first and nothing else. It is
   *  never a gate — a confidence number must not be what decides that a
   *  commitment is real enough to act on. */
  confidence: number;
  created_at: number;
  /** Id of the obligation that replaced this one, or `null` while it stands.
   *  A correction supersedes rather than deletes, so "what did Zaram think
   *  last week" stays answerable. */
  superseded_by: string | null;
  superseded_at: number | null;
}

export interface ObligationQuestion {
  id: string;
  kind: ObligationKind;
  clause: Clause;
  reason: UnresolvedReason;
  /** Already written for a person by the backend. Shown as it arrives —
   *  rewording it here would be a second place for the wording to drift. */
  question: string;
  document_id: string;
  scope: string;
  created_at: number;
}

export interface ObligationListing {
  obligations: Obligation[];
  questions: ObligationQuestion[];
}

export const KIND_LABELS: Record<ObligationKind, string> = {
  payment: 'Payment',
  deliverable: 'Deliverable',
  expiry: 'Expires',
  renewal: 'Renews',
};

/** What the user is changing. Absent fields are left alone. Mirrors the
 *  backend's `ObligationCorrection` exactly, including what it omits. */
export interface ObligationCorrection {
  /** ISO date. */
  due?: string;
  summary?: string;
  /** A decimal string, for the reason `Obligation.amount` gives. */
  amount?: string;
  currency?: string;
  direction?: ObligationDirection;
}

/** Shared failure handling. A refusal carries the backend's own sentence:
 *  "That date did not resolve the clause" is something a person can act on and
 *  `409` is not. */
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!response.ok) {
    let detail = '';
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? '';
    } catch {
      /* not every failure has a body */
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

const asJson = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/**
 * Live commitments, soonest first, each with the clause it was read from —
 * and the clauses that could not be dated, as questions.
 *
 * `includeClosed` brings back dismissed and met ones too. That is not an
 * administrative nicety: a product that says "you can dismiss this" has to be
 * able to show what was dismissed, or the promise has no audit.
 */
export async function fetchObligations(
  opts: { scope?: string; includeClosed?: boolean } = {},
): Promise<ObligationListing> {
  const params = new URLSearchParams();
  if (opts.scope) params.set('scope', opts.scope);
  if (opts.includeClosed) params.set('include_closed', 'true');
  const query = params.toString();
  return json<ObligationListing>(`/obligations${query ? `?${query}` : ''}`);
}

/**
 * Replace an obligation with a corrected one. Rule 4 — the original is
 * superseded rather than deleted and stays readable.
 *
 * The body is assembled field by field rather than spread, so what goes on the
 * wire is bounded by this list and not by whatever the caller happened to hold.
 * `ObligationCorrection` already forbids a `source_clause` at compile time;
 * this is the same guarantee at runtime, where a plain object at a call site
 * lives. The clause is the evidence an obligation rests on, and evidence the
 * interface can rewrite is not evidence.
 *
 * A field is omitted when undefined, because the backend reads an absent field
 * as "leave it alone" — sending the whole record back would record the user as
 * having confirmed figures they never looked at.
 */
export async function correctObligation(
  id: string,
  changes: ObligationCorrection,
): Promise<Obligation> {
  const body: ObligationCorrection = {};
  if (changes.due !== undefined) body.due = changes.due;
  if (changes.summary !== undefined) body.summary = changes.summary;
  if (changes.amount !== undefined) body.amount = changes.amount;
  if (changes.currency !== undefined) body.currency = changes.currency;
  if (changes.direction !== undefined) body.direction = changes.direction;

  return json<Obligation>(
    `/obligations/${encodeURIComponent(id)}/correct`,
    asJson(body),
  );
}

/** Say this was never an obligation. Stored, not deleted — otherwise the next
 *  ingest of the same document extracts the clause and asks again, which
 *  teaches the user that correcting Zaram does not stick. */
export async function dismissObligation(id: string): Promise<Obligation> {
  return json<Obligation>(`/obligations/${encodeURIComponent(id)}/dismiss`, {
    method: 'POST',
  });
}

/** It was real, and it happened. Distinct from dismissing. */
export async function markObligationMet(id: string): Promise<Obligation> {
  return json<Obligation>(`/obligations/${encodeURIComponent(id)}/met`, {
    method: 'POST',
  });
}

/**
 * Supply the date a relative term counts from, and turn a clause into a dated
 * commitment.
 *
 * A 409 means the anchor was accepted and still did not settle the clause, so
 * the question stays open rather than being closed on a guess. That arrives
 * here as the backend's sentence, which says exactly that.
 */
export async function answerObligationQuestion(
  questionId: string,
  anchor: string,
): Promise<Obligation> {
  return json<Obligation>(
    `/obligations/questions/${encodeURIComponent(questionId)}/answer`,
    asJson({ anchor }),
  );
}

export interface ObligationCounts {
  /** Live: open, and not replaced by a correction. */
  open: number;
  /** Past the date in the clause. A subset of `open`. */
  overdue: number;
  /** Clauses read but not datable on their own. */
  questions: number;
}

/**
 * Count a listing. One implementation, because two callers need the same
 * number and the tab badge disagreeing with the list under it is the kind of
 * defect nobody reports and everybody stops trusting.
 *
 * `overdue` counts a missing or unparseable date as *not* late. A date Zaram
 * cannot read is not evidence that something has lapsed, and reporting it as
 * late would put a red number on the one surface whose value is that its
 * claims can be checked.
 */
export function countObligations(
  listing: ObligationListing,
  now: Date = new Date(),
): ObligationCounts {
  const live = listing.obligations.filter(
    (o) => o.status === 'open' && !o.superseded_by,
  );
  return {
    open: live.length,
    overdue: live.filter((o) => (daysUntil(o.due, now) ?? 0) < 0).length,
    questions: listing.questions.length,
  };
}

/** The last segment of a document path, which is what a person recognises.
 *  Not prettified into a title — a slug turned into a title is a value nobody
 *  entered, and this surface does not invent any. */
export function documentName(id: string): string {
  if (!id) return '';
  const parts = id.split(/[\\/]/);
  return parts[parts.length - 1] || id;
}

/** Whole days from today to an ISO date. Negative is overdue.
 *
 *  Both sides are reduced to a local calendar date before subtracting, so
 *  "due today" does not become "due yesterday" because it is now the evening.
 *  A date is a day, not an instant. */
export function daysUntil(iso: string, now: Date = new Date()): number | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!parts) return null;
  const due = Date.UTC(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]));
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((due - today) / 86_400_000);
}

/** How close it is, in the words a person would use. `null` for an
 *  unparseable date, so the caller shows the raw value rather than a
 *  confident wrong phrase. */
export function dueLabel(iso: string, now: Date = new Date()): string | null {
  const days = daysUntil(iso, now);
  if (days === null) return null;
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days === -1) return '1 day late';
  if (days < 0) return `${-days} days late`;
  if (days < 30) return `in ${days} days`;
  return null;
}
