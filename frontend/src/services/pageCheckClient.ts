/**
 * Asking the backend to run a page a model wrote, and say whether it worked.
 *
 * `core/page_check.py` has the reasoning. Here: one call, a verdict, and a
 * failure to ask is reported as "could not check" rather than thrown or
 * mistaken for a pass.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface PageVerdict {
  /** Whether the page was run at all. */
  checked: boolean;
  /** True only when it was run, stayed up and threw nothing. */
  ok: boolean | null;
  hung: boolean;
  errors: string[];
  blocked: string[];
  blockedSeconds: number;
  /** What to tell a model, one sentence each. */
  problems: string[];
  /** Why it was not checked, or a line about a slow start. */
  note: string;
}

/** Longer than the backend's own budget, so the backend answers first. */
const TIMEOUT_MS = 60_000;

export async function checkPage(html: string): Promise<PageVerdict> {
  const unchecked = (note: string): PageVerdict => ({
    checked: false,
    ok: null,
    hung: false,
    errors: [],
    blocked: [],
    blockedSeconds: 0,
    problems: [],
    note,
  });
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}/preview/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html }),
      signal: abort.signal,
    });
    if (!response.ok) return unchecked(`the check was refused (${response.status})`);
    const body = (await response.json()) as Record<string, unknown>;
    return {
      checked: body.checked === true,
      ok: typeof body.ok === 'boolean' ? body.ok : null,
      hung: body.hung === true,
      errors: Array.isArray(body.errors) ? (body.errors as string[]) : [],
      blocked: Array.isArray(body.blocked) ? (body.blocked as string[]) : [],
      blockedSeconds: typeof body.blocked_seconds === 'number' ? body.blocked_seconds : 0,
      problems: Array.isArray(body.problems) ? (body.problems as string[]) : [],
      note: typeof body.note === 'string' ? body.note : '',
    };
  } catch {
    return unchecked('the backend did not answer');
  } finally {
    clearTimeout(timer);
  }
}
