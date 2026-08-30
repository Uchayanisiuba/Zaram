/**
 * Artifacts transport — what the user has made.
 *
 * Backs the Work surface and, later, the in-conversation file cards. Both read
 * the same records, because they are the same thing shown twice.
 *
 * The field names here are the backend's, deliberately. The shape that used to
 * live in `data/sampleArtifacts` was a first draft written before the model
 * existed, and it had drifted — `projectId` against `project_id`, a nested
 * `conversation` object against two flat fields, and a `previewText` with
 * nothing behind it. Renaming on the way in would mean two vocabularies for one
 * record and a mapping layer where they disagree quietly. The model won.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** The kinds the backend can produce.
 *
 *  `artifacts/contracts.py` says outright that divergence between the two is a
 *  bug rather than a variation, and it had diverged: `deck` shipped on the
 *  backend and never arrived here, so a slide deck's card had no icon and no
 *  colour — `Record<ArtifactKind, …>` cannot catch a member it does not know
 *  exists. `cv` is added with it.
 */
export type ArtifactKind =
  | 'invoice'
  | 'document'
  | 'spreadsheet'
  | 'chart'
  | 'deck'
  | 'cv';

export const KIND_LABELS: Record<ArtifactKind, string> = {
  invoice: 'Invoices',
  document: 'Documents',
  spreadsheet: 'Spreadsheets',
  chart: 'Charts',
  deck: 'Decks',
  cv: 'CVs',
};

/** Where an artifact drew on. Mirrors `ChatSource` in chatClient — provenance
 *  is one idea, not two. */
export interface ArtifactSource {
  kind: string;
  url: string | null;
  title: string | null;
}

/** One sentence in the document, and the fact it came from. Finer-grained than
 *  a source: sources say what the document drew on, claims say which sentence
 *  came from where. */
export interface ArtifactClaim {
  id: string;
  source_id: string;
  excerpt: string;
  source_excerpt: string;
  source_revision: string | null;
  verified_at: number | null;
}

export interface Artifact {
  id: string;
  filename: string;
  kind: ArtifactKind;
  project_id: string;
  /** `generated` for everything Zaram makes. Rule 7b — recall uses this to
   *  deprioritise Zaram's own restatements where a user source says the same. */
  origin: string;
  /** Epoch seconds. */
  created_at: number;
  size_bytes: number;
  path: string | null;
  /** The conversation that produced it. Work exists to hold output *with* the
   *  conversation that made it — without this it is a file browser. */
  conversation_id: string;
  conversation_title: string;
  sources: ArtifactSource[];
  claims: ArtifactClaim[];
  indexed: boolean;
  /** The "Don't remember this" override. `null` means the user has not decided,
   *  which is not the same as `false`. */
  remember_override: boolean | null;
  /** Whether the file is still where it was written. The record can outlive the
   *  file — the user may have moved it — and the download button has to know
   *  the difference between "no such document" and "not where we left it". */
  exists: boolean;
  /** Only present when fetched with `includeHtml`. The source of truth for
   *  every export, and what the preview renders. */
  html?: string;
}

export interface ArtifactListing {
  total: number;
  offset: number;
  limit: number;
  artifacts: Artifact[];
}

export interface ArtifactProject {
  id: string;
  count: number;
}

export interface ExportFormat {
  extension: string;
  label: string;
  available: boolean;
  /** Why it cannot run here. Empty when available. */
  reason: string;
  /** What would fix it. Shown next to the greyed-out option rather than hidden,
   *  because a capability that is off silently reads as a broken product. */
  remedy: string;
}

/** Shared failure handling, same shape as memoryClient. The dev proxy answers
 *  500 with an empty body when the backend is down, so a bare status is not a
 *  useful message. */
async function failure(res: Response, fallback: string): Promise<Error> {
  let detail = '';
  try {
    detail = (await res.text()).slice(0, 300);
  } catch {
    /* body unreadable */
  }
  if (!detail.trim() && [500, 502, 503, 504].includes(res.status)) {
    return new Error('Could not reach the Zaram backend.');
  }
  if (res.status === 404) return new Error('That artifact no longer exists.');
  if (res.status === 410) {
    return new Error('The record is here, but the file is no longer at its path.');
  }
  return new Error(`${fallback} (${res.status})${detail ? `: ${detail}` : ''}`);
}

export async function listArtifacts(
  options: { projectId?: string; kind?: string; conversationId?: string } = {},
): Promise<ArtifactListing> {
  const query = new URLSearchParams();
  if (options.projectId) query.set('project_id', options.projectId);
  if (options.kind) query.set('kind', options.kind);
  if (options.conversationId) query.set('conversation_id', options.conversationId);

  const suffix = query.toString() ? `?${query}` : '';
  const res = await fetch(`${API_BASE}/artifacts${suffix}`);
  if (!res.ok) throw await failure(res, 'Could not load your work');
  return res.json();
}

export async function getArtifact(id: string, includeHtml = false): Promise<Artifact> {
  const res = await fetch(
    `${API_BASE}/artifacts/${encodeURIComponent(id)}${includeHtml ? '?include_html=true' : ''}`,
  );
  if (!res.ok) throw await failure(res, 'Could not load that artifact');
  return res.json();
}

export async function listProjects(): Promise<ArtifactProject[]> {
  const res = await fetch(`${API_BASE}/artifacts/projects`);
  if (!res.ok) throw await failure(res, 'Could not load projects');
  return (await res.json()).projects;
}

export async function listFormats(): Promise<ExportFormat[]> {
  const res = await fetch(`${API_BASE}/artifacts/formats`);
  if (!res.ok) throw await failure(res, 'Could not load export formats');
  return (await res.json()).formats;
}

/** The URL the browser downloads from. A plain link rather than a fetch-and-
 *  blob, so the browser's own download UI handles it and a large file does not
 *  sit in memory first. */
export function downloadUrl(id: string): string {
  return `${API_BASE}/artifacts/${encodeURIComponent(id)}/download`;
}

/** Move a file into a project, out of one, or between two.
 *
 *  `''` is the destination for "no project" — the same value a file is born
 *  with, so leaving a project restores its original state rather than inventing
 *  a third one. The backend refuses a project it has never heard of, which is
 *  what stops a typo creating a group that cannot be renamed or deleted.
 *
 *  Nothing moves on disk. A project is a label, not a folder, and the output
 *  directory is deliberately flat. */
export async function assignToProject(id: string, projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/artifacts/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) throw await failure(res, 'Could not move that file');
}

export async function setRemember(id: string, remember: boolean | null): Promise<void> {
  const res = await fetch(`${API_BASE}/artifacts/${encodeURIComponent(id)}/remember`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ remember }),
  });
  if (!res.ok) throw await failure(res, 'Could not save that preference');
}
