/**
 * Pairing transport — the other assistants that hold Zaram's memory.
 *
 * `core/pairing.py` had the rules for a second client's credential and no
 * caller for a month; `core/paired_clients.py` is the caller, and this is
 * the way in from Settings. The shape is the one people already know from
 * WhatsApp and Signal: the computer shows a code, the other device redeems
 * it, and the computer can revoke it. Here the "other device" is Claude
 * Code, Cline or a script on the same machine, holding `zaram_mcp` — the
 * Spine as an MCP server.
 *
 * **The credential never passes through here.** Settings issues a *token*;
 * the client redeems it itself and is the only thing that ever sees the
 * credential. What this surface can show is the token once, the list of
 * clients, and a Revoke — which is exactly the set of things an owner needs
 * and nothing that would be worth stealing off the screen.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface PairedClient {
  id: string;
  name: string;
  linkedAt: number;
  lastSeen: number | null;
  revokedAt: number | null;
  isActive: boolean;
}

export interface PairingToken {
  token: string;
  /** Seconds the token stays valid. About a minute, on purpose. */
  expiresIn: number;
  /** The command to run with the token, as the backend phrases it. */
  command: string;
}

export class PairingError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'PairingError';
    this.status = status;
  }
}

async function readOrThrow(response: Response): Promise<Record<string, unknown>> {
  if (response.ok) return (await response.json()) as Record<string, unknown>;
  let detail = response.statusText || `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string' && body.detail) detail = body.detail;
  } catch {
    /* not JSON */
  }
  throw new PairingError(detail, response.status);
}

const num = (value: unknown): number | null => (typeof value === 'number' ? value : null);

function toClient(raw: Record<string, unknown>): PairedClient {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    linkedAt: num(raw.linked_at) ?? 0,
    lastSeen: num(raw.last_seen),
    revokedAt: num(raw.revoked_at),
    isActive: raw.is_active === true,
  };
}

export async function fetchPairedClients(signal?: AbortSignal): Promise<PairedClient[]> {
  const raw = await readOrThrow(await fetch(`${API_BASE}/pairing/clients`, { signal }));
  return Array.isArray(raw.clients)
    ? raw.clients.map((c) => toClient(c as Record<string, unknown>))
    : [];
}

export async function issuePairingToken(): Promise<PairingToken> {
  const raw = await readOrThrow(await fetch(`${API_BASE}/pairing/token`, { method: 'POST' }));
  return {
    token: String(raw.token ?? ''),
    expiresIn: num(raw.expires_in) ?? 60,
    command: String(raw.command ?? ''),
  };
}

export async function revokePairedClient(id: string): Promise<void> {
  await readOrThrow(
    await fetch(`${API_BASE}/pairing/clients/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  );
}
