/**
 * The session store, over HTTP.
 *
 * Rule 7d's *"session state and long-term memory are separate stores"* — and
 * this is the first one, which until 27 August 2026 did not exist. Closing the
 * window lost the conversation.
 *
 * **A transcript read back here is not memory.** It is what was said, restored
 * so a person can find it. Nothing in this file feeds recall, and nothing it
 * returns is a citation: facts live in the Spine with their own provenance and
 * their own correction loop, and conflating the two is the failure 7d was
 * written from.
 */
const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** Marks a request as coming from Zaram's own interface.
 *
 * Not a credential and never reasoned about as one -- CLAUDE.md is explicit:
 * *"`X-Zaram-Client` is a label, not a credential."* What it buys is that the
 * header is off the CORS safelist, so a browser must preflight a mutating
 * request and the preflight is checked against the backend's origin
 * allow-list. Deleting someone's transcripts from a page they happen to have
 * open should not be a simple request. */
const CLIENT_HEADER = { 'X-Zaram-Client': 'zaram-ui' } as const;

/** A failure with the backend's own sentence preserved.
 *
 * The refusals are written for a person -- "No such conversation", "A
 * conversation needs a title" -- and replacing them with "Request failed"
 * throws away the part that took the thought. */
export class ConversationError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ConversationError';
  }
}

async function readOrThrow(response: Response): Promise<unknown> {
  if (response.ok) return response.json();

  let detail = response.statusText || `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string' && body.detail) detail = body.detail;
  } catch {
    /* not JSON; keep the status text */
  }
  throw new ConversationError(detail, response.status);
}

async function get(path: string): Promise<unknown> {
  return readOrThrow(await fetch(`${API_BASE}${path}`));
}

async function send(
  path: string,
  method: 'POST' | 'PATCH' | 'DELETE',
  body?: unknown,
): Promise<unknown> {
  return readOrThrow(
    await fetch(`${API_BASE}${path}`, {
      method,
      headers: { ...CLIENT_HEADER, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
  );
}

/** One stored conversation, without its messages. */
export interface ConversationSummary {
  id: string;
  /** Taken from the first thing the user typed. Never generated, never asked. */
  title: string;
  /** Rule 7i. Empty is a real answer: asked outside any project. */
  projectId: string;
  createdAt: number;
  /** Last activity, which is what the list is ordered by — that is what a
   *  person means by "the one I was just in". Renaming does not count. */
  updatedAt: number;
  messageCount: number;
}

export interface StoredMessage {
  id: string;
  seq: number;
  role: 'user' | 'assistant';
  text: string;
  createdAt: number;
  /** Which model produced an assistant message, or '' where none was recorded.
   *
   *  Per message rather than per conversation, because the model can change
   *  between replies — that is the product's argument, not an edge case. */
  model: string;
  /** Where that model ran, or '' when it could not be placed.
   *
   *  Empty is not "local". `locality_of` answers `null` for a model it cannot
   *  resolve, and this inherits that: *"runs on this machine" would be a
   *  confident false claim on the one thing the user is most likely to check.* */
  locality: string;
}

export interface StoredConversation extends ConversationSummary {
  messages: StoredMessage[];
}

function toSummary(row: Record<string, unknown>): ConversationSummary {
  return {
    id: String(row.id),
    title: String(row.title ?? ''),
    projectId: String(row.project_id ?? ''),
    createdAt: Number(row.created_at ?? 0),
    updatedAt: Number(row.updated_at ?? 0),
    messageCount: Number(row.message_count ?? 0),
  };
}

function toMessage(row: Record<string, unknown>): StoredMessage {
  return {
    id: String(row.id),
    seq: Number(row.seq ?? 0),
    role: row.role === 'assistant' ? 'assistant' : 'user',
    text: String(row.text ?? ''),
    createdAt: Number(row.created_at ?? 0),
    model: String(row.model ?? ''),
    locality: String(row.locality ?? ''),
  };
}

/**
 * Conversations by last activity, most recent first.
 *
 * `projectId` omitted means every conversation; `''` means the ones belonging
 * to no project. **Two different questions**, and this signature keeps them
 * apart the way the backend does — collapsing them is how "show me everything"
 * quietly becomes "show me the unscoped ones".
 */
export async function fetchConversations(
  projectId?: string | null,
  limit = 50,
): Promise<ConversationSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (projectId !== undefined && projectId !== null) {
    params.set('project_id', projectId);
  }
  const rows = (await get(`/conversations?${params}`)) as Array<Record<string, unknown>>;
  return rows.map(toSummary);
}

/** One conversation and its whole transcript, in sequence. */
export async function fetchConversation(id: string): Promise<StoredConversation> {
  const row = (await get(`/conversations/${encodeURIComponent(id)}`)) as Record<
    string,
    unknown
  >;
  const messages = Array.isArray(row.messages) ? row.messages : [];
  return {
    ...toSummary(row),
    messages: (messages as Array<Record<string, unknown>>).map(toMessage),
  };
}

export async function startConversation(projectId = ''): Promise<ConversationSummary> {
  const row = (await send('/conversations', 'POST', { project_id: projectId })) as Record<
    string,
    unknown
  >;
  return toSummary(row);
}

export async function renameConversation(
  id: string,
  title: string,
): Promise<ConversationSummary> {
  const row = (await send(`/conversations/${encodeURIComponent(id)}`, 'PATCH', { title })) as Record<
    string,
    unknown
  >;
  return toSummary(row);
}

/**
 * Delete a transcript. Rule 4, applied to what was said.
 *
 * **Facts Zaram remembered from it are not touched**, and the caller is
 * expected to say so rather than let the user assume either way. They are
 * scoped, sourced and correctable in Memory in their own right; removing them
 * here would make a delete larger than the one that was asked for.
 */
export async function deleteConversation(id: string): Promise<{ note: string }> {
  const body = (await send(`/conversations/${encodeURIComponent(id)}`, 'DELETE')) as Record<
    string,
    unknown
  >;
  return { note: String(body.note ?? '') };
}
