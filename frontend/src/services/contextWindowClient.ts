/**
 * What Zaram will actually ask this model for, and where that figure came
 * from.
 *
 * **A route of its own rather than a field on the settings payload**, for
 * the reason `/providers/context-ceiling` was separated in the first
 * place: reading Settings must not make a network call as a side effect.
 * It is loopback and cheap, but rule 7g's posture is that refreshing from
 * anywhere is an action rather than a consequence of looking.
 *
 * Three numbers that disagree, which is the whole reason this exists —
 * measured on the maintainer's machine, 4 October 2026:
 *
 * | | `gemma4:12b` | `qwen3-14b-16k` |
 * |---|---|---|
 * | declares it can hold | 262,144 | 40,960 |
 * | its own file asks for | 131,072 | 16,384 |
 * | loads with | 4,096 | 16,384 |
 * | **Zaram resolves to** | 131,072 | 16,384 |
 *
 * and the two resolved figures come from different places: gemma4's from
 * its author, qwen3's from the card. Nothing on screen would distinguish
 * those, which is what `reason` is for.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface ContextWindow {
  /** **What was actually answered about.** With no model named the
   *  backend resolves the one that would answer a question, which is the
   *  common case — an explicit default is the third of the three tiers of
   *  control, and most people are on the first. So this is read back
   *  rather than assumed to be what was asked for. */
  model: string;
  /** The ceiling the model's own file declares, or `null`. */
  ceiling: number | null;
  /** What it actually came up with, or `null` if it is not loaded. */
  loaded: number | null;
  /** What Zaram will ask for. `0` means *send no `num_ctx`* — a decision,
   *  not an absence of one. `null` only when no model was named. */
  resolved: number | null;
  /** Shown to the person. "16k tokens, the most this card affords beside
   *  the weights" reads differently from "16k tokens, set for this
   *  model", and they are the same number. */
  reason: string;
  /** Graphics memory one cached token costs, or `null` when the cache
   *  cannot be priced — `gemma4`'s sliding-window layers are exactly
   *  that, so this is not an edge case. **Never 0**: that would let the
   *  interface conclude context is free. */
  costPerToken: number | null;
  /** **Whether Zaram can set this window at all.**
   *
   *  `num_ctx` is an Ollama request field. An OpenAI-compatible server —
   *  TabbyAPI, llama.cpp — fixes its window when it loads the model, so
   *  there the figure is *reported* and the place to change it is that
   *  server. Offering a control over it would be a switch that settles
   *  nothing, which is what the permission card already refuses to ship.
   *
   *  Measured 4 October 2026: the model that answers on the maintainer's
   *  machine is `Qwen3.8-27B-exl3-2.20bpw` under TabbyAPI, holding
   *  65,536 tokens — and the first version of this feature reported
   *  *"whatever the server does, usually 4,096"* for it, because every
   *  reader spoke only Ollama. */
  settable: boolean;
  /** Which runtime answered — `'ollama'`, `'local server'`, or `''`. Said
   *  out loud when it is not the one a person would assume. */
  servedBy: string;
}

/** The resolved window, or `null`.
 *
 *  **Never throws.** A control that failed to render because Ollama was
 *  slow is worse than one that renders without the explanation. */
export async function fetchContextWindow(model: string): Promise<ContextWindow | null> {
  try {
    const response = await fetch(
      `${API_BASE}/providers/context-ceiling?model=${encodeURIComponent(model)}`,
    );
    if (!response.ok) return null;
    const body = await response.json();
    // A backend with no provider layer started, or a machine with
    // nothing installed, answers with no model. There is nothing to say
    // about a window then, and saying it about a model that is not going
    // to run would be worse than saying nothing.
    if (!body.model) return null;
    return {
      model: String(body.model),
      ceiling: typeof body.ceiling === 'number' ? body.ceiling : null,
      loaded: typeof body.loaded === 'number' ? body.loaded : null,
      resolved: typeof body.resolved === 'number' ? body.resolved : null,
      reason: String(body.reason ?? ''),
      costPerToken: typeof body.cost_per_token === 'number' ? body.cost_per_token : null,
      // Only an exact `false` means not settable. A backend older than
      // this field is an Ollama-only one, where it always was.
      settable: body.settable !== false,
      servedBy: typeof body.served_by === 'string' ? body.served_by : '',
    };
  } catch {
    return null;
  }
}

/** `2.7 GB`. What a window of this size costs on the card, or `''` when
 *  the cache cannot be priced — which is a real and common state, so the
 *  caller renders nothing rather than `0 GB`. */
export function cacheCost(tokens: number, costPerToken: number | null): string {
  if (!costPerToken || !tokens) return '';
  const bytes = tokens * costPerToken;
  // Decimal, matching `gigabytes()` in the model catalogue and every
  // download figure a person compares against.
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}
