/**
 * What falls due soon, said once — the one time Zaram speaks first.
 *
 * `CLAUDE.md`: obligations are *"surfaced before they lapse"*, and *"Zaram
 * speaks first only when it has something real."* A commitment with a date
 * inside the coming week is something real. The desktop's notification
 * service existed from the first build and nothing ever called it — the
 * unreachable-subsystem shape this repository keeps finding — so this is
 * its first caller.
 *
 * Three bounds, each of which is what keeps this from being an engagement
 * mechanic:
 *
 * - **Only open obligations with a date within `WITHIN_DAYS`, or already
 *   past.** Nothing else earns an interruption.
 * - **Once per obligation per day.** What was said is remembered in
 *   `localStorage`; a restart does not repeat it, and tomorrow says it again
 *   only if it is still open.
 * - **One notification, not one per item.** Three things due this week is
 *   one sentence, with the nearest first.
 *
 * Zaram is not a calendar and does not become one here: it says a date is
 * coming and where the clause is. Putting it *in* a calendar is the export.
 */

import type { Obligation } from '@/services/obligationsClient';
import { daysUntil } from '@/services/obligationsClient';

export const WITHIN_DAYS = 7;
const KEY = 'zaram.dueSoon.said';

export interface DueSoonNotice {
  title: string;
  body: string;
  /** The obligations the notice covers, nearest first. */
  ids: string[];
}

function dayStamp(now: Date): string {
  return now.toISOString().slice(0, 10);
}

/** The ids already said today, from storage that may be absent or refuse. */
export function alreadySaid(now: Date, storage: Pick<Storage, 'getItem'> | null): Set<string> {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as { day?: string; ids?: string[] };
    if (parsed.day !== dayStamp(now)) return new Set();
    return new Set(parsed.ids ?? []);
  } catch {
    return new Set();
  }
}

export function rememberSaid(ids: string[], now: Date, storage: Pick<Storage, 'setItem'> | null): void {
  try {
    storage?.setItem(KEY, JSON.stringify({ day: dayStamp(now), ids }));
  } catch {
    /* a notification is not worth a failed launch */
  }
}

function when(days: number): string {
  if (days < 0) return days === -1 ? 'yesterday' : `${-days} days ago`;
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  return `in ${days} days`;
}

/**
 * The notice to show now, or `null` when there is nothing new to say.
 * Pure: takes the listing, the clock, and what was already said.
 */
export function dueSoonNotice(
  obligations: Obligation[],
  now: Date,
  said: Set<string>,
): DueSoonNotice | null {
  const due = obligations
    .filter((o) => o.status === 'open' && !o.superseded_by)
    .map((o) => ({ o, days: daysUntil(o.due, now) }))
    .filter((x): x is { o: Obligation; days: number } => x.days !== null && x.days <= WITHIN_DAYS)
    .filter((x) => !said.has(x.o.id))
    .sort((a, b) => a.days - b.days);
  if (due.length === 0) return null;

  const lines = due.slice(0, 3).map((x) => `${x.o.summary} — ${when(x.days)}`);
  const more = due.length > 3 ? ` and ${due.length - 3} more` : '';
  const overdue = due.filter((x) => x.days < 0).length;
  const title =
    overdue > 0
      ? `${overdue} commitment${overdue === 1 ? ' is' : 's are'} past due`
      : `${due.length} commitment${due.length === 1 ? '' : 's'} due this week`;
  return { title, body: lines.join('\n') + more, ids: due.map((x) => x.o.id) };
}
