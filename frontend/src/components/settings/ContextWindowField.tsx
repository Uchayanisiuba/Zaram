/**
 * How much context to ask a local model for.
 *
 * Built 4 October 2026 from one sentence: *"a while ago, I needed to use
 * Claude to increase Zaram's LLM context token limit."* **Rebuilt the same
 * day from the next one:** *"should we have the default token limit to be
 * high, something like 128k, and only adjust down based on the model's
 * limit? I don't want users to need to switch token limits every time they
 * switch or download a new model, there needs to be a more elegant
 * alternative."*
 *
 * The first version was a ladder of sizes and one stored number, and that
 * is the thing being replaced. A single figure cannot be right for two
 * models, so it becomes a chore exactly as described.
 *
 * **Why the elegant answer is not "default to 128k and clamp to the
 * model's limit".** The model's limit is almost never the binding
 * constraint — the card is. Measured on the maintainer's machine,
 * `qwen3-14b-16k` costs 160 KiB per cached token, so 131,072 tokens is
 * **21.5 GB** of cache on a 12 GB card, and even its own declared ceiling
 * of 40,960 is 6.7 GB on top of 9.3 GB of weights. Clamping to the model
 * would still produce a window that will not load, and it does not fail
 * cleanly: Ollama spills the cache into system RAM and every reply becomes
 * slow, which reads as the model being bad rather than as a setting being
 * wrong.
 *
 * So the control stops storing a number and stores an **intent**, and
 * `context_budget.resolve_context_window` works the figure out against
 * *(this model, this card)* at call time. Nothing to re-pick on a model
 * switch or a new download, which is what was asked for.
 *
 * **It shows the resolved figure and where it came from.** Routing
 * legibility applied to the one setting whose wrong value makes a good
 * model look bad — measured, `qwen3-14b-16k` resolves to 16k *from the
 * card* while `gemma4:12b` resolves to 128k *from its own file*, and
 * nothing on screen would otherwise distinguish those.
 *
 * **Behind Advanced, and that is the rule rather than timidity.**
 * `CLAUDE.md` keeps context-length sliders out of the primary path because
 * the target user is not technical, and in the same breath puts per-task
 * assignment behind Advanced. With `fit` as the default there is now
 * nothing in here a non-technical person needs to open at all, which is
 * the strongest version of that rule this screen has managed.
 */
import { useEffect, useState } from 'react';

import type { ContextPolicy } from '@/services/settingsClient';
import { cacheCost, fetchContextWindow, type ContextWindow } from '@/services/contextWindowClient';

/** Sizes worth offering for one model, largest first — the same ladder
 *  `CONTEXT_STEPS` resolves onto in the backend, so a window Zaram chose
 *  and a window somebody chose are the same kind of thing. `0` clears the
 *  override and hands the model back to the policy. */
const SIZES = [131_072, 65_536, 32_768, 16_384, 8_192] as const;

const POLICY_LABEL: Record<ContextPolicy, string> = {
  fit: 'As much as fits',
  server: 'Whatever the server does',
  fixed: 'One size for every model',
};

/** The second line under each choice. Each says what the choice *costs*,
 *  because that is the part nobody can see. */
const POLICY_DETAIL: Record<ContextPolicy, string> = {
  fit: 'Zaram works out the most each model can hold on this card, and does it again when you change or download one. Nothing to set.',
  server: 'Ollama decides, which is usually 4,096 tokens however much the model says it can hold.',
  fixed: 'The same number asked of every model, reduced only where a model cannot hold it.',
};

function label(tokens: number): string {
  if (!tokens) return 'Let Zaram decide';
  if (tokens >= 1_024 && tokens % 1_024 === 0) return `${tokens / 1_024}k tokens`;
  return `${tokens.toLocaleString()} tokens`;
}

interface Props {
  policy: ContextPolicy;
  /** The number `fixed` honours. */
  value: number;
  max: number;
  /** Windows set against one model each, by name. */
  overrides: Record<string, number>;
  /** The model this screen has **explicitly** selected, or `''`.
   *
   *  `''` is not "no model" — it is *"Zaram picks"*, which is the first of
   *  the three tiers of control and where most people are. The backend
   *  resolves which model that is and names it in the reply, so the panel
   *  is about a real model either way. Guessing here instead would render
   *  an invented value on the one panel whose subject is memory. */
  model?: string;
  busy?: boolean;
  onChoosePolicy: (policy: ContextPolicy) => void;
  onChooseFixed: (tokens: number) => void;
  onChooseForModel: (model: string, tokens: number) => void;
}

export default function ContextWindowField({
  policy,
  value,
  max,
  overrides,
  model = '',
  busy,
  onChoosePolicy,
  onChooseFixed,
  onChooseForModel,
}: Props) {
  const [open, setOpen] = useState(false);
  const [window_, setWindow] = useState<ContextWindow | null>(null);

  // **Only while the disclosure is open**, so Settings does not call
  // Ollama as a side effect of being looked at. `policy` and the override
  // are in the dependencies because both change the answer, and a panel
  // still showing the old figure after a choice is the control
  // contradicting itself.
  useEffect(() => {
    if (!open) {
      setWindow(null);
      return;
    }
    let live = true;
    void fetchContextWindow(model).then((next) => {
      if (live) setWindow(next);
    });
    return () => {
      live = false;
    };
  }, [open, model, policy, value, overrides[model], overrides[window_?.model ?? '']]);

  // **The model that came back, not the one that was asked for.** They
  // differ exactly when nobody chose one, which is the common setup, and
  // keying the override row off the prop left it blank there.
  const subject = window_?.model ?? model;
  const override = overrides[subject] ?? 0;
  const offered = SIZES.filter((size) => !window_?.ceiling || size <= window_.ceiling);

  return (
    <details
      className="mt-1"
      data-testid="advanced-context"
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="text-xs cursor-pointer select-none" style={{ color: 'var(--color-text-muted)' }}>
        Advanced
      </summary>

      <div className="flex flex-col gap-3 mt-2">
        {/* The decision. Three choices in plain language, which is the
            whole setting — the figure is downstream of this. */}
        <div className="flex flex-col gap-1">
          {(Object.keys(POLICY_LABEL) as ContextPolicy[]).map((option) => {
            const active = policy === option;
            return (
              <button
                key={option}
                type="button"
                data-testid={`context-policy-${option}`}
                aria-pressed={active}
                disabled={busy}
                onClick={() => onChoosePolicy(option)}
                className="rounded-lg px-2.5 py-2 text-left text-xs disabled:opacity-40"
                style={{
                  border: `1px solid ${active ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                  color: active ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                }}
              >
                <span className="block">{POLICY_LABEL[option]}</span>
                <span
                  className="block mt-0.5 leading-snug"
                  style={{ color: 'var(--color-text-faint)', maxWidth: '48ch' }}
                >
                  {POLICY_DETAIL[option]}
                </span>
              </button>
            );
          })}
        </div>

        {/* What that decision actually produced for the selected model,
            and which of the three sources it came from. A resolved
            window with no stated origin is a number the person has to
            trust rather than read. */}
        {open && window_ && (
          <p
            data-testid="context-resolved"
            className="text-xs leading-snug"
            style={{ color: 'var(--color-text)', maxWidth: '52ch' }}
          >
            {`${subject}: ${window_.reason}.`}
            {!window_.settable ? (
              <span style={{ color: 'var(--color-text-faint)' }}>
                {' '}
                That window belongs to the server holding this model, not to Zaram —
                it is fixed when the model loads, so it is changed there rather
                than here.
              </span>
            ) : null}
            {window_.resolved && window_.costPerToken ? (
              <span style={{ color: 'var(--color-text-faint)' }}>
                {' '}
                That cache costs about {cacheCost(window_.resolved, window_.costPerToken)} of
                graphics memory, on every reply rather than only long ones.
              </span>
            ) : null}
            {window_.loaded && window_.resolved && window_.loaded !== window_.resolved ? (
              <span style={{ color: 'var(--color-text-faint)' }}>
                {' '}
                It is loaded with {label(window_.loaded)} and will change on its next load.
              </span>
            ) : null}
          </p>
        )}

        {/* One number for everything, under `fixed` only. Drawn only when
            chosen: a ladder on screen under a policy that ignores it is a
            control that does nothing, which is the shape of a product
            that looks broken. */}
        {policy === 'fixed' && window_?.settable !== false && (
          <div className="flex flex-wrap items-center gap-1.5" data-testid="context-fixed">
            {SIZES.filter((size) => size <= max).map((size) => (
              <button
                key={size}
                type="button"
                data-testid={`context-${size}`}
                aria-pressed={value === size}
                disabled={busy}
                onClick={() => onChooseFixed(size)}
                className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                style={{
                  border: `1px solid ${value === size ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                  color: value === size ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                }}
              >
                {label(size)}
              </button>
            ))}
          </div>
        )}

        {/* And the escape hatch: one model, one number, remembered against
            that model. This is what makes `fit` safe to default to —
            disagreeing with it costs one click and does not change any
            other model. */}
        {subject && window_?.settable !== false && (
          <div className="flex flex-col gap-1.5" data-testid="context-for-model">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Just for {subject}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {[0, ...offered].map((size) => (
                <button
                  key={size}
                  type="button"
                  data-testid={`context-model-${size}`}
                  aria-pressed={override === size}
                  disabled={busy}
                  onClick={() => onChooseForModel(subject, size)}
                  className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                  style={{
                    border: `1px solid ${override === size ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                    color: override === size ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                  }}
                >
                  {label(size)}
                </button>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs leading-snug" style={{ color: 'var(--color-text-faint)', maxWidth: '52ch' }}>
          A context window is graphics memory, claimed on every reply rather than
          only on long ones. Asking for more than the card holds does not fail
          cleanly — it spills into system memory and everything becomes slow.
        </p>
      </div>
    </details>
  );
}
