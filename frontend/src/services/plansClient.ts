/**
 * Unfinished tasks — transport.
 *
 * A task that runs out of window hands itself over and carries on. When even
 * that allowance is spent it stops, and what it found is written down so the
 * job survives closing the app. This is how the interface reads that list.
 *
 * **The steps come back named, not filled in.** A tool result holds file
 * contents, and shipping all of it to render a row would put somebody's
 * repository into a panel nobody asked to read. Continuing the task is what
 * brings the contents back — into the model, not onto the screen.
 *
 * Field names are the backend's, for the reason `artifactsClient.ts` gives: a
 * mapping layer is a second vocabulary and a place for the two to disagree
 * quietly.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface PlanStep {
  server: string;
  tool: string;
}

export interface UnfinishedTask {
  id: string;
  question: string;
  project_id: string;
  model: string;
  /** What the user was told about why it stopped, in those words. */
  stopped_because: string;
  steps: PlanStep[];
  created_at: number;
  updated_at: number;
}

export interface UnfinishedTasks {
  plans: UnfinishedTask[];
  /** How long Zaram keeps one. Read from the backend rather than repeated here,
   *  so the number shown to the user is the number the store enforces. */
  kept_for_days: number;
}

export async function listUnfinished(
  projectId?: string,
  signal?: AbortSignal,
): Promise<UnfinishedTasks> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  const response = await fetch(`${API_BASE}/plans${query}`, { signal });
  if (!response.ok) {
    throw new Error(`Could not read unfinished tasks (${response.status})`);
  }
  return (await response.json()) as UnfinishedTasks;
}

export async function discardTask(planId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/plans/${encodeURIComponent(planId)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Could not discard the task (${response.status})`);
  }
  const body = (await response.json()) as { discarded?: boolean };
  return Boolean(body.discarded);
}
