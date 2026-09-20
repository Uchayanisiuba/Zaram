/**
 * Work that runs on its own — `core/triggers.py`, coworker step 4.
 *
 * A trigger is a question and when to ask it. A run is the ordinary chat
 * route, unattended: it never approves itself, and the first held tool
 * stops it and lands in Activity. Configured under Settings; read by
 * Activity. Nothing here is a menu item.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export type TriggerKind = 'daily' | 'weekly' | 'obligations';
export type RunOutcome = 'done' | 'held' | 'failed';

export interface Trigger {
  id: string;
  question: string;
  kind: TriggerKind;
  /** "HH:MM", local time. */
  at: string;
  weekday: string;
  daysAhead: number;
  projectId: string;
  enabled: boolean;
  lastRunAt: number;
  /** When it will next run, or null when it will not (disabled or paused). */
  nextRunAt: number | null;
  heldInARow: number;
  /** Non-empty when the circuit breaker paused it — three runs in a row that
   *  each stopped at something needing a person. */
  pausedReason: string;
}

export interface TriggerRun {
  id: string;
  triggerId: string;
  startedAt: number;
  finishedAt: number;
  outcome: RunOutcome;
  /** The conversation the run made — its transcript — or '' for a run that
   *  had nothing to do. */
  conversationId: string;
  question: string;
  obligationId: string;
  note: string;
}

function toTrigger(raw: Record<string, unknown>): Trigger {
  return {
    id: String(raw.id),
    question: String(raw.question ?? ''),
    kind: raw.kind as TriggerKind,
    at: String(raw.at ?? '09:00'),
    weekday: String(raw.weekday ?? 'mon'),
    daysAhead: Number(raw.days_ahead ?? 7),
    projectId: String(raw.project_id ?? ''),
    enabled: raw.enabled === true,
    lastRunAt: Number(raw.last_run_at ?? 0),
    nextRunAt: typeof raw.next_run_at === 'number' ? raw.next_run_at : null,
    heldInARow: Number(raw.held_in_a_row ?? 0),
    pausedReason: String(raw.paused_reason ?? ''),
  };
}

function toRun(raw: Record<string, unknown>): TriggerRun {
  return {
    id: String(raw.id),
    triggerId: String(raw.trigger_id),
    startedAt: Number(raw.started_at ?? 0),
    finishedAt: Number(raw.finished_at ?? 0),
    outcome: raw.outcome as RunOutcome,
    conversationId: String(raw.conversation_id ?? ''),
    question: String(raw.question ?? ''),
    obligationId: String(raw.obligation_id ?? ''),
    note: String(raw.note ?? ''),
  };
}

async function call(path: string, init?: RequestInit): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* the status is the message */
    }
    throw new Error(detail);
  }
  return (await res.json()) as Record<string, unknown>;
}

export async function fetchTriggers(): Promise<{ triggers: Trigger[]; runs: TriggerRun[] }> {
  const raw = await call('/triggers');
  return {
    triggers: ((raw.triggers as Record<string, unknown>[]) ?? []).map(toTrigger),
    runs: ((raw.runs as Record<string, unknown>[]) ?? []).map(toRun),
  };
}

export async function createTrigger(body: {
  question: string;
  kind: TriggerKind;
  at: string;
  weekday?: string;
  daysAhead?: number;
  projectId?: string;
}): Promise<Trigger> {
  return toTrigger(
    await call('/triggers', {
      method: 'POST',
      body: JSON.stringify({
        question: body.question,
        kind: body.kind,
        at: body.at,
        weekday: body.weekday ?? 'mon',
        days_ahead: body.daysAhead ?? 7,
        project_id: body.projectId ?? '',
      }),
    }),
  );
}

export async function setTriggerEnabled(id: string, enabled: boolean): Promise<Trigger> {
  return toTrigger(
    await call(`/triggers/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  );
}

export async function deleteTrigger(id: string): Promise<void> {
  await call(`/triggers/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function runTriggerNow(id: string): Promise<TriggerRun[]> {
  const raw = await call(`/triggers/${encodeURIComponent(id)}/run`, { method: 'POST' });
  return ((raw.runs as Record<string, unknown>[]) ?? []).map(toRun);
}

/** "Mondays at 09:00" / "Every day at 08:30" / "Obligations due within 7 days, checked daily at 08:00". */
export function describeSchedule(t: Pick<Trigger, 'kind' | 'at' | 'weekday' | 'daysAhead'>): string {
  const days: Record<string, string> = {
    mon: 'Mondays',
    tue: 'Tuesdays',
    wed: 'Wednesdays',
    thu: 'Thursdays',
    fri: 'Fridays',
    sat: 'Saturdays',
    sun: 'Sundays',
  };
  if (t.kind === 'weekly') return `${days[t.weekday] ?? t.weekday} at ${t.at}`;
  if (t.kind === 'obligations') return `Obligations due within ${t.daysAhead} days, checked daily at ${t.at}`;
  return `Every day at ${t.at}`;
}
