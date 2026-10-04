/**
 * The models Zaram knows about, graded against this machine.
 *
 * `/readiness` offers exactly one — *the first of the tier* — which is
 * right for a first run and wrong for somebody who wants to choose. This
 * is the list behind the browser.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface CatalogueModel {
  name: string;
  /** The download, as the manifest quotes it. Approximate and dated on
   *  purpose; the pull itself reports the real total. */
  size_bytes: number;
  /** One line on why somebody would want it, written by a person. */
  why: string;
  /** The manifest's date. Shown, because a recommendation is only as
   *  current as the list it came from. */
  generated: string;
  /** **Three-valued.** `true` fits the measured budget, `false` does not,
   *  and `null` means the machine could not be measured — Apple and
   *  DirectML report no VRAM. `null` must not render as either: greying
   *  the catalogue out on a Mac is wrong, and so is promising a fit
   *  nobody measured. */
  fits: boolean | null;
  /** In the tier the manifest aims at this machine — what first run would
   *  have offered. A different question from `fits`: a tiny model runs
   *  anywhere and is nobody's recommendation above 3 GB. */
  recommended: boolean;
  installed: boolean;
}

export interface ModelCatalogue {
  models: CatalogueModel[];
  /** Room for a chat model beside the embedder, or `null` when unmeasured.
   *  Never 0 — that would read as "no room" on a machine nobody measured. */
  budget_bytes: number | null;
  generated: string;
}

/** The catalogue, or an empty one.
 *
 *  **Never throws.** A browser that failed to open because the backend was
 *  slow is worse than one that opens empty and says so. */
export async function fetchModelCatalogue(): Promise<ModelCatalogue> {
  try {
    const response = await fetch(`${API_BASE}/providers/recommendations`);
    if (!response.ok) return { models: [], budget_bytes: null, generated: '' };
    const body = await response.json();
    return {
      models: Array.isArray(body.models) ? body.models : [],
      budget_bytes: typeof body.budget_bytes === 'number' ? body.budget_bytes : null,
      generated: String(body.generated ?? ''),
    };
  } catch {
    return { models: [], budget_bytes: null, generated: '' };
  }
}

/** `7.2 GB`. Decimal, because that is how every download is quoted — a
 *  provider's page, a data plan, a disk — and a user comparing Zaram's
 *  number against one of those should see the same figure. */
export function gigabytes(bytes: number): string {
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}
