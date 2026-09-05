/**
 * Commitments — what Zaram read out of the user's documents, and how to fix it.
 *
 * **Why this is a section of Memory and not a node of its own.** `CLAUDE.md`
 * fixes the navigation at six and says a pack "adds no screens"; obligations
 * are the first pack. The division between the two stores it *does* have is
 * that Memory holds derived facts about the user and Knowledge holds the
 * documents those came from — and an obligation is a derived, correctable
 * claim carrying provenance back to a source. That is Memory's contract
 * exactly, down to the mechanism: a correction here supersedes and keeps the
 * original, the same shape `MemoryRecord.superseded_by` uses for facts.
 *
 * **It is not a calendar, and the shape is where that is enforced.** No grid,
 * no month, no week, nothing to plan against. A list in the order things fall
 * due, with the sentence each one was read from. `docs/VISION.md`: *"It is not
 * where anyone plans their week."*
 *
 * **The clause is never behind a disclosure.** Rule: every obligation shows
 * its source clause. A date the user reorganises their week around, with the
 * evidence one click away, is a date they will trust without checking — which
 * is the failure the rule exists to prevent. So the clause is on the row, in
 * the collapsed state, always.
 *
 * **The questions come first, and they are the honest half.** A clause Zaram
 * could see and could not date is neither dropped nor guessed at; it is asked
 * about. Putting the answered commitments first and the questions below would
 * make a partially-read document look cleanly read.
 *
 * **Direction is offered as one click because it is the field the extractor
 * refuses to guess.** "Payment is due within 30 days" reads identically on an
 * invoice sent and one received, so `unknown` is the common case and is not a
 * defect. Telling a freelancer they owe money they are in fact owed is the
 * expensive kind of wrong, and this is where the user settles it.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowUpRight,
  CalendarClock,
  Check,
  CornerDownRight,
  FileText,
  HelpCircle,
  Pencil,
  RefreshCw,
  X,
} from 'lucide-react';

import {
  KIND_LABELS,
  answerObligationQuestion,
  correctObligation,
  countObligations,
  dismissObligation,
  documentName,
  dueLabel,
  daysUntil,
  fetchObligations,
  markObligationMet,
  type Obligation,
  type ObligationCorrection,
  type ObligationCounts,
  type ObligationDirection,
  type ObligationKind,
  type ObligationQuestion,
} from '@/services/obligationsClient';

/** One accent per kind, drawn from the existing token set. No new hues, and
 *  none of them is a state colour — the orb owns those. */
const KIND_COLOUR: Record<ObligationKind, string> = {
  payment: 'var(--color-emerald)',
  deliverable: 'var(--color-cyan-light)',
  expiry: 'var(--color-amber)',
  renewal: 'var(--color-violet)',
};

const DIRECTION_LABELS: Record<ObligationDirection, string> = {
  owed_by_user: 'You owe this',
  owed_to_user: 'Owed to you',
  unknown: 'Who owes this is not in the document',
};

const longDate = (iso: string) => {
  const parsed = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!parsed) return iso;
  return new Date(
    Number(parsed[1]),
    Number(parsed[2]) - 1,
    Number(parsed[3]),
  ).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' });
};

const shortStamp = (seconds: number) =>
  new Date(seconds * 1000).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  });

/** The money, exactly as stored. The amount is a decimal string all the way
 *  from SQLite and is not turned into a number here — a rounding error in a
 *  figure somebody invoices is not a display bug. */
const money = (amount: string | null, currency: string) => {
  if (amount === null) return null;
  return currency ? `${currency} ${amount}` : amount;
};

/**
 * Whether the amount still needs saying, given what the summary already says.
 *
 * The backend writes the money into the summary whenever it has both an amount
 * and a currency, so repeating the field beside it prints one figure twice in
 * two formats — measured on a real contract as *"Payment of GBP 1,200.00 due
 * · GBP 1200"*. Correcting the amount leaves the old summary standing, though,
 * and the corrected figure has to appear somewhere, so this is a comparison
 * rather than an unconditional suppression.
 *
 * Digits only, because "1200" and "1,200.00" are the same figure. A short
 * amount can coincidentally appear inside a longer one and be hidden by that;
 * that is the direction to fail in, since the clause is on the row either way
 * and the alternative failure is printing a number that is not the amount.
 */
const amountIsNews = (amount: string | null, summary: string) => {
  if (amount === null) return false;
  const digits = (text: string) => text.replace(/\D/g, '');
  const figure = digits(amount);
  return figure.length > 0 && !digits(summary).includes(figure);
};

/** The clause, shown as a quotation rather than as body text.
 *
 *  It is deliberately not truncated. A clause cut at 80 characters is a
 *  citation the user cannot check, which is the same as no citation. */
function SourceClause({ text, document }: { text: string; document: string }) {
  return (
    <div
      className="mt-2 rounded-md px-3 py-2"
      style={{ background: 'var(--color-glass)', borderLeft: '2px solid var(--color-border)' }}
    >
      <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
        “{text}”
      </p>
      {document && (
        <p
          className="mt-1 flex items-center gap-1 text-[10px] text-slate-500"
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          <FileText size={9} />
          {documentName(document)}
        </p>
      )}
    </div>
  );
}

function KindBadge({ kind }: { kind: ObligationKind }) {
  return (
    <span
      className="shrink-0 rounded px-1.5 py-0.5 text-[9px] uppercase tracking-wider"
      style={{
        fontFamily: 'var(--font-mono)',
        border: '1px solid var(--color-border-subtle)',
        color: KIND_COLOUR[kind],
      }}
    >
      {KIND_LABELS[kind]}
    </span>
  );
}

interface QuestionCardProps {
  question: ObligationQuestion;
  busy: boolean;
  onAnswer: (anchor: string) => void;
}

/**
 * A clause Zaram can see and cannot date.
 *
 * The question text is the backend's, shown as it arrives. Rewording it here
 * would be a second place for the wording to drift, and the backend is the
 * side that knows *why* it could not be dated.
 */
function QuestionCard({ question, busy, onAnswer }: QuestionCardProps) {
  const [anchor, setAnchor] = useState('');

  return (
    <li
      className="rounded-lg px-4 py-3"
      style={{
        border: '1px solid rgba(251,191,36,0.25)',
        background: 'rgba(251,191,36,0.05)',
      }}
    >
      <div className="flex items-start gap-2">
        <HelpCircle
          size={13}
          className="mt-0.5 shrink-0"
          style={{ color: 'var(--color-amber, #fbbf24)' }}
        />
        <p className="text-sm leading-snug flex-1" style={{ color: 'var(--color-text)' }}>
          {question.question}
        </p>
        <KindBadge kind={question.kind} />
      </div>

      <SourceClause text={question.clause.text} document={question.document_id} />

      <div className="mt-2.5 flex items-center gap-2 flex-wrap">
        <input
          type="date"
          value={anchor}
          onChange={(e) => setAnchor(e.target.value)}
          aria-label="The date this document was issued"
          className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
          style={{
            background: 'var(--color-glass)',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text)',
            colorScheme: 'dark',
          }}
        />
        <button
          disabled={busy || !anchor}
          onClick={() => onAnswer(anchor)}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40"
          style={{
            border: '1px solid var(--color-border)',
            background: 'rgba(255,255,255,0.08)',
            color: 'var(--color-text)',
          }}
        >
          <Check size={12} />
          Work out the date
        </button>
        {/* Says what pressing it does, so the user is not agreeing to a
            deadline sight unseen. The commitment appears in the list below,
            with this same clause attached. */}
        <span className="text-[10px] text-slate-500">
          Zaram counts from this date and shows you what it gets.
        </span>
      </div>
    </li>
  );
}

interface CorrectFormProps {
  obligation: Obligation;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (changes: ObligationCorrection) => void;
}

/**
 * Correcting one. Only the fields that changed are sent, because the backend
 * treats an absent field as "leave it alone" and sending everything back would
 * make a correction of the date look like a correction of the amount too.
 *
 * The clause is not among the fields and is shown above the form unchanged.
 */
function CorrectForm({ obligation, busy, onCancel, onSubmit }: CorrectFormProps) {
  const [due, setDue] = useState(obligation.due);
  const [summary, setSummary] = useState(obligation.summary);
  const [amount, setAmount] = useState(obligation.amount ?? '');
  const [currency, setCurrency] = useState(obligation.currency);
  const [direction, setDirection] = useState<ObligationDirection>(obligation.direction);

  const changes: ObligationCorrection = {};
  if (due !== obligation.due) changes.due = due;
  if (summary !== obligation.summary) changes.summary = summary;
  if (amount !== (obligation.amount ?? '')) changes.amount = amount;
  if (currency !== obligation.currency) changes.currency = currency;
  if (direction !== obligation.direction) changes.direction = direction;
  const changed = Object.keys(changes).length > 0;

  const field = {
    background: 'var(--color-glass)',
    border: '1px solid var(--color-border-subtle)',
    color: 'var(--color-text)',
    colorScheme: 'dark' as const,
  };

  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">Due</span>
          <input
            type="date"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
            style={field}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            Who owes it
          </span>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as ObligationDirection)}
            className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
            style={field}
          >
            <option value="unknown" style={{ color: '#000' }}>
              Not stated in the document
            </option>
            <option value="owed_by_user" style={{ color: '#000' }}>
              You owe this
            </option>
            <option value="owed_to_user" style={{ color: '#000' }}>
              Owed to you
            </option>
          </select>
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            What it is
          </span>
          <input
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
            style={field}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">Amount</span>
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder="none stated"
            className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
            style={{ ...field, fontFamily: 'var(--font-mono)' }}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">Currency</span>
          <input
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            placeholder="GBP"
            className="rounded-lg px-2.5 py-1.5 text-[11px] outline-none"
            style={{ ...field, fontFamily: 'var(--font-mono)' }}
          />
        </label>
      </div>

      <p className="mt-2 text-[10px] text-slate-500">
        The clause above is not editable — a correction says Zaram read the sentence
        wrongly, not that the sentence was different. The original is kept and struck
        through.
      </p>

      <div className="mt-2 flex gap-2">
        <button
          disabled={busy || !changed}
          onClick={() => onSubmit(changes)}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40"
          style={{
            border: '1px solid var(--color-border)',
            background: 'rgba(255,255,255,0.08)',
            color: 'var(--color-text)',
          }}
        >
          <Check size={12} />
          Save correction
        </button>
        <button
          onClick={onCancel}
          className="rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

type View = 'open' | 'closed';

export interface CommitmentsProps {
  /** Reported upwards after every load, including a failed one, where the
   *  counts are zero rather than stale. Memory takes its own first reading on
   *  mount — the badge has to exist before the user opens this tab, or it
   *  is not a reason to open it — and this keeps that reading current. */
  onCounts?: (counts: ObligationCounts) => void;
}

export default function Commitments({ onCounts }: CommitmentsProps) {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [questions, setQuestions] = useState<ObligationQuestion[]>([]);
  const [view, setView] = useState<View>('open');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [confirmDismiss, setConfirmDismiss] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (which: View) => {
      setLoading(true);
      try {
        const listing = await fetchObligations({ includeClosed: which === 'closed' });
        setObligations(listing.obligations);
        setQuestions(listing.questions);
        setError(null);
        onCounts?.(countObligations(listing));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not load commitments.');
        setObligations([]);
        setQuestions([]);
        // Zero, not the previous figure: a count left standing beside an
        // error message claims a measurement that just failed.
        onCounts?.({ open: 0, overdue: 0, questions: 0 });
      } finally {
        setLoading(false);
      }
    },
    [onCounts],
  );

  useEffect(() => {
    void load(view);
  }, [view, load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load(view);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.');
    } finally {
      setBusy(false);
    }
  };

  /** The obligation that replaced a superseded one, so the old row can point
   *  at it. Only resolvable in the closed view, which is the only one that
   *  returns superseded rows. */
  const replacementOf = useCallback(
    (id: string | null) => obligations.find((o) => o.id === id) ?? null,
    [obligations],
  );

  const visible = useMemo(
    () =>
      view === 'open'
        ? obligations
        : // Everything, so a correction and a dismissal can both be audited.
          obligations.filter((o) => o.status !== 'open' || o.superseded_by),
    [obligations, view],
  );

  return (
    <div className="flex-1 overflow-y-auto px-8 pb-8">
      <div className="flex items-center gap-2 pb-3">
        {(
          [
            ['open', 'Live'],
            ['closed', 'Settled and corrected'],
          ] as [View, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setView(id);
              setExpanded(null);
              setEditing(null);
            }}
            className="rounded-full px-3 py-1 text-[11px] transition-colors hover:bg-white/5"
            style={{
              border: `1px solid ${view === id ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
              background: view === id ? 'rgba(255,255,255,0.08)' : 'transparent',
              color: view === id ? 'var(--color-text)' : 'var(--color-text-muted)',
            }}
          >
            {label}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => void load(view)}
          aria-label="Refresh commitments"
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg px-4 py-3 text-xs mb-3"
          style={{ background: 'rgba(248,113,113,0.08)', color: '#fca5a5' }}
        >
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* The questions, first. A document Zaram read incompletely must not look
          as though it was read cleanly. */}
      {view === 'open' && questions.length > 0 && (
        <section className="mb-5">
          <h3 className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Zaram could not work out {questions.length === 1 ? 'this date' : 'these dates'}
          </h3>
          <ul className="flex flex-col gap-1.5">
            {questions.map((q) => (
              <QuestionCard
                key={q.id}
                question={q}
                busy={busy}
                onAnswer={(anchor) =>
                  void act(() => answerObligationQuestion(q.id, anchor))
                }
              />
            ))}
          </ul>
        </section>
      )}

      {!error && !loading && visible.length === 0 && (
        <div className="py-16 text-center">
          <p className="text-sm text-slate-400">
            {view === 'closed'
              ? 'Nothing has been settled or corrected yet.'
              : questions.length > 0
                ? 'Nothing dated yet — answer the question above and it will appear here.'
                : 'Zaram has not found any commitments.'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {view === 'closed'
              ? 'Marking something done, or saying it was never a commitment, keeps it here.'
              : 'Add a contract, quote or invoice under Knowledge — Zaram reads the dates out of it.'}
          </p>
        </div>
      )}

      {visible.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {visible.map((o) => {
            const superseded = Boolean(o.superseded_by);
            const isOpen = expanded === o.id;
            const replacement = replacementOf(o.superseded_by);
            const days = daysUntil(o.due);
            const late = o.status === 'open' && !superseded && days !== null && days < 0;
            const settled = o.status !== 'open';
            // How long until it falls due, but only while that is still a
            // question. A countdown beside "done" describes a deadline that
            // stopped mattering when the user said so.
            const relative = superseded || settled ? null : dueLabel(o.due);

            return (
              <li
                key={o.id}
                className="rounded-lg transition-colors"
                style={{
                  border: `1px solid ${isOpen ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
                  background: isOpen ? 'rgba(255,255,255,0.03)' : 'transparent',
                  // A superseded or settled row recedes and is never hidden.
                  opacity: superseded || settled ? 0.55 : 1,
                }}
              >
                <div className="px-4 py-3">
                  <button
                    onClick={() => setExpanded(isOpen ? null : o.id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-start gap-2">
                      <KindBadge kind={o.kind} />
                      <p
                        className="text-sm leading-snug flex-1"
                        style={{
                          color: 'var(--color-text)',
                          textDecoration: superseded ? 'line-through' : undefined,
                        }}
                      >
                        {o.summary}
                        {amountIsNews(o.amount, o.summary) && (
                          <span style={{ fontFamily: 'var(--font-mono)' }}>
                            {' '}
                            · {money(o.amount, o.currency)}
                          </span>
                        )}
                      </p>
                    </div>

                    <p
                      className="mt-1.5 flex items-center gap-1.5 text-[10px]"
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      <CalendarClock size={10} className="text-slate-500" />
                      <span style={{ color: late ? 'rgb(248,113,113)' : 'var(--color-text-muted)' }}>
                        {longDate(o.due)}
                        {relative && ` · ${relative}`}
                      </span>
                      {settled && (
                        <span className="text-slate-500">
                          · {o.status === 'met' ? 'done' : 'not a commitment'}
                        </span>
                      )}
                      {superseded && o.superseded_at && (
                        <span style={{ color: 'var(--color-amber, #fbbf24)' }}>
                          · corrected {shortStamp(o.superseded_at)}
                        </span>
                      )}
                    </p>
                  </button>

                  {/* Always visible. The evidence is the point. */}
                  <SourceClause
                    text={o.source_clause.text}
                    document={o.source_document_id}
                  />

                  {superseded && replacement && (
                    <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-slate-400">
                      <CornerDownRight size={11} className="mt-0.5 shrink-0" />
                      {/* What it became. Direction is named only when it is
                          what moved, because correcting it alone otherwise
                          produces a replacement line identical to the struck
                          row above — an audit trail showing that something
                          changed and not what. */}
                      <span>
                        {replacement.summary} · {longDate(replacement.due)}
                        {replacement.direction !== o.direction &&
                          ` · ${DIRECTION_LABELS[replacement.direction].toLowerCase()}`}
                      </span>
                    </p>
                  )}
                </div>

                {isOpen && !superseded && (
                  <div
                    className="px-4 pb-3 pt-3"
                    style={{ borderTop: '1px solid var(--color-border-subtle)' }}
                  >
                    {editing === o.id ? (
                      <CorrectForm
                        obligation={o}
                        busy={busy}
                        onCancel={() => setEditing(null)}
                        onSubmit={(changes) =>
                          void act(async () => {
                            await correctObligation(o.id, changes);
                            setEditing(null);
                            setExpanded(null);
                          })
                        }
                      />
                    ) : confirmDismiss === o.id ? (
                      <div>
                        <p className="text-[11px] text-slate-300 mb-2">
                          Say this was never a commitment? It stays here, marked, so the
                          same clause is not read out of the document again.
                        </p>
                        <div className="flex gap-2">
                          <button
                            disabled={busy}
                            onClick={() =>
                              void act(async () => {
                                await dismissObligation(o.id);
                                setConfirmDismiss(null);
                                setExpanded(null);
                              })
                            }
                            className="rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40"
                            style={{
                              border: '1px solid rgba(248,113,113,0.4)',
                              color: 'rgb(248,113,113)',
                            }}
                          >
                            Not a commitment
                          </button>
                          <button
                            onClick={() => setConfirmDismiss(null)}
                            className="rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* The one thing the document cannot say, offered as
                            one click rather than buried in the form. */}
                        <p className="text-[11px] text-slate-400 mb-2">
                          {DIRECTION_LABELS[o.direction]}
                          {o.direction === 'unknown' && '.'}
                        </p>
                        {o.direction === 'unknown' && (
                          <div className="flex gap-2 mb-3">
                            <button
                              disabled={busy}
                              onClick={() =>
                                void act(() =>
                                  correctObligation(o.id, { direction: 'owed_by_user' }),
                                )
                              }
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                              style={{ border: '1px solid var(--color-border-subtle)' }}
                            >
                              <ArrowUpRight size={12} />
                              You owe this
                            </button>
                            <button
                              disabled={busy}
                              onClick={() =>
                                void act(() =>
                                  correctObligation(o.id, { direction: 'owed_to_user' }),
                                )
                              }
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                              style={{ border: '1px solid var(--color-border-subtle)' }}
                            >
                              <ArrowDownLeft size={12} />
                              Owed to you
                            </button>
                          </div>
                        )}

                        <div className="flex gap-2 flex-wrap">
                          <button
                            disabled={busy}
                            onClick={() => setEditing(o.id)}
                            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                            style={{ border: '1px solid var(--color-border-subtle)' }}
                          >
                            <Pencil size={12} />
                            Correct
                          </button>
                          {o.status === 'open' && (
                            <button
                              disabled={busy}
                              onClick={() =>
                                void act(async () => {
                                  await markObligationMet(o.id);
                                  setExpanded(null);
                                })
                              }
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                              style={{ border: '1px solid var(--color-border-subtle)' }}
                            >
                              <Check size={12} />
                              Done
                            </button>
                          )}
                          {o.status === 'open' && (
                            <button
                              disabled={busy}
                              onClick={() => setConfirmDismiss(o.id)}
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40 hover:bg-white/5"
                              style={{
                                border: '1px solid var(--color-border-subtle)',
                                color: 'rgb(248,113,113)',
                              }}
                            >
                              <X size={12} />
                              Not a commitment
                            </button>
                          )}
                          <div className="flex-1" />
                          <button
                            onClick={() => setExpanded(null)}
                            aria-label="Collapse"
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-white/5 transition-colors"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
