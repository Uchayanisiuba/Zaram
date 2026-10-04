/**
 * How much context to ask a local model for.
 *
 * Built 4 October 2026 from one sentence: *"a while ago, I needed to use
 * Claude to increase Zaram's LLM context token limit."*
 *
 * **Zaram could read this number and not set it.** `context_budget.py`
 * exists because Ollama serves its own `num_ctx` whatever a model
 * advertises — measured on the maintainer's machine, `gemma4:12b` reports
 * a 262,144-token maximum and loads with **4,096**. That module is the
 * measurement; there was no control, and the way past the default was a
 * Modelfile written by hand somewhere else.
 *
 * **Behind Advanced, and that is the rule rather than timidity.**
 * `CLAUDE.md` keeps context-length sliders out of the primary path
 * because the target user is not technical, and in the same breath puts
 * per-task assignment behind Advanced. The people who need this know they
 * need it.
 *
 * **It says what it costs.** A KV cache is VRAM, and a window somebody
 * raises for one long document is paid on every reply afterwards. Raising
 * it past what the card holds does not fail cleanly — it spills into
 * system RAM and everything becomes slow, which reads as the model being
 * bad rather than the setting being wrong. So the help text leads with the
 * cost and the field offers sizes rather than a free-running slider.
 */
import { useEffect, useState } from 'react';

/** Sizes worth offering, smallest first. `0` is "leave it alone". */
const SIZES = [0, 8_192, 16_384, 32_768, 65_536, 131_072] as const;

function label(tokens: number): string {
  if (!tokens) return 'Whatever the server does';
  if (tokens >= 1_000) return `${Math.round(tokens / 1_024)}k tokens`;
  return `${tokens} tokens`;
}

interface Props {
  value: number;
  max: number;
  busy?: boolean;
  onChoose: (tokens: number) => void;
}

export default function ContextWindowField({ value, max, busy, onChoose }: Props) {
  const [chosen, setChosen] = useState(value);
  useEffect(() => setChosen(value), [value]);

  // Never offer a size the backend would clamp. A control that accepts a
  // number and then shows a smaller one back is the shape of a product
  // that looks broken.
  const offered = SIZES.filter((size) => size === 0 || size <= max);

  return (
    // Behind Advanced, matching `AdvancedModelField`: one disclosure
    // pattern in Settings rather than two, and the three tiers of control
    // put a context length here rather than in the primary path.
    <details className="mt-1" data-testid="advanced-context">
      <summary
        className="text-xs cursor-pointer select-none"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Advanced
      </summary>
      <div className="flex flex-col gap-2 mt-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {offered.map((size) => {
          const active = chosen === size;
          return (
            <button
              key={size}
              type="button"
              data-testid={`context-${size}`}
              disabled={busy}
              onClick={() => {
                setChosen(size);
                onChoose(size);
              }}
              className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
              style={{
                border: `1px solid ${active ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                color: active ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
              }}
            >
              {label(size)}
            </button>
          );
        })}
      </div>
      <p className="text-xs leading-snug" style={{ color: 'var(--color-text-faint)', maxWidth: '52ch' }}>
        {chosen === 0
          ? 'Ollama serves its own default — often 4,096 tokens, whatever the model says it can do. Raise it if Zaram keeps losing the start of a long document.'
          : 'This memory is taken from the graphics card on every reply, not just long ones. If replies become slow after changing this, the card is full and a smaller window is the remedy.'}
        </p>
      </div>
    </details>
  );
}
