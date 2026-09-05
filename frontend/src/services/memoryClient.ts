/**
 * Memory transport — inspecting and forgetting stored facts.
 *
 * Separate from chatClient because these are ordinary request/response calls
 * rather than a stream, and because deletion is a different kind of operation
 * from conversation: it changes what Zaram knows.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface MemoryRecord {
  id: string;
  content: string;
  memory_type: string;
  created_at: number;
  last_accessed: number;
  access_count: number;
  importance: number;
  source: string;
  tags: string[];
  session_id: string | null;
  metadata: Record<string, unknown>;
  /** Id of the fact that replaced this one. Null while it still stands.
   *  A superseded fact is excluded from recall but stays on this screen,
   *  struck through — a correction the user cannot see is indistinguishable
   *  from a deletion, and the visible correction is the trust artifact. */
  superseded_by?: string | null;
  superseded_at?: number | null;
  pinned?: boolean;
  /** Set when this record replaced another. The inverse of superseded_by. */
  corrects?: string | null;
  /** Rule 7i: `global`, or `project:<id>`. One field, because facts move
   *  between the two and recall needs both at once — two stores would make a
   *  move a copy, and the correction loop would have to exist twice.
   *
   *  It is also the multiplayer boundary: project memory is shareable and
   *  global memory never is. That is why this is shown rather than kept
   *  internal — where a fact sits decides who could eventually see it. */
  scope?: string;
  /**
   * Where the curator stands on this fact — rule 7e's own vocabulary.
   *
   * `provisional` in and not yet used · `durable` recalled at least once ·
   * `fading` the next pass would forget it · `pinned` the user said keep it.
   *
   * Sent by the backend rather than derived here, because the thresholds
   * belong to the decay engine and a second copy of them in this file would
   * disagree with it the first time anyone tuned one.
   */
  standing?: 'provisional' | 'durable' | 'fading' | 'pinned';
}

/** The project a scope belongs to, or `null` for global. One place that knows
 *  the `project:` prefix, so a hand-built string cannot drift from it. */
export function scopeProjectId(scope: string | undefined): string | null {
  if (!scope || !scope.startsWith('project:')) return null;
  return scope.slice('project:'.length) || null;
}

/** Shared failure handling. The dev proxy answers 500 with an empty body when
 *  the backend is down, so a bare status is not a useful message. */
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
  if (res.status === 404) return new Error('That memory no longer exists.');
  return new Error(`${fallback} (${res.status})${detail ? `: ${detail}` : ''}`);
}

export interface MemoryListing {
  total: number;
  offset: number;
  limit: number;
  records: MemoryRecord[];
}

export interface MemoryStats {
  total_records: number;
  by_type: Record<string, number>;
  sessions: number;
  newest_at: number | null;
  storage_bytes: number;
  /** Null until the egress log exists. Null is not zero: an absent measurement
   *  must never be displayed as a measured zero. */
  bytes_left_device_today: number | null;
}

export async function fetchMemoryList(
  opts: { limit?: number; offset?: number; q?: string } = {},
  signal?: AbortSignal,
): Promise<MemoryListing> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  if (opts.q) params.set('q', opts.q);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory?${params}`, { signal });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not load memory');
  return (await res.json()) as MemoryListing;
}

export async function fetchMemoryStats(signal?: AbortSignal): Promise<MemoryStats> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/stats`, { signal });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not load memory stats');
  return (await res.json()) as MemoryStats;
}

export async function fetchMemory(
  id: string,
  signal?: AbortSignal,
): Promise<MemoryRecord> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/${encodeURIComponent(id)}`, { signal });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not load this source');
  return (await res.json()) as MemoryRecord;
}

export interface CorrectionResult {
  superseded_id: string;
  replacement_id: string;
  note: string;
}

/**
 * Correct a fact. Rule 4, in the form that keeps the record.
 *
 * Not an edit: the original is kept and marked superseded, and a new record
 * takes its place. Answers that depended on the old one change, because it is
 * dropped from the index — but the user can still see that Zaram had it wrong
 * and that they said so.
 */
export async function correctMemory(
  id: string,
  content: string,
  signal?: AbortSignal,
): Promise<CorrectionResult> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/${encodeURIComponent(id)}/correct`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      signal,
    });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (res.status === 409) {
    throw new Error('That fact has already been corrected.');
  }
  if (!res.ok) throw await failure(res, 'Could not correct this fact');
  return (await res.json()) as CorrectionResult;
}

/**
 * Keep something the user picked out of a conversation.
 *
 * **An override on the automatic capture, never a replacement for it.** The
 * engine still decides what enters on its own and `SpineMaintenance` still
 * decays what is never used — rule 7e is that the system answers from
 * behaviour rather than asking. This is the other half of the pair rule 7b
 * already describes ("Don't remember this" on a file card, *"an override,
 * never a gate"*), pointing the other way, for the cases where a heuristic is
 * not good enough: a rate, a term, a decision already taken.
 *
 * `origin` must say whose words these are. Saved off a Zaram reply it is
 * `generated`, and recall ranks it below a user document saying the same thing
 * — rule 7b, and the reason Zaram does not end up citing itself.
 */
export async function rememberText(
  text: string,
  options: { projectId?: string | null; origin?: 'conversation' | 'generated' } = {},
  signal?: AbortSignal,
): Promise<{ id: string; note: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        project_id: options.projectId ?? null,
        origin: options.origin ?? 'conversation',
      }),
      signal,
    });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not keep that');
  return (await res.json()) as { id: string; note: string };
}

/** Pin a fact so recall prefers it over merely-recent ones. */
export async function pinMemory(
  id: string,
  pinned: boolean,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/${encodeURIComponent(id)}/pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned }),
      signal,
    });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not pin this fact');
}

/** Move a fact between global and a project, or between two projects.
 *
 *  `''` is global — about the user rather than about the work. Rule 7e keeps
 *  promotion evidence-driven, so Zaram asks when a fact has been recalled
 *  across several projects; this is where that answer goes, and the manual
 *  override for when it never asks.
 *
 *  The backend refuses an unknown project. A fact under a scope no project
 *  points at could not be found to be corrected or deleted, which is rule 4
 *  broken by a spelling mistake. */
export async function setMemoryScope(
  id: string,
  projectId: string,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/${encodeURIComponent(id)}/scope`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId }),
      signal,
    });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not move this fact');
}

export async function deleteMemory(id: string, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/memory/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      signal,
    });
  } catch {
    throw new Error('Could not reach the Zaram backend.');
  }
  if (!res.ok) throw await failure(res, 'Could not delete this memory');
}
