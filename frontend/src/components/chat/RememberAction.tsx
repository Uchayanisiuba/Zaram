/**
 * "Remember this" — the user putting something into the Spine on purpose.
 *
 * Asked for on 3 September 2026, and the shape matters more than the button.
 *
 * **It is an override, not a gate.** Zaram still decides what to keep on its
 * own, and still forgets what is never used. This exists for the cases a
 * heuristic cannot be trusted with — a rate, a term, a decision already
 * taken — and it is the mirror of the "Don't remember this" that rule 7b
 * already describes as *"an override, never a gate"*. Making it the only way
 * in would ask people to predict at capture time which sentence matters in
 * November, which is rule 7e in as many words.
 *
 * **What it saves is a fact, not the message.** This is the part that would go
 * wrong quietly. Storing the whole exchange is what `CLAUDE.md` calls L0 and
 * rejects outright, and its recorded cost is duplicate citations and Zaram
 * quoting its own replies back. So the text is *editable before it is saved*,
 * pre-filled from the user's selection when there is one — because a person
 * highlighting the sentence they mean is a better extractor than any rule, and
 * it costs them a drag they were probably making anyway.
 *
 * **Saved, not pinned.** They are different promises and the panel says so: a
 * saved fact starts ahead of one merely mentioned and still fades if it is
 * never used; pinning is what makes something permanent, and it lives in
 * Memory where the fact does.
 */
import { useRef, useState } from 'react';
import { Brain, Check, X } from 'lucide-react';

import { rememberText } from '@/services/memoryClient';

/** How long the confirmation stays up. Matches `MessageActions`' copy tick. */
const CONFIRM_MS = 2400;

/**
 * The user's selection, but only when it lies inside *this* message.
 *
 * Without the containment check, text highlighted in a different reply — or in
 * the composer — would be pre-filled here, and someone would save a sentence
 * from somewhere else believing they had saved this one.
 *
 * The message is found by walking up from the button rather than by being
 * handed down as a ref. The transcript renders messages in a `map`, so a ref
 * would have to be one per message, kept in a dictionary, in a component whose
 * only interest in the DOM is this single question.
 */
function selectionInsideMessage(button: HTMLElement | null): string {
  const message = button?.closest('[data-message-id]');
  if (!message) return '';
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return '';
  if (!message.contains(selection.getRangeAt(0).commonAncestorContainer)) return '';
  return selection.toString().trim();
}

export default function RememberAction({
  text,
  origin,
  projectId,
}: {
  text: string;
  /** Whose words these are — rule 7b. `generated` for a Zaram reply. */
  origin: 'conversation' | 'generated';
  projectId: string | null;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);

  const open = () => {
    // The selection wins where there is one: it is the user saying which part
    // they meant, which no rule here could work out.
    const selected = selectionInsideMessage(button.current);
    setError(null);
    setDraft(selected || text.trim());
  };

  const save = async () => {
    const fact = (draft ?? '').trim();
    if (!fact || busy) return;
    setBusy(true);
    setError(null);
    try {
      await rememberText(fact, { projectId, origin });
      setDraft(null);
      setSaved(true);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setSaved(false), CONFIRM_MS);
    } catch (e) {
      // The backend's own sentence where it sent one — "that is too long to
      // keep as one fact" tells the user what to do and "413" does not.
      setError(e instanceof Error ? e.message : 'Could not keep that.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={open}
        disabled={busy || draft !== null}
        aria-label={saved ? 'Kept in Memory' : 'Remember this'}
        title={
          saved
            ? 'Kept in Memory'
            : 'Remember this — select part of the message first to keep just that'
        }
        className="inline-flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] text-slate-500 hover:text-slate-300 hover:bg-white/5 disabled:opacity-30 transition-colors"
      >
        {saved ? (
          <>
            <Check size={11} style={{ color: 'var(--color-emerald)' }} />
            <span style={{ color: 'var(--color-emerald)' }}>Remembered</span>
          </>
        ) : (
          <>
            <Brain size={11} />
            <span>Remember</span>
          </>
        )}
      </button>

      {draft !== null && (
        <div
          className="mt-1 w-full rounded-lg px-2.5 py-2"
          style={{
            background: 'var(--color-glass)',
            border: '1px solid rgba(255,255,255,.08)',
          }}
        >
          {/* Shown before it is stored, and editable, because this is the
              moment the user still knows what they meant. A fact they can
              correct a month later is rule 4; a fact they can get right now is
              cheaper for both sides. */}
          <p className="mb-1.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
            What Zaram should remember. Trim it to the part that matters.
          </p>
          <textarea
            autoFocus
            value={draft}
            rows={3}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setDraft(null);
              // Enter saves; Shift+Enter is a new line, as in the composer.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void save();
              }
            }}
            aria-label="What Zaram should remember"
            className="w-full resize-none rounded-md bg-transparent px-2 py-1.5 text-[11px] outline-none"
            style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
          />

          {error && (
            <p className="mt-1 text-[10px]" style={{ color: '#fca5a5' }}>
              {error}
            </p>
          )}

          <div className="mt-1.5 flex items-center justify-between gap-2">
            {/* Saved and pinned are different promises, so the difference is
                stated where the decision is made rather than discovered later
                when something fades. */}
            <p className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              Kept in Memory. It fades if it is never used — pin it there to keep it for good.
            </p>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => setDraft(null)}
                aria-label="Don't remember this"
                className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[10px]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <X size={11} aria-hidden />
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void save()}
                disabled={busy || !draft.trim()}
                className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] disabled:opacity-40"
                style={{ color: 'var(--color-cyan-light)' }}
              >
                <Check size={11} aria-hidden />
                {busy ? 'Keeping…' : 'Remember'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
