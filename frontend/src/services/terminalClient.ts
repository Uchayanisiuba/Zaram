/**
 * The project's terminal, as the person sees it.
 *
 * The tools that let Zaram use a shell existed for a day before anything let the
 * shell's owner look at it. These are the three calls behind the panel: read the
 * scrollback (which includes what Zaram ran), type a command of your own, close
 * the shell.
 *
 * **Both authors are kept, and the type says so.** A line is `zaram` or `user`;
 * a terminal that does not say who typed what is one nobody can audit.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';
const CLIENT_HEADER = { 'X-Zaram-Client': 'zaram-ui' } as const;

export interface TerminalLine {
  text: string;
  /** The command line itself, or what it printed. */
  kind: 'command' | 'output';
  who: 'zaram' | 'user';
  at: number;
}

export interface TerminalState {
  alive: boolean;
  lines: TerminalLine[];
  cwd: string;
}

export class TerminalError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'TerminalError';
  }
}

async function readOrThrow(res: Response): Promise<Record<string, unknown>> {
  if (res.ok) return (await res.json()) as Record<string, unknown>;
  let detail = res.statusText || `HTTP ${res.status}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === 'string' && body.detail) detail = body.detail;
  } catch {
    /* not JSON; the status text will have to do */
  }
  throw new TerminalError(detail, res.status);
}

function toState(raw: Record<string, unknown>): TerminalState {
  const lines = Array.isArray(raw.lines) ? raw.lines : [];
  return {
    alive: raw.alive === true,
    cwd: typeof raw.cwd === 'string' ? raw.cwd : '',
    lines: lines
      .filter((l): l is Record<string, unknown> => !!l && typeof l === 'object')
      .map((l) => ({
        text: String(l.text ?? ''),
        kind: l.kind === 'command' ? 'command' : 'output',
        who: l.who === 'user' ? 'user' : 'zaram',
        at: typeof l.at === 'number' ? l.at : 0,
      })),
  };
}

const path = (projectId: string) => `${API_BASE}/projects/${encodeURIComponent(projectId)}/terminal`;

export async function readTerminal(projectId: string, signal?: AbortSignal): Promise<TerminalState> {
  return toState(await readOrThrow(await fetch(path(projectId), { signal })));
}

/** Run the person's own command. Resolves when it finishes; the panel reads
 *  the scrollback meanwhile so a long install is watched rather than waited on. */
export async function typeInTerminal(projectId: string, command: string): Promise<TerminalState> {
  return toState(
    await readOrThrow(
      await fetch(path(projectId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CLIENT_HEADER },
        body: JSON.stringify({ command }),
      }),
    ),
  );
}

export async function stopTerminal(projectId: string): Promise<boolean> {
  const raw = await readOrThrow(
    await fetch(path(projectId), { method: 'DELETE', headers: CLIENT_HEADER }),
  );
  return raw.stopped === true;
}
