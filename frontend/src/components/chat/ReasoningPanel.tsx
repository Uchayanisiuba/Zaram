import { useState } from 'react';
import { ChevronRight } from 'lucide-react';

/**
 * The model's working, shown above the answer it produced.
 *
 * **Why it is visually quiet.** This is not the reply, and `CLAUDE.md` is
 * explicit that a notice must never be rendered as the model speaking. The same
 * argument applies here with more force: thinking is provisional by definition —
 * it contains the wrong turns the model then abandoned — so styling it like an
 * answer would put discarded reasoning on the same footing as the conclusion.
 * Muted text, no accent border, and collapsed once it is done.
 *
 * **Open while it streams, closed when it finishes.** While the model is still
 * working, the thinking is the only thing there is to look at, and it is what
 * makes a long wait explicable rather than merely long — the same argument the
 * `model_load` event is built on. Once the answer arrives the answer is the
 * point, so this steps out of the way and stays one click from view.
 *
 * The user's own toggle always wins over that default. Someone who collapsed
 * the panel mid-stream meant it, and having it spring back open when the reply
 * lands would read as the interface arguing.
 */
export default function ReasoningPanel({
  text,
  streaming,
}: {
  text: string;
  streaming: boolean;
}) {
  const [override, setOverride] = useState<boolean | null>(null);
  if (!text) return null;

  const open = override ?? streaming;

  return (
    <div style={{ marginBottom: 8 }}>
      <button
        type="button"
        onClick={() => setOverride(!open)}
        aria-expanded={open}
        className="flex items-center gap-1 text-[10px] uppercase tracking-wider"
        style={{
          color: 'var(--color-text-muted)',
          fontFamily: 'var(--font-display)',
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
        }}
      >
        <ChevronRight
          size={11}
          style={{
            transform: open ? 'rotate(90deg)' : 'none',
            transition: 'transform 120ms ease',
          }}
        />
        {/* Present tense while it is happening, past tense once it is not. The
            label is the only thing that reports whether the model is still
            working, because the panel itself looks the same either way. */}
        {streaming ? 'Thinking' : 'Thought process'}
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
