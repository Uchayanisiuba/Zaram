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
