/** Updates, from the window.
 *
 * The backend finds a newer build and fetches it through the egress gate
 * (`backend/core/updates.py`); the desktop shell runs it. The window never sees a
 * file path and never names one -- `install` takes no arguments.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface UpdateRelease {
  tag: string;
  /** The release page on GitHub, for "what's new". */
  page: string;
  installer: { name: string; url: string; size: number };
}

export type UpdatePhase = 'idle' | 'checking' | 'available' | 'up_to_date' | 'downloading' | 'ready';

export interface UpdateStatus {
  /** The release this is, or null for a build that was never stamped. */
  current: string | null;
  known: boolean;
  /** Yes, no, or not asked yet. */
  checks: boolean | null;
  last_checked: number | null;
  phase: UpdatePhase;
  latest: UpdateRelease | null;
  progress: { done: number; total: number };
  error: string;
  /** Downloaded, checked, and waiting to be run. */
  ready: boolean;
  can_install: boolean;
  /** Why it cannot be installed from here, or ''. */
  manual_reason: string;
  release_page: string;
  /** Set when saying yes could not allow the hosts (a block the person set). */
  note?: string;
}

async function readOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = typeof body?.detail === 'string' ? body.detail : '';
    } catch {
      // not JSON; the status says enough
    }
    throw new Error(detail || `Updates: the backend answered ${response.status}`);
  }
  return (await response.json()) as T;
}

const json = { 'Content-Type': 'application/json' };

export async function fetchUpdateStatus(): Promise<UpdateStatus> {
  return readOrThrow(await fetch(`${API_BASE}/updates/status`));
}

export async function setUpdateChecks(checks: boolean): Promise<UpdateStatus> {
  return readOrThrow(
    await fetch(`${API_BASE}/updates/settings`, { method: 'PUT', headers: json, body: JSON.stringify({ checks }) }),
  );
}

/** `force` is the person pressing the button: an act, not held back by the setting. */
export async function checkForUpdates(force: boolean): Promise<UpdateStatus> {
  return readOrThrow(
    await fetch(`${API_BASE}/updates/check`, { method: 'POST', headers: json, body: JSON.stringify({ force }) }),
  );
}

export async function startUpdateDownload(): Promise<UpdateStatus> {
  return readOrThrow(await fetch(`${API_BASE}/updates/download`, { method: 'POST' }));
}

/** Hands the downloaded installer to the desktop shell, which closes Zaram and runs it. */
export async function installUpdate(): Promise<{ ok: boolean; reason?: string }> {
  const install = window.zaram?.updates?.install;
  if (typeof install !== 'function') {
    return { ok: false, reason: 'Installing an update only works in the desktop app.' };
  }
  return install();
}
