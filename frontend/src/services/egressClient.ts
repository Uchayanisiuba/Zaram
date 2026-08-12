/**
 * Egress client — reading the record of what left this machine.
 *
 * Rule 3 says every byte that leaves is logged. A log nobody can read satisfies
 * the letter of that and none of the point, so this is the transport that makes
 * it legible.
 *
 * One deliberate choice runs through the types below: `literalText` is carried
 * separately from `url` and `body` even though it is derived from them. The
 * interface's job is to show the user the exact text that left, and keeping that
 * as its own field means a view cannot accidentally render a summary and call it
 * the record.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What happened to a request. A denial is as worth showing as a send. */
export type EgressDecision = 'allowed' | 'denied' | 'cancelled';

export interface EgressEntry {
  id: string;
  /** Unix seconds. */
  at: number;
  /** "request", or "retention" for a record that entries were pruned. */
  kind: string;
  host: string;
  method: string;
  url: string;
  body: string | null;
  /** Exactly what went on the wire. Show this, not a summary of it. */
  literalText: string;
  bytes: number;
  decision: EgressDecision | string;
  /** Plain language: why this was allowed, refused or cancelled. */
  reason: string;
  /** Which part of Zaram asked — e.g. "wikipedia", "internet.rss". */
  source: string;
  meta: Record<string, unknown>;
}

export interface EgressPage {
  total: number;
  entries: EgressEntry[];
}

export interface EgressIntegrity {
  intact: boolean;
  entries: number;
  detail: string;
  /** Present when intact. States what the check does *not* prove. */
  caveat?: string;
  atRow?: number;
  entryId?: string | null;
}

export type PolicyMode = 'allow' | 'ask' | 'deny';

export interface EgressPolicySnapshot {
  /** Always "deny" — stated by the backend rather than assumed here. */
  default: string;
  rules: Record<string, PolicyMode>;
  hostsSeen: string[];
  /** Contacted at least once but never ruled on. What the pane should offer. */
  hostsWithoutARule: string[];
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.text()).slice(0, 300);
    } catch {
      /* body unreadable; the status will have to do */
    }
    throw new Error(
      detail
        ? `${res.status} ${res.statusText}: ${detail}`
        : `${res.status} ${res.statusText}`,
    );
  }
  return (await res.json()) as T;
}

export async function fetchEgressLog(limit = 100, offset = 0): Promise<EgressPage> {
  const raw = await json<{
    total: number;
    entries: Array<Record<string, unknown>>;
  }>(`/egress?limit=${limit}&offset=${offset}`);

  return {
    total: raw.total,
    entries: raw.entries.map((e) => ({
      id: String(e.id),
      at: Number(e.at),
      kind: String(e.kind),
      host: String(e.host),
      method: String(e.method),
      url: String(e.url),
      body: e.body == null ? null : String(e.body),
      literalText: String(e.literal_text ?? e.url),
      bytes: Number(e.bytes ?? 0),
      decision: String(e.decision),
      reason: String(e.reason),
      source: String(e.source),
      meta: (e.meta as Record<string, unknown>) ?? {},
    })),
  };
}

export async function verifyEgressLog(): Promise<EgressIntegrity> {
  const raw = await json<Record<string, unknown>>('/egress/verify');
  return {
    intact: Boolean(raw.intact),
    entries: Number(raw.entries ?? 0),
    detail: String(raw.detail ?? ''),
    caveat: raw.caveat == null ? undefined : String(raw.caveat),
    atRow: raw.at_row == null ? undefined : Number(raw.at_row),
    entryId: raw.entry_id == null ? null : String(raw.entry_id),
  };
}

export async function fetchEgressPolicy(): Promise<EgressPolicySnapshot> {
  const raw = await json<Record<string, unknown>>('/egress/policy');
  return {
    default: String(raw.default ?? 'deny'),
    rules: (raw.rules as Record<string, PolicyMode>) ?? {},
    hostsSeen: (raw.hosts_seen as string[]) ?? [],
    hostsWithoutARule: (raw.hosts_without_a_rule as string[]) ?? [],
  };
}

export async function setEgressPolicy(host: string, mode: PolicyMode): Promise<void> {
  await json('/egress/policy', {
    method: 'PUT',
    body: JSON.stringify({ host, mode }),
  });
}

export async function forgetEgressPolicy(host: string): Promise<void> {
  await json(`/egress/policy/${encodeURIComponent(host)}`, { method: 'DELETE' });
}

/**
 * A request parked inside the gate, waiting for the user to answer.
 *
 * The thread that produced this is blocked on it: the model is not thinking,
 * the reply is not streaming, and nothing has been logged or sent. That is the
 * whole design — the decision happens before the bytes move, not after.
 */
export interface PendingEgress {
  id: string;
  host: string;
  method: string;
  url: string;
  body: string | null;
  /** Exactly what would go on the wire. The dialog shows this, not a summary. */
  literalText: string;
  byteCount: number;
  /** Which part of Zaram is asking — "chat", a tool name. */
  source: string;
  /** Unix seconds, for ordering when more than one is waiting. */
  createdAt: number;
}

export async function fetchPendingEgress(): Promise<PendingEgress[]> {
  const raw = await json<{ pending: Array<Record<string, unknown>> }>('/egress/pending');
  return (raw.pending ?? []).map((p) => ({
    id: String(p.id),
    host: String(p.host),
    method: String(p.method),
    url: String(p.url),
    body: p.body == null ? null : String(p.body),
    literalText: String(p.literal_text ?? p.url),
    byteCount: Number(p.byte_count ?? 0),
    source: String(p.source ?? 'unknown'),
    createdAt: Number(p.created_at ?? 0),
  }));
}

/**
 * Answer a waiting request.
 *
 * `body` is what the user approved after editing — omit it to send the request
 * unchanged. Omitting is meaningfully different from passing the same string
 * back: an unedited body keeps its original bytes, while an edit is
 * re-serialised, and the two are only guaranteed identical for text that
 * survives a round trip.
 *
 * Resolves `false` when there was nothing left to answer, which is the normal
 * outcome of a double-click or of a dialog that sat open past the timeout. It
 * is not an error worth showing — the request was already refused.
 */
export async function decidePendingEgress(
  id: string,
  approved: boolean,
  body?: string,
): Promise<boolean> {
  const res = await fetch(`${API_BASE}/egress/pending/${encodeURIComponent(id)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, body: body ?? null }),
  });
  if (res.status === 404) return false;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return true;
}

export interface RetentionResult {
  removed: number;
  remaining: number;
  days: number;
  note: string;
}

/** `days` of 0 keeps everything. */
export async function applyRetention(days: number): Promise<RetentionResult> {
  return json<RetentionResult>('/egress/retention', {
    method: 'POST',
    body: JSON.stringify({ days }),
  });
}
