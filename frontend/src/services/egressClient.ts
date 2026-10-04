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

/**
 * *What* is leaving, as distinct from where it is going — rule 7j's second
 * dimension.
 *
 * `prompt` is what a plain host rule has always meant and is the default
 * everywhere. The others must be granted for a destination in their own right:
 * a chat message is a couple of kilobytes and a photograph is a few megabytes
 * of something far more personal, so connecting a provider for text is not
 * consent to send it a picture.
 */
export type EgressDataClass = 'prompt' | 'image' | 'spine';

export interface EgressPolicySnapshot {
  /** Always "deny" — stated by the backend rather than assumed here. */
  default: string;
  rules: Record<string, PolicyMode>;
  /**
   * host → class → mode, for the classes a host rule does not speak for.
   *
   * Its own field rather than a nesting of `rules`, matching the backend: that
   * shape is already rendered and parsed, and changing it quietly is how a
   * privacy pane comes to show nothing at all.
   */
  classRules: Record<string, Partial<Record<EgressDataClass, PolicyMode>>>;
  hostsSeen: string[];
  /** Hosts Zaram can draw at, contacted or not.
   *
   *  Listed so the image grant has somewhere to be given. A provider refused
   *  at `availability()` never reaches the gate, so it never enters the log
   *  and never appears in `hostsSeen` — which left the image refusal's own
   *  remedy pointing at a row that did not exist.
   *
   *  Listing is not permitting: these carry no rule and the default is still
   *  deny. `needsKey` is false for the one that needs no account at all. */
  canDrawAt: Array<{ host: string; what: string; needsKey: boolean }>;
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

/** What one step of one reply sent off this machine — `docs/PLAN.md` C2.
 *
 *  Every entry the gate wrote while that step ran carries its id
 *  (`core/egress/step_context.py`); a bare correlation id covers the whole
 *  reply. An empty list is a real answer: the gate logs every request, so a
 *  marked step with no entries sent nothing. Entries written outside any
 *  step are never matched, and the pane says nothing about them rather than
 *  guessing. */
export async function fetchEgressForStep(stepId: string, limit = 50): Promise<EgressEntry[]> {
  if (!stepId.trim()) return [];
  const page = await json<{ total: number; entries: Array<Record<string, unknown>> }>(
    `/egress?step_id=${encodeURIComponent(stepId)}&limit=${limit}`,
  );
  return page.entries.map((e) => ({
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
  }));
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
    classRules:
      (raw.class_rules as Record<string, Partial<Record<EgressDataClass, PolicyMode>>>) ?? {},
    hostsSeen: (raw.hosts_seen as string[]) ?? [],
    hostsWithoutARule: (raw.hosts_without_a_rule as string[]) ?? [],
    // An older backend does not send it, and an empty list is the honest
    // reading of that rather than a claim that Zaram can draw nowhere.
    canDrawAt: (Array.isArray(raw.can_draw_at) ? raw.can_draw_at : []).map(
      (d: Record<string, unknown>) => ({
        host: String(d.host ?? ''),
        what: String(d.what ?? ''),
        needsKey: Boolean(d.needs_key),
      }),
    ),
  };
}

/**
 * Set one destination's rule, for one class of thing.
 *
 * `dataClass` defaults to `prompt`, so every existing call site keeps its
 * exact behaviour — and the default is the least sensitive class rather than
 * the most, because a caller that does not say what it is sending must not be
 * able to grant permission for a photograph by omission.
 */
export async function setEgressPolicy(
  host: string,
  mode: PolicyMode,
  dataClass: EgressDataClass = 'prompt',
): Promise<void> {
  await json('/egress/policy', {
    method: 'PUT',
    body: JSON.stringify({ host, mode, data_class: dataClass }),
  });
}

/**
 * Remove a rule.
 *
 * Omitting `dataClass` forgets the destination entirely, every class with it.
 * Leaving an image grant behind after the host rule was removed would be a
 * permission outliving the decision that created it — and an invisible one,
 * since the list shows host rules.
 */
export async function forgetEgressPolicy(
  host: string,
  dataClass?: EgressDataClass,
): Promise<void> {
  const query = dataClass ? `?data_class=${encodeURIComponent(dataClass)}` : '';
  await json(`/egress/policy/${encodeURIComponent(host)}${query}`, { method: 'DELETE' });
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
  /** Rule 7j's second dimension: what kind of thing is leaving. */
  dataClass: string;
  /** A yes is kept as a standing rule for this host and class — the first
   *  picture to a provider the user already connected. Stated on the request,
   *  because a consent wider than the request has to be visible on it. */
  remember: boolean;
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
    dataClass: String(p.data_class ?? 'prompt'),
    remember: Boolean(p.remember),
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

/**
 * Record that something was fetched from a host on the user's behalf.
 *
 * **For requests `EgressGate` cannot see.** The gate intercepts what the
 * *backend* sends; a preview frame and the browser pane fetch directly
 * from the renderer and from Chromium, so nothing they do passes through
 * Python at all. Rule 3 — *every byte that leaves is logged* — stops being
 * satisfied by the backend alone the moment the product renders somebody
 * else's page. `CLAUDE.md` names this hole already, for a VRM's `uri`
 * fetches.
 *
 * It records; it does not decide. Whether the fetch may happen was settled
 * before this was called.
 *
 * **Never throws.** A log that will not write must not stop the person
 * seeing their page — the failure shows up in Activity as an absence,
 * which is the honest outcome of a backend that is not there.
 */
export async function recordBrowsed(host: string, path = '/'): Promise<void> {
  try {
    await fetch(`${API_BASE}/egress/browse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ host, path }),
    });
  } catch {
    /* see the note above */
  }
}
