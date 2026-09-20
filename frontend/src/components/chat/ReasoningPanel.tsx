import { useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { reasoningLabel } from './reasoningLabel';

/**
 * The model's working, shown above the answer it produced.
 *
 * **Why it is visually quiet.** This is not the reply, and `CLAUDE.md` is
 * explicit that a notice must never be rendered as the model speaking. The same
 * argument applies here with more force: thinking is provisional by definition —
 * it contains the wrong turns the model then abandoned — so styling it like an
 * answer would put discarded reasoning on the same footing as the conclusion.
 * Muted text, no accent border, and collapsed.
 *
 * **Collapsed by default, always — revised 19 September 2026.** It used to
 * open while streaming on the argument that the thinking was the only thing
 * to look at during the wait. The maintainer watched what that showed: a
 * Qwen deliberating, at length and in the first person, about whether it was
 * Qwen or Zaram — the identity preamble now tells it not to, but a panel that
 * puts every wrong turn on screen by default is still the wrong default. So
 * the reference is Claude's: **one quiet line** that says what the model is
 * on, changing as it moves, with the full text one click away and never
 * deleted.
 *
 * The line is the model's own words — the checklist item it is doing, else
 * the opening of its latest paragraph (`reasoningLabel`). Never a generated
 * summary: no second model call, and no invented value.
 *
 * *Thought for 12 s* is measured here, by this component, from the first
 * render with `streaming` to the first without it. A message restored from
 * history has no such measurement and shows none — a number nobody measured
 * is not rendered.
 *
 * The user's own toggle always wins over the default. Someone who opened the
 * panel mid-stream meant it, and having it close when the reply lands would
 * read as the interface arguing.
 */
export default function ReasoningPanel({
  text,
  streaming,
  doing,
}: {
  text: string;
  streaming: boolean;
  /** The checklist item the model has marked `doing`, if it keeps one. */
  doing?: string | null;
}) {
  const [override, setOverride] = useState<boolean | null>(null);
  const startedAt = useRef<number | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);

  useEffect(() => {
    if (streaming) {
      if (startedAt.current === null) startedAt.current = Date.now();
    } else if (startedAt.current !== null && seconds === null) {
      setSeconds(Math.max(1, Math.round((Date.now() - startedAt.current) / 1000)));
    }
  }, [streaming, seconds]);

  if (!text) return null;

  const open = override ?? false;
  const line = reasoningLabel(text, doing);
  const heading = streaming ? 'Thinking' : seconds !== null ? `Thought for ${seconds} s` : 'Thought process';

  return (
    <div style={{ marginBottom: 8 }} data-testid="reasoning-panel">
      <button
        type="button"
        onClick={() => setOverride(!open)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs"
        style={{
          color: 'var(--color-text-muted)',
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          maxWidth: '100%',
          textAlign: 'left',
        }}
      >
        <ChevronRight
          size={11}
          style={{
            flex: 'none',
            transform: open ? 'rotate(90deg)' : 'none',
            transition: 'transform 120ms ease',
          }}
        />
        {/* Present tense while it is happening, past tense once it is not. The
            heading is the only thing that reports whether the model is still
            working, because the panel itself looks the same either way. */}
        <span
          className="uppercase tracking-wider"
          style={{ fontFamily: 'var(--font-display)', flex: 'none' }}
        >
          {heading}
        </span>
        {line && !open && (
          <span
            data-testid="reasoning-line"
            style={{
              color: 'var(--color-text-faint, var(--color-text-muted))',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              minWidth: 0,
            }}
          >
            {line}
          </span>
        )}
      </button>

      {open && (
        <p
          className="text-xs leading-relaxed whitespace-pre-wrap"
          style={{
            color: 'var(--color-text-muted)',
            borderLeft: '1px solid var(--color-border)',
            paddingLeft: 10,
            marginTop: 6,
          }}
        >
          {text}
        </p>
      )}
    </div>
  );
}
