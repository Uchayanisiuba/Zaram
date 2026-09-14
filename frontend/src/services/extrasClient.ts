/**
 * The optional packs — what each turns on, what it costs, and getting one.
 *
 * `GET /extras` lists them; `POST /extras/{id}/install` streams the
 * installer's own lines as NDJSON, the same shape as a model pull. Pressing
 * the button is the consent (rule 7g), and the backend writes the download to
 * the egress log before the first byte.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';
const CLIENT_HEADER = { 'X-Zaram-Client': 'zaram-ui' } as const;

export interface Extra {
  id: string;
  name: string;
  enables: string[];
  sizeMb: number;
  measured: string;
  installed: boolean;
  /** Zaram has to be restarted before this pack takes effect. */
  restart: boolean;
}

export async function fetchExtras(): Promise<Extra[]> {
  const res = await fetch(`${API_BASE}/extras`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const body: { extras?: Array<Record<string, unknown>> } = await res.json();
  return (body.extras ?? []).map((e) => ({
    id: String(e.id),
    name: String(e.name),
    enables: Array.isArray(e.enables) ? e.enables.map(String) : [],
    sizeMb: Number(e.size_mb ?? 0),
    measured: String(e.measured ?? ''),
    installed: Boolean(e.installed),
    restart: Boolean(e.restart),
  }));
}

export type InstallEvent =
  | { stage: string }
  | { line: string }
  | { done: true; restart: boolean; seconds?: number }
  | { error: string };

/**
 * Get a pack, calling `onEvent` for each line as it arrives. Resolves with
 * the terminal event. A stream that ends without one is reported as an
 * error rather than a success — the installer being cut off is not the pack
 * being installed.
 */
export async function installExtra(
  id: string,
  onEvent: (event: InstallEvent) => void,
): Promise<InstallEvent> {
  const res = await fetch(`${API_BASE}/extras/${encodeURIComponent(id)}/install`, {
    method: 'POST',
    headers: CLIENT_HEADER,
  });
  if (!res.ok || !res.body) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep the status */
    }
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal: InstallEvent | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl = buffer.indexOf('\n');
    while (nl >= 0) {
      const raw = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (raw) {
        const event = JSON.parse(raw) as InstallEvent;
        onEvent(event);
        if ('done' in event || 'error' in event) terminal = event;
      }
      nl = buffer.indexOf('\n');
    }
  }
  return terminal ?? { error: 'The installer stopped without saying whether it finished.' };
}
