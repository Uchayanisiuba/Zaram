/**
 * Select a part of a reply and ask about that part.
 *
 * Asked for by the maintainer on 3 October 2026, naming Claude's behaviour:
 * *"I would like to select sections of Zaram's responses and reply them as a
 * new prompt."* The want underneath it is narrower than it sounds and worth
 * stating, because it decides the design: a long reply has one paragraph you
 * actually mean, and typing *"the second thing you said about the gate"* is
 * both slower than pointing at it and less precise — it asks the model to
 * re-resolve a reference that was unambiguous a second ago.
 *
 * That makes this a **grounding** feature rather than a convenience. Rule 9 is
 * the one it serves: *"when recall cannot resolve what the user is referring
 * to, say so and ask"*, and the documented failure behind that rule is a
 * referential prompt — *"write that up as a proposal"* — retrieving nothing
 * and the model inventing a client. A quote removes the reference entirely.
 * The text is in the prompt; there is nothing left to resolve.
 *
 * Three decisions, each of which could have gone the other way.
 *
 * **It is a chip above the composer, not text inserted into it.** The composer
 * is a single-line `<input type="text">`, so a multi-line quote put *in* it
 * would have to be flattened to one line — and the obvious flattening,
 * newlines to spaces, silently joins a list into a sentence. The chip keeps
 * the selection intact and the person's own question separate from it, which
 * is also what the `revising` chip beside it already does and what Claude
 * does. Nothing about the composer had to change.
 *
 * **Markers come off.** `[M1]` and `[S2]` are grounding tags that mean nothing
 * outside Zaram, and a quote carrying them would send the model its own
 * citation labels back. `stripCitationMarkers` is the function, not a fresh
 * regex: there were three callers of that idea once and the one that had been
 * missed was the one that spoke the markers aloud. This is the fifth caller.
 *
 * **Nothing is truncated.** A selection is the person naming exactly what they
 * mean, and shortening it to fit would answer a question they did not ask —
 * the same reasoning that lets somebody pin more tools than the context budget
 * has room for. The chip shows the first line and the full text is in its
 * `title`; the prompt carries all of it.
 *
 * What this is **not**: it does not send anything on its own. The quote arms
 * the next message and the person still types the question, for the same
 * reason dictated speech lands in the composer as editable text rather than
 * being submitted — a feature that acts on a selection the moment it is made
 * has spoken for them.
 */
import { useCallback, useEffect, useState } from 'react';
import { Quote } from 'lucide-react';

import { stripCitationMarkers } from '@/lib/markers';

/** Marks a region whose text may be quoted. Put on each assistant message. */
export const QUOTABLE = 'data-zaram-quotable';

/** Selections shorter than this are a mis-click, not an intention.
 *
 *  A double-click lands two or three characters and a stray drag lands one;
 *  offering to quote those puts a button over the text every time somebody
 *  taps it. Three is low enough that a deliberately selected short word —
 *  a name, `npm`, a number — still offers. */
export const MIN_QUOTE_CHARS = 3;

/** How much of the quote the chip shows before it elides.
 *
 *  Display only. The prompt carries the whole thing; see the header. */
export const CHIP_CHARS = 80;

/**
 * The selection turned into the lines that go in front of the question.
 *
 * Exported and pure so the transform is tested without a DOM: markers off,
 * every line prefixed, blank lines kept as bare `>` so a quoted list does not
 * collapse into one paragraph.
 *
 * Markdown blockquote rather than quotation marks, because the reply was
 * markdown and the model reads markdown. Quotation marks around a passage that
 * itself contains quotation marks produce a prompt nobody can parse, including
 * the model.
 */
export function quoteLines(selection: string): string {
  const clean = stripCitationMarkers(selection).trim();
  if (!clean) return '';
  return clean
    .split(/\r?\n/)
    .map((line) => (line.trim() ? `> ${line.trim()}` : '>'))
    .join('\n');
}

/**
 * The whole prompt: the quote, a blank line, then what they typed.
 *
 * The blank line is load-bearing — without it markdown folds the question
 * into the blockquote and the model reads its own words and the person's as
 * one passage.
 */
export function promptWithQuote(quote: string, question: string): string {
  const lines = quoteLines(quote);
  if (!lines) return question;
  return `${lines}\n\n${question}`;
}

/** What `useQuotableSelection` reports: the text, and where to put the button. */
export interface Quotable {
  text: string;
  /** Viewport coordinates of the selection's end, for the floating button. */
  x: number;
  y: number;
}

/** Is this node inside something marked quotable? */
function insideQuotable(node: Node | null): boolean {
  let el: Node | null = node;
  while (el) {
    if (el instanceof HTMLElement && el.hasAttribute(QUOTABLE)) return true;
    el = el.parentNode;
  }
  return false;
}

/**
 * Watch for a selection inside a quotable region.
 *
 * Both ends must be inside one, so a drag that starts in a reply and finishes
 * in the composer does not offer to quote half the interface. `selectionchange`
 * rather than `mouseup`, because keyboard selection and touch handles are
 * selections too and a mouse-only trigger would quietly exclude both.
 */
export function useQuotableSelection(): {
  quotable: Quotable | null;
  clear: () => void;
} {
  const [quotable, setQuotable] = useState<Quotable | null>(null);

  const clear = useCallback(() => {
    setQuotable(null);
    try {
      window.getSelection()?.removeAllRanges();
    } catch {
      /* a browser that refuses is a browser where the button simply goes */
    }
  }, []);

  useEffect(() => {
    const read = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
        setQuotable(null);
        return;
      }
      const text = selection.toString();
      if (text.trim().length < MIN_QUOTE_CHARS) {
        setQuotable(null);
        return;
      }
      if (!insideQuotable(selection.anchorNode) || !insideQuotable(selection.focusNode)) {
        setQuotable(null);
        return;
      }
      // The end of the selection, which is where the cursor already is.
      //
      // **Guarded, and the first version was not.** A comment here claimed
      // rects could be missing and the call was made anyway, so a `Range`
      // without `getClientRects` threw inside a `selectionchange` handler —
      // which does not merely lose the button, it breaks the listener for the
      // rest of the session. jsdom is one such `Range`, which is how this was
      // found; the lesson is the one the egress exemption taught an hour
      // earlier, that a comment describing a guard is not a guard.
      let x = 0;
      let y = 0;
      try {
        const rects = selection.getRangeAt(0).getClientRects();
        const last = rects[rects.length - 1];
        if (last) {
          x = last.right;
          y = last.bottom;
        }
      } catch {
        /* no geometry; the button renders where it can rather than not at all */
      }
      setQuotable({ text, x, y });
    };

    document.addEventListener('selectionchange', read);
    return () => document.removeEventListener('selectionchange', read);
  }, []);

  return { quotable, clear };
}

/**
 * The floating offer, at the end of the selection.
 *
 * Rule 7h: *offer at the moment of doubt; never make the user choose in
 * advance.* There is no setting for this and no button in the message row —
 * it appears because text is selected, which is the only moment it means
 * anything, and it costs nothing the rest of the time.
 *
 * `onMouseDown` with `preventDefault`, not `onClick`: a click clears the
 * selection before the handler runs, so by the time `onClick` fired there
 * would be nothing to quote.
 */
export default function QuoteButton({
  quotable,
  onQuote,
}: {
  quotable: Quotable | null;
  onQuote: (text: string) => void;
}) {
  if (!quotable) return null;
  return (
    <button
      type="button"
      className="fixed z-50 flex items-center gap-1 rounded-md px-2 py-1 text-xs shadow-lg"
      style={{
        left: Math.max(8, quotable.x - 40),
        top: quotable.y + 6,
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border-subtle)',
        color: 'var(--color-text)',
      }}
      onMouseDown={(e) => {
        e.preventDefault();
        onQuote(quotable.text);
      }}
      data-testid="quote-selection"
      aria-label="Ask about this part"
    >
      <Quote size={11} aria-hidden />
      Ask about this
    </button>
  );
}

/** The armed quote, above the composer, beside the revising chip. */
export function QuoteChip({
  quote,
  onDrop,
}: {
  quote: string;
  onDrop: () => void;
}) {
  const oneLine = quote.replace(/\s+/g, ' ').trim();
  return (
    <div
      className="flex items-start justify-between gap-2 rounded-lg px-2.5 py-1.5 mb-2 text-xs"
      style={{
        background: 'var(--color-glass)',
        border: '1px solid var(--color-border-subtle)',
        borderLeft: '2px solid var(--color-cyan)',
      }}
      data-testid="quote-chip"
    >
      {/* The full selection in `title`, because the chip elides and the
          person should be able to check what they actually caught. */}
      <span className="truncate" style={{ color: 'var(--color-text)' }} title={quote}>
        Asking about “
        {oneLine.length > CHIP_CHARS ? `${oneLine.slice(0, CHIP_CHARS)}…` : oneLine}”
      </span>
      <button
        type="button"
        className="text-xs px-1.5 py-0.5 rounded shrink-0"
        style={{ color: 'var(--color-text-muted)' }}
        onClick={onDrop}
        aria-label="Drop the quote"
      >
        ✕
      </button>
    </div>
  );
}
