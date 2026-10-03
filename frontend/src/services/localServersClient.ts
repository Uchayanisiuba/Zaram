/**
 * What is listening on this machine.
 *
 * Read by the browser pane's new tab. Nothing here is recalled, indexed or
 * sent anywhere — the shape of somebody's machine is exactly the kind of
 * fact rule 8 keeps out of an outbound query, and the only consumer is a
 * list of things to click.
 */
// Plain `fetch`. `installApiCredential` wraps `window.fetch` before the
// first paint and attaches the credential to same-origin requests, so a
// client that reached for its own wrapper would be a second place that has
// to remember.
const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface LocalServer {
  port: number;
  /** Always a loopback URL — the backend reports a server bound to every
   *  interface at 127.0.0.1, so this can never navigate off-machine. */
  url: string;
  name: string;
  pid: number;
  process: string;
  /** `zaram` — this install's own; `project` — one of the user's projects';
   *  `other` — anything else running. The pane shows the first two and
   *  collapses the third. */
  origin: 'zaram' | 'project' | 'other';
  projectId: string;
  webbish: boolean;
}

export interface LocalServerListing {
  servers: LocalServer[];
  /** How many fell into `other`, counted by the backend so the collapsed
   *  row does not re-derive the rule. */
  hidden: number;
}

/** Everything listening, or nothing.
 *
 *  **Never throws.** A new tab that failed to open because the process
 *  table was unreadable is a worse outcome than a new tab with an empty
 *  list, which is also what a machine with nothing running looks like. */
export async function fetchLocalServers(): Promise<LocalServerListing> {
  try {
    const response = await fetch(`${API_BASE}/local-servers`);
    if (!response.ok) return { servers: [], hidden: 0 };
    const body = await response.json();
    return {
      servers: Array.isArray(body.servers) ? body.servers : [],
      hidden: Number(body.hidden ?? 0),
    };
  } catch {
    return { servers: [], hidden: 0 };
  }
}
