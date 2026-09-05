/**
 * Tools transport — the MCP servers this machine has, and what each may do.
 *
 * **The client has been live since 1 September with no way in.**
 * `core/bootstrapper.py` builds the runtime, `core/planner.py` can name
 * `mcp.call`, and `core/execution_engine.py` runs it — but attaching a server
 * meant hand-editing `mcp-servers.json` in the data directory. This is the
 * same shape of gap `letterheadClient` was written to close: a capability the
 * product could not reach.
 *
 * **The shape is `.mcp.json`, deliberately.** A block that works in another
 * client is pasted rather than retyped into a form. `config.py` says why: a
 * config format is not a place to be original, and inventing one would be the
 * plugin-format mistake `CLAUDE.md` forbids arriving through the back door.
 *
 * **What a pasted block may not decide is decided on the server.**
 * `runtimes/mcp/api.py` strips `writes` and `grantedTools` before storing,
 * because a block can arrive from a stranger and a declared write mode is a
 * claim about its own permissions. Nothing here re-adds them, and nothing here
 * should ever send them — the interface offers no control that would.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What a server may change, as the backend records it.
 *
 *  `read_only` is the default for anything unrecognised. `host_undo` means the
 *  application behind the server has its own undo stack — Blender, Unreal,
 *  DaVinci, Figma — and that is the maintainer's checked claim, never the
 *  server's. */
export type WriteMode = 'read_only' | 'host_undo';

export interface ToolServer {
  id: string;
  /** The stdio command line, empty for an http server. */
  command: string[];
  /** Present for http servers, which this client cannot yet attach to. */
  url: string;
  transport: 'stdio' | 'http';
  /** Whether Zaram can actually connect. False for http: the transport does
   *  not exist yet, and saying so beats rendering an empty tool list that
   *  reads as a broken server. */
  reachable: boolean;
  writes: WriteMode;
  grantedTools: string[];
  /** Why this server is presumed to have undo, or null. The sentence to show
   *  beside one that may write, because "why is this allowed to change
   *  things" is the question a person actually has. */
  knownHost: string | null;
}

export class ToolsError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ToolsError';
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
    /* not JSON; the status text will have to do */
  }
  throw new ToolsError(detail, response.status);
}

const str = (value: unknown): string => (typeof value === 'string' ? value : '');
const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];

function toServer(raw: Record<string, unknown>): ToolServer {
  return {
    id: str(raw.id),
    command: strings(raw.command),
    url: str(raw.url),
    transport: raw.transport === 'http' ? 'http' : 'stdio',
    reachable: raw.reachable === true,
    // Anything unrecognised reads as read_only. A wrong guess in the other
    // direction would tell the user a server may write when it may not.
    writes: raw.writes === 'host_undo' ? 'host_undo' : 'read_only',
    grantedTools: strings(raw.grantedTools),
    knownHost: typeof raw.knownHost === 'string' && raw.knownHost ? raw.knownHost : null,
  };
}

export async function fetchServers(signal?: AbortSignal): Promise<ToolServer[]> {
  const raw = await readOrThrow(await fetch(`${API_BASE}/tools/servers`, { signal }));
  return Array.isArray(raw.servers) ? raw.servers.map((s) => toServer(s as Record<string, unknown>)) : [];
}

/**
 * Attach one or more servers from a pasted `.mcp.json` block.
 *
 * The text is parsed here so a malformed paste is a message beside the box
 * rather than a 422 from the server — the person is mid-edit and the answer
 * they need is *which bracket*, not a status code.
 */
export async function attachServers(blockText: string): Promise<ToolServer[]> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(blockText);
  } catch (error) {
    throw new ToolsError(
      `That is not valid JSON — ${(error as Error).message}`,
      0,
    );
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new ToolsError('Expected a JSON object with an "mcpServers" key.', 0);
  }

  // Both forms accepted: the whole file, or just the inner object. People paste
  // whichever half their clipboard happened to hold, and refusing one of them
  // teaches nothing.
  const record = parsed as Record<string, unknown>;
  const inner = record.mcpServers ?? record;
  if (!inner || typeof inner !== 'object' || Array.isArray(inner)) {
    throw new ToolsError('Expected a JSON object with an "mcpServers" key.', 0);
  }

  const raw = await readOrThrow(
    await fetch(`${API_BASE}/tools/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mcpServers: inner }),
    }),
  );
  return Array.isArray(raw.servers) ? raw.servers.map((s) => toServer(s as Record<string, unknown>)) : [];
}

export async function detachServer(serverId: string): Promise<void> {
  await readOrThrow(
    await fetch(`${API_BASE}/tools/servers/${encodeURIComponent(serverId)}`, { method: 'DELETE' }),
  );
}
