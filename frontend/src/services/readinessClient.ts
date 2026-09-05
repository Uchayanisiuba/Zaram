/**
 * Readiness — whether Zaram can answer yet, and what to offer if it cannot.
 *
 * `/health` says the process is alive. This says something different and more
 * useful on a fresh install: whether the *product* can do its job. A machine
 * with no engine and no key is not broken, but a composer that answers nothing
 * looks broken, which is worse.
 *
 * Two mappings below are the whole point of this file existing rather than the
 * component calling `fetch` directly.
 *
 * **`downloadLabel` is `null`, never `""` and never `"0 MB"`.** The backend
 * returns an empty string when nothing is fetched; a component rendering that
 * shows an empty space where a price belongs, and a component computing its own
 * would show `0 MB`, which reads as *free* rather than as *absent*. One
 * representation of "there is no size", enforced here so no view has to
 * remember.
 *
 * **The label is taken, not recomputed.** It is a second spelling of
 * `downloadBytes` and the two can disagree; the backend already formats it, so
 * this carries it across rather than deriving it again.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What the product can do right now. */
export type ReadinessState = 'ready' | 'engine_without_model' | 'no_engine';

/** What the user can choose. Left open to a string: an offer kind this build
 *  does not know about should still render its label and detail, because those
 *  are written for a person and are readable without the enum. */
export type OfferKind =
  | 'install_engine'
  | 'pull_model'
  | 'use_cloud_key'
  | 'explore';

export interface ReadinessOffer {
  kind: OfferKind | string;
  /** The button, as a person would read it. */
  label: string;
  /** One sentence on what happens if they choose it. */
  detail: string;
  /** Bytes that would be downloaded, or null when nothing is fetched. */
  downloadBytes: number | null;
  /** The same figure, formatted, or null. Show this on the button itself. */
  downloadLabel: string | null;
  /**
   * The date on the list the model was recommended from, or null when it came
   * from the fallback constant instead.
   *
   * Shown rather than held: a recommendation is only as current as the list
   * behind it, and `CLAUDE.md` asks for the manifest's date to be visible.
   * Null is a real answer here too — a fallback has no list behind it, and
   * rendering today's date would put a figure on screen that nothing produced.
   */
  recommendedOn: string | null;
}

export interface ReadinessReport {
  readiness: ReadinessState | string;
  /** One line for the user. Plain language, no model filenames. */
  summary: string;
  canChat: boolean;
  offers: ReadinessOffer[];
  /** What works while unready. The difference between "unconfigured" and
   *  "broken", and the reason someone explores instead of uninstalling. */
  stillWorks: string[];
}

export async function fetchReadiness(): Promise<ReadinessReport> {
  const res = await fetch(`${API_BASE}/readiness`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const raw = (await res.json()) as Record<string, unknown>;

  const offers = Array.isArray(raw.offers) ? (raw.offers as Record<string, unknown>[]) : [];

  return {
    readiness: String(raw.readiness ?? 'no_engine'),
    summary: String(raw.summary ?? ''),
    canChat: Boolean(raw.can_chat),
    offers: offers.map((o) => {
      const bytes = o.download_bytes == null ? null : Number(o.download_bytes);
      const label = String(o.download_label ?? '').trim();
      const recommendedOn = String(o.recommended_on ?? '').trim();
      return {
        kind: String(o.kind ?? ''),
        label: String(o.label ?? ''),
        detail: String(o.detail ?? ''),
        downloadBytes: bytes,
        // No bytes means no price, whatever the label says. The two cannot
        // disagree downstream if only one of them can be present.
        downloadLabel: bytes == null || !label ? null : label,
        // Empty and absent collapse to the same null, for the same reason the
        // label does: one representation of "there is none".
        recommendedOn: recommendedOn || null,
        // `model_name` is on the payload and deliberately not carried across.
        // No model filename belongs in the primary path, so nothing here would
        // render it — it is there for whatever executes the pull, and mapping
        // it before that exists would add a value no view reads.
      };
    }),
    stillWorks: Array.isArray(raw.still_works) ? raw.still_works.map(String) : [],
  };
}
