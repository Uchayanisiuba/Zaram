/**
 * Ingest transport — folders in, and an honest account of what came out.
 *
 * The field names are the backend's, for the reason written in
 * `artifactsClient.ts`: a mapping layer is a second vocabulary and a place for
 * the two to disagree quietly.
 *
 * The status vocabulary is the interesting part. There is no boolean `ok`,
 * because "read it" and "opened it and got nothing" and "could not open it"
 * have three different remedies, and collapsing them is how a scanned PDF gets
 * reported as a success and silently degrades every answer that touches it.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** Exactly one applies to each file. */
export type IngestStatus =
  | 'indexed'
  | 'sparse'
  | 'empty'
  | 'failed'
  | 'unsupported';

/** The three the user has to be shown. `unsupported` is not a problem — the
 *  file simply is not a document — and `indexed` is the happy path. */
export const PROBLEM_STATUSES: IngestStatus[] = ['sparse', 'empty', 'failed'];

export function isProblem(status: IngestStatus): boolean {
  return PROBLEM_STATUSES.includes(status);
}

export const STATUS_LABELS: Record<IngestStatus, string> = {
  indexed: 'Indexed',
  sparse: 'Almost nothing',
  empty: 'Nothing at all',
  failed: "Couldn't read",
  unsupported: 'Not a document',
};

export interface IngestOutcome {
  id: string;
  source_id: string;
  path: string;
  name: string;
  status: IngestStatus;
  parser: string;
  chars: number;
  pages: number;
  fact_ids: string[];
  /** What happened, in a sentence a person can act on. Empty when fine. */
  reason: string;
  /** The fix and what it costs. Empty when there isn't one. */
  remedy: string;
  seconds: number;
}

export interface IngestSource {
  id: string;
  root: string;
  name: string;
  added_at: number;
  scanned_at: number;
  seconds: number;
  policy: 'local_only' | 'cloud_allowed';
  notified: boolean;
  counts: Partial<Record<IngestStatus, number>>;
  total: number;
  problems: number;
  /** True when this source is Zaram's own uploads directory — the files in it
   *  are copies Zaram wrote when documents were dropped or pasted, so
   *  withdrawing it deletes them. A scanned folder holds the user's originals
   *  and withdrawing it never touches the disk. The backend answers this; it is
   *  deliberately not inferred from the folder's name. */
  staged: boolean;
}

/** One event from the ingest stream. Progress is per file, never a percentage:
 *  a bar stuck at 90% says nothing about which document is missing. */
export type IngestEvent =
  | { type: 'start'; root: string; total: number }
  | ({ type: 'file'; index: number; total: number } & Omit<IngestOutcome, 'id' | 'source_id'>)
  | { type: 'done'; source_id: string; root: string; total: number; problems: number }
  | { type: 'error'; message: string };

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchSources(): Promise<IngestSource[]> {
  const data = await json<{ sources: IngestSource[] }>('/ingest/sources');
  return data.sources;
}

export async function fetchOutcomes(
  sourceId?: string,
  problemsOnly = false,
): Promise<IngestOutcome[]> {
  const params = new URLSearchParams();
  if (sourceId) params.set('source_id', sourceId);
  if (problemsOnly) params.set('problems_only', 'true');
  const suffix = params.toString() ? `?${params}` : '';
  const data = await json<{ outcomes: IngestOutcome[] }>(`/ingest/outcomes${suffix}`);
  return data.outcomes;
}

export async function retryOutcome(outcomeId: string): Promise<IngestOutcome> {
  return json<IngestOutcome>(`/ingest/outcomes/${outcomeId}/retry`, { method: 'POST' });
}

export async function setSourcePolicy(
  sourceId: string,
  policy: IngestSource['policy'],
): Promise<void> {
  await json(`/ingest/sources/${sourceId}/policy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ policy }),
  });
}

export async function removeSource(
  sourceId: string,
): Promise<{ facts_removed: number; facts_recorded: number; files_deleted: number }> {
  return json(`/ingest/sources/${sourceId}`, { method: 'DELETE' });
}

/**
 * Index a folder, calling `onEvent` as each file finishes.
 *
 * The three ways in — a folder, dropped files, pasted text — emit one NDJSON
 * vocabulary and share `consume` below. That is the backend's decision as much
 * as this file's: a second event shape would be a second set of split-chunk
 * bugs, and this one has already been through them.
 */
export async function ingestFolder(
  path: string,
  onEvent: (event: IngestEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
    signal,
  });
  await consume(response, onEvent);
}

/**
 * Dropped, chosen or pasted files.
 *
 * No `Content-Type` header: the browser has to set it, because a multipart
 * body is worthless without the boundary it generates, and naming the type by
 * hand omits it.
 */
export async function uploadFiles(
  files: File[],
  onEvent: (event: IngestEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const form = new FormData();
  for (const file of files) form.append('files', file, file.name);

  const response = await fetch(`${API_BASE}/ingest/upload`, {
    method: 'POST',
    body: form,
    signal,
  });
  await consume(response, onEvent);
}

/** Pasted text. Written as a file and read by the same parser as any other —
 *  see the route, which explains why it does not go straight into the Spine. */
export async function ingestText(
  text: string,
  name: string,
  onEvent: (event: IngestEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/ingest/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, name }),
    signal,
  });
  await consume(response, onEvent);
}

/**
 * Read one NDJSON ingest stream, whatever produced it.
 *
 * Shared rather than repeated per route, because the two cases that are easy
 * to get wrong only appear under load: a JSON object split across chunk
 * boundaries, and a multi-byte character split mid-sequence. Three copies of
 * this would be three chances to fix only one of them.
 *
 * A refusal carries the backend's own sentence — "that file is larger than
 * 100 MB", "there was nothing in that" — rather than a status code, because
 * the status code is not something the user can act on.
 */
async function consume(
  response: Response,
  onEvent: (event: IngestEvent) => void,
): Promise<void> {
  if (!response.ok || !response.body) {
    let detail = '';
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? '';
    } catch {
      /* not every failure has a body */
    }
    throw new Error(detail || `Ingest failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newline = buffer.indexOf('\n');
    while (newline !== -1) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) {
        try {
          onEvent(JSON.parse(line) as IngestEvent);
        } catch {
          // A malformed line is not worth ending the ingest over; the `done`
          // event carries the authoritative totals either way.
        }
      }
      newline = buffer.indexOf('\n');
    }
  }

  const tail = buffer.trim();
  if (tail) {
    try {
      onEvent(JSON.parse(tail) as IngestEvent);
    } catch {
      /* ignore */
    }
  }
}
