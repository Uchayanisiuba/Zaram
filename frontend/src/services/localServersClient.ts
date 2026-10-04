/**
 * What Zaram has running.
 *
 * Read by the browser pane's new tab. **Only what Zaram started or
 * opened** — this listed everything on the machine for a day, and of 46
 * listeners on the maintainer's own machine 44 were Discord, OneDrive,
 * Epic Games and svchost. The narrowed list is both quieter and more
 * honest: it is what Zaram is responsible for.
 *
 * Nothing here is recalled, indexed or sent anywhere.
 */

// Plain `fetch`. `installApiCredential` wraps `window.fetch` before the
// first paint and attaches the credential to same-origin requests, so a
// client that reached for its own wrapper would be a second place that has
// to remember.
const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface LocalServer {
  /** Always a loopback URL. The backend drops anything else, so this can
   *  never navigate off-machine. */
  url: string;
  /** The project's name where Zaram knows it, otherwise the folder's. */
  name: string;
  /** `zaram` — this install's own backend; `project` — a dev server Zaram
   *  started for one of the user's projects. */
  origin: 'zaram' | 'project';
  pid: number;
  projectId: string;
  /** Which runner started it (`npm run dev`, `vite`), or `''` for Zaram's
   *  own backend. The quiet second line on the row. */
  runner: string;
  port: number;
}

export interface LocalServerListing {
  servers: LocalServer[];
}

/** Everything Zaram has running, or nothing.
 *
 *  **Never throws.** A new tab that failed to open because the backend was
 *  slow is a worse outcome than a new tab with an empty list, which is
 *  also what "Zaram has started nothing yet" looks like. */
export async function fetchLocalServers(): Promise<LocalServerListing> {
  try {
    const response = await fetch(`${API_BASE}/local-servers`);
    if (!response.ok) return { servers: [] };
    const body = await response.json();
    return { servers: Array.isArray(body.servers) ? body.servers : [] };
  } catch {
    return { servers: [] };
  }
}
