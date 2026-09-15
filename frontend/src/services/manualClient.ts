/**
 * Zaram's own manual — the pages under Settings → Help, and the same pages
 * the Zaram domain recalls from. Read-only; nothing here writes.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface ManualPage {
  slug: string;
  title: string;
  order: number;
}

export interface ManualIndex {
  pages: ManualPage[];
  /** Fingerprint of the pages shipped with this build. */
  version: string;
  /** Fingerprint of the pages the Zaram domain holds, or null before the
   *  first index. When it differs from `version`, the domain is behind. */
  indexedVersion: string | null;
}

export async function fetchManual(): Promise<ManualIndex> {
  const res = await fetch(`${API_BASE}/manual`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const body: { pages?: ManualPage[]; version?: string; indexed_version?: string | null } = await res.json();
  return {
    pages: (body.pages ?? []).map((p) => ({ slug: String(p.slug), title: String(p.title), order: Number(p.order) })),
    version: String(body.version ?? ''),
    indexedVersion: body.indexed_version ?? null,
  };
}

export async function fetchManualPage(slug: string): Promise<string> {
  const res = await fetch(`${API_BASE}/manual/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const body: { markdown?: string } = await res.json();
  return body.markdown ?? '';
}

/** Where a picture named in a page is served from; the backend confines the
 *  name to the manual's own folder. */
export function manualAssetUrl(path: string): string {
  return path.startsWith('/manual/assets/') ? `${API_BASE}${path}` : path;
}
