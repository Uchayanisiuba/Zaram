/** Connecting GitHub, from Settings.
 *
 * The window never sees the token: it asks the backend for a code, shows it, and
 * polls. What the backend answers with is a name (`octocat`), never a credential.
 * See `backend/packs/github/api.py`.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface GithubStatus {
  /** The app is registered on this build, so there is something to connect to. */
  configured: boolean;
  connected: boolean;
  /** Signed in once, and the token has since run out. */
  expired: boolean;
  login: string;
  /** Epoch seconds, or null for a token that does not expire. */
  expires_at: number | null;
  /** Whether the token on disk is sealed to this Windows user; null when none is stored. */
  sealed: boolean | null;
  /** Where a person chooses which repositories Zaram may reach. */
  install_url: string;
  /** Where a person withdraws Zaram's access on GitHub's side. */
  manage_url: string;
}

export interface GithubDeviceCode {
  flow: string;
  user_code: string;
  verification_uri: string;
  interval: number;
  expires_in: number;
}

export type GithubPoll =
  | { state: 'pending'; interval?: number }
  | { state: 'expired' | 'denied' | 'error'; detail?: string; interval?: number }
  | ({ state: 'done' } & GithubStatus);

export interface GithubRepository {
  full_name: string;
  private: boolean;
  default_branch: string;
  can_push: boolean;
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
    throw new Error(detail || `GitHub: the backend answered ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchGithubStatus(): Promise<GithubStatus> {
  return readOrThrow(await fetch(`${API_BASE}/github/status`));
}

export async function startGithubConnect(): Promise<GithubDeviceCode> {
  return readOrThrow(await fetch(`${API_BASE}/github/connect`, { method: 'POST' }));
}

export async function pollGithubConnect(flow: string): Promise<GithubPoll> {
  return readOrThrow(
    await fetch(`${API_BASE}/github/connect/poll`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flow }),
    }),
  );
}

export async function disconnectGithub(): Promise<GithubStatus & { note: string }> {
  return readOrThrow(await fetch(`${API_BASE}/github/connect`, { method: 'DELETE' }));
}

export async function fetchGithubRepositories(): Promise<{
  repositories: GithubRepository[];
  install_url: string;
}> {
  return readOrThrow(await fetch(`${API_BASE}/github/repositories`));
}
