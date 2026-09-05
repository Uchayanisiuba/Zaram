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
  | 'cv'
  | 'image';

export const KIND_LABELS: Record<ArtifactKind, string> = {
  invoice: 'Invoices',
  document: 'Documents',
  spreadsheet: 'Spreadsheets',
  chart: 'Charts',
  deck: 'Decks',
  cv: 'CVs',
  image: 'Images',
};

/** Kinds whose file *is* a picture, so a thumbnail says more than a filename.
 *
 *  Both of these embed their PNG in their HTML as a data URI and export
 *  through the same exporter — see `artifacts/export/chart.py`. They are still
 *  two kinds, because a chart is derived from numbers the user has and always
 *  carries the data table that makes it checkable, while an image is drawn
 *  from a description and has nothing behind it to check.
 *
 *  Used for density rather than for behaviour: Work draws these as a grid of
 *  thumbnails and everything else as rows, because a page of pictures is
 *  browsable in a way a page of filenames is not. */
export const PICTORIAL_KINDS: ReadonlySet<ArtifactKind> = new Set<ArtifactKind>([
  'image',
  'chart',
]);

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
  /** Waiting to be kept, rather than saved.
   *
   *  Images are generated several at a time and most of them are discards,
   *  so they land in a staging area and reach the output folder only when
   *  the user presses Save. Documents are never staged — an invoice is asked
   *  for once, on purpose, and confirming it is the dialog rule 7h refuses.
   *
   *  Derived on the server from the directory the file is in rather than
   *  stored beside it, so it cannot disagree with where the file actually
   *  is. */
  staged: boolean;
  /** When a staged file clears itself, as epoch seconds, or `null`.
   *
   *  Rendered on the card, because a retention window the user cannot see is
   *  indistinguishable from a product that loses things. `null` for anything
   *  kept, and for a staged file whose bytes have already gone. */
  expires_at: number | null;
  /** Only present when fetched with `includeHtml`. The source of truth for
   *  every export, and what the preview renders. */
  html?: string;
  /** Whether this artifact was **the point of the request**.
   *
   *  Transport-only, like `exists` and `download_url` — a property of the
   *  exchange rather than of the file, so it is never stored and never
   *  returned by `/artifacts`.
   *
   *  It exists so the preview can open itself for "draw me a logo" and stay
   *  shut for an artifact that appeared alongside a reply. An overlay arriving
   *  unbidden mid-conversation is an interruption rather than a convenience,
   *  and the difference between the two is exactly this: did the user ask for
   *  the thing that just appeared. */
  deliberate?: boolean;
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

/** The backend path a file is served from.
 *
 *  **Not something to put in an `href` or an `img src` any more**, and that is
 *  a change rather than a preference. This used to be handed straight to an
 *  `<a download>`, with the reasoning that the browser's own download UI
 *  should handle it and a large file should not sit in memory first. Both
 *  halves of that were right and both stopped being available on 28 August
 *  2026, when `RequireApiSecret` began authenticating every request against a
 *  per-launch credential.
 *
 *  That credential is attached by a wrapper around `fetch`, and **a link is
 *  not a fetch**. Neither is an `<img>`. So a plain anchor navigates without
 *  the header and the backend answers 401 — measured against the running
 *  backend, 3 September 2026: `/health` with no credential returns 401, and
 *  the download route is behind the same middleware with nothing exempt.
 *
 *  Kept exported because it is still the right *path*, and it is what the
 *  functions below fetch. Nothing should render it. */
export function downloadUrl(id: string): string {
  return `${API_BASE}/artifacts/${encodeURIComponent(id)}/download`;
}

async function fetchArtifactFile(id: string): Promise<Blob> {
  // Goes through `fetch`, so the credential wrapper attaches the header. This
  // is the whole reason the plain link had to go.
  const res = await fetch(downloadUrl(id));
  if (!res.ok) throw await failure(res, 'Could not download that file');
  return res.blob();
}

/** Save an artifact to disk, credential and all.
 *
 *  Fetch, object URL, synthesised click, revoke. More machinery than an
 *  anchor, and the anchor is not an option: see `downloadUrl`. The blob is
 *  released on the next tick rather than immediately, because Chrome cancels a
 *  download whose URL is revoked before it has started reading it. */
export async function downloadArtifact(id: string, filename: string): Promise<void> {
  const blob = await fetchArtifactFile(id);
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
}

/** An object URL for an artifact that *is* a picture, for a thumbnail.
 *
 *  Same reason as above — an `<img src="/artifacts/…">` never carries the
 *  credential — and the caller is responsible for revoking what it gets back
 *  when the element goes away.
 *
 *  Deliberately not cached here. A cache would have to decide when to release
 *  its URLs, and an object URL that is never revoked is a copy of the file
 *  held in memory for the life of the tab. The component that renders the
 *  thumbnail knows when it unmounts; this module does not. */
export async function artifactImageUrl(id: string): Promise<string> {
  return URL.createObjectURL(await fetchArtifactFile(id));
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

/** Save a staged image to the output folder, for good.
 *
 *  Returns the updated artifact rather than nothing, because the filename can
 *  change on the way there: the output folder increments on collision, so a
 *  staged `blue.png` becomes `blue-2.png` if one is already sitting there. A
 *  card that went on showing the old name would be naming a file nobody has.
 *
 *  Safe to press twice. The server treats a second press as the first, because
 *  that is what the user means by it.
 *
 *  The same shape as `POST /chat/attachments/{id}/keep`, which exists for the
 *  same reason one surface along: looking at something is not deciding to keep
 *  it forever. */
export async function keepArtifact(id: string): Promise<Artifact> {
  const res = await fetch(`${API_BASE}/artifacts/${encodeURIComponent(id)}/keep`, {
    method: 'POST',
  });
  if (!res.ok) throw await failure(res, 'Could not save that file');
  return (await res.json()).artifact as Artifact;
}

export async function setRemember(id: string, remember: boolean | null): Promise<void> {
  const res = await fetch(`${API_BASE}/artifacts/${encodeURIComponent(id)}/remember`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ remember }),
  });
  if (!res.ok) throw await failure(res, 'Could not save that preference');
}
