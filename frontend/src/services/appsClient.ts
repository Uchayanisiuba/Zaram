/** Direct calls to the code pack's app stack tools.
 *
 * These go through the same `fetch` wrapper as the rest of the product,
 * so the API credential is attached automatically.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';
const CODE_PACK_SERVER_ID = 'code'; // The built-in code pack server ID

/** Direct tool call via the MCP runtime. */
async function callTool(
  server: string,
  tool: string,
  arguments_: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/tools/call`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ server, tool, arguments: arguments_ }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to call ${tool} on ${server}`);
  }
  const data = await res.json();
  return data.result as Record<string, unknown>;
}

export interface StackRunnerInfo {
  name: string;
  group?: string;
  description: string;
}

export interface StackProcess {
  name: string;
  /** What the process is for -- `frontend`, `backend`, `worker`, `database` --
   *  or null when nothing says. The page to open is chosen by this. */
  role?: string | null;
  runner: string;
  command: string;
  running: boolean;
  pid: number;
  url: string | null;
  ready: boolean;
  state: 'stopped' | 'ready' | 'starting';
  readiness_error: string;
  http_status: number | null;
  exit_code: number | null;
  uptime_seconds: number;
}

export interface StackStartResult {
  stack: boolean;
  processes: StackProcess[];
  started: string[];
}

export interface StackStatusResult {
  running: boolean;
  processes: StackProcess[];
  available: string[];
}

/** Start multiple runners as a stack for the given project. */
export async function startAppStack(
  _projectId: string,
  runners: string[],
): Promise<StackStartResult> {
  const result = await callTool(CODE_PACK_SERVER_ID, 'start_app_stack', { runners });
  return result as unknown as StackStartResult;
}

/** Stop all processes in the project's app stack. */
export async function stopAppStack(
  _projectId: string,
): Promise<{ stopped: boolean; processes: string[] }> {
  const result = await callTool(CODE_PACK_SERVER_ID, 'stop_app_stack', {});
  return result as unknown as { stopped: boolean; processes: string[] };
}

/** Get status of all processes in the project's app stack. */
export async function getAppStackStatus(
  _projectId: string,
): Promise<StackStatusResult> {
  const result = await callTool(CODE_PACK_SERVER_ID, 'get_app_stack_status', {});
  return result as unknown as StackStatusResult;
}

/** Get available stack groups for a project. */
export async function getStackGroups(
  _projectId: string,
): Promise<Record<string, string[]>> {
  const result = await callTool(CODE_PACK_SERVER_ID, 'get_stack_groups', {});
  return result as unknown as Record<string, string[]>;
}