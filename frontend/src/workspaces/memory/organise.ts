/**
 * How Memory cuts, arranges and orders what Zaram remembers.
 *
 * **Everything here was already on the record and none of it was reachable.**
 * `MemoryRecord` carries `scope` (rule 7i), `standing` (rule 7e),
 * `access_count`, `source` and the correction chain, and the surface *rendered*
 * all of it per row while offering three filters: All, Pinned, Corrected. So a
 * user could read that a fact was fading and could not ask which ones were; the
 * screen showed the answer one fact at a time to somebody who had a question
 * about all of them.
 *
 * Two cuts matter more than the rest, and they are the two the rules single
 * out:
 *
 * * **Fading.** Rule 7e: facts enter provisionally, become durable through use,
 *   and *decay if never recalled*. Which ones are about to go is the one
 *   question on this surface with an action attached — pin it, correct it, or
 *   let it. It was the least reachable thing here.
 * * **Scope.** Rule 7i: `global` is about the person, `project:<id>` is about
 *   the work, and it is *"also the multiplayer boundary: project memory is
 *   shareable, global memory never is."* Somebody asking "what does this thing
 *   think it knows about me" is asking for the global cut, and there was no way
 *   to ask.
 *
 * Kept out of the workspace component so both can be walked without rendering a
 * screen that fetches four endpoints — the same reasoning as `work/organise.ts`.
 * The two files are deliberately *not* one shared abstraction yet: two examples
 * is where you start to see the shape, not where you commit to it, and the
 * grouping keys here are a different kind of thing from Work's.
 */
import { scopeProjectId, type MemoryRecord } from '@/services/memoryClient';

export type MemoryFilter = 'all' | 'fading' | 'pinned' | 'corrected';
export type MemoryGroupBy = 'none' | 'scope' | 'standing' | 'source';
export type MemorySortBy = 'newest' | 'oldest' | 'recalled' | 'forgotten';

export const FILTER_LABELS: Record<MemoryFilter, string> = {
  all: 'All',
  fading: 'Fading',
  pinned: 'Pinned',
  corrected: 'Corrected',
};

export const GROUP_LABELS: Record<MemoryGroupBy, string> = {
  none: 'Nothing',
  scope: 'What it is about',
  standing: 'How it is holding up',
  source: 'Where it came from',
};

export const SORT_LABELS: Record<MemorySortBy, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  recalled: 'Most recalled',
  forgotten: 'Least recalled',
};

/** The scope cut, in the user's words rather than the field's.
 *
 *  `global` is not a word anybody uses about themselves, and `project:acme` is
 *  a database value. `CLAUDE.md` says the target user is not technical and that
 *  filenames and internal identifiers stay out of the primary path — but the
 *  *project's own name* is the user's own string and is shown as it stands,
 *  because prettifying it would invent a value nobody entered. */
export function scopeLabel(scope: string | undefined): string {
  const project = scopeProjectId(scope);
  if (project) return project;
  return 'About you';
}

/** Whether `record` survives `filter`. */
export function matchesFilter(record: MemoryRecord, filter: MemoryFilter): boolean {
  switch (filter) {
    case 'fading':
      // Pinned is exempt from fading, so a pinned record is never in this cut
      // however its standing was computed. Asserting it here rather than
      // trusting the backend's `standing` is the one place this file duplicates
      // a rule — and it is worth it, because the cut is offered as "these will
      // be forgotten" and a pinned fact appearing in it would be a false alarm
      // about the user's own data.
      return record.standing === 'fading' && !record.pinned;
    case 'pinned':
      return record.pinned === true;
    case 'corrected':
      return Boolean(record.superseded_by);
    case 'all':
    default:
      return true;
  }
}

/** How many records fall in each cut. Live, so an empty filter says so before
 *  it is clicked rather than after. */
export function filterCounts(records: MemoryRecord[]): Record<MemoryFilter, number> {
  const counts = { all: 0, fading: 0, pinned: 0, corrected: 0 } as Record<MemoryFilter, number>;
  for (const record of records) {
    for (const key of Object.keys(counts) as MemoryFilter[]) {
      if (matchesFilter(record, key)) counts[key] += 1;
    }
  }
  return counts;
}

/** The distinct scopes present, with counts, `About you` first.
 *
 *  Global leads because it is the one every machine has and the one the
 *  multiplayer boundary is drawn around; projects follow by name. */
export function scopesPresent(
  records: MemoryRecord[],
): Array<{ scope: string; label: string; count: number }> {
  const seen = new Map<string, number>();
  for (const record of records) {
    const key = record.scope || 'global';
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  return [...seen.entries()]
    .map(([scope, count]) => ({ scope, label: scopeLabel(scope), count }))
    .sort((a, b) => {
      const aGlobal = !scopeProjectId(a.scope);
      const bGlobal = !scopeProjectId(b.scope);
      if (aGlobal !== bGlobal) return aGlobal ? -1 : 1;
      return a.label.localeCompare(b.label, undefined, { sensitivity: 'base' });
    });
}

export function comparator(sort: MemorySortBy): (a: MemoryRecord, b: MemoryRecord) => number {
  switch (sort) {
    case 'oldest':
      return (a, b) => a.created_at - b.created_at;
    case 'recalled':
      return (a, b) => b.access_count - a.access_count;
    case 'forgotten':
      // **Least recalled, tie-broken by age.** A pile of never-recalled facts
      // all reading `0` is not an ordering, and the useful question inside it
      // is which have been sitting unused *longest* — those are the ones decay
      // will reach first.
      return (a, b) => a.access_count - b.access_count || a.created_at - b.created_at;
    case 'newest':
    default:
      return (a, b) => b.created_at - a.created_at;
  }
}

export interface MemoryGroup {
  key: string;
  label: string;
  records: MemoryRecord[];
}

/** Standing, coarsest problem first: what is about to be lost, then what is
 *  holding, then what is safe. An ordering by severity rather than by
 *  alphabet, because the first group is the one with an action attached. */
const STANDING_ORDER = ['fading', 'provisional', 'durable', 'pinned', 'unknown'];

const STANDING_LABELS: Record<string, string> = {
  fading: 'Fading — the next pass would forget these',
  provisional: 'Provisional — stored, not yet used',
  durable: 'Durable — recalled and kept',
  pinned: 'Pinned — kept because you said so',
  unknown: 'Standing not recorded',
};

export function group(
  records: MemoryRecord[],
  by: MemoryGroupBy,
  sort: MemorySortBy,
): MemoryGroup[] {
  const sorted = records.slice().sort(comparator(sort));
  if (by === 'none') {
    return sorted.length ? [{ key: 'all', label: '', records: sorted }] : [];
  }

  const buckets = new Map<string, MemoryRecord[]>();
  for (const record of sorted) {
    const key =
      by === 'scope'
        ? record.scope || 'global'
        : by === 'standing'
          ? record.standing || 'unknown'
          : record.source || 'unknown';
    const existing = buckets.get(key);
    if (existing) existing.push(record);
    else buckets.set(key, [record]);
  }

  const keys = [...buckets.keys()];

  if (by === 'standing') {
    keys.sort((a, b) => STANDING_ORDER.indexOf(a) - STANDING_ORDER.indexOf(b));
    return keys.map((k) => ({
      key: k,
      label: STANDING_LABELS[k] ?? k,
      records: buckets.get(k)!,
    }));
  }

  if (by === 'scope') {
    keys.sort((a, b) => {
      const aGlobal = !scopeProjectId(a);
      const bGlobal = !scopeProjectId(b);
      if (aGlobal !== bGlobal) return aGlobal ? -1 : 1;
      return scopeLabel(a).localeCompare(scopeLabel(b), undefined, { sensitivity: 'base' });
    });
    return keys.map((k) => ({ key: k, label: scopeLabel(k), records: buckets.get(k)! }));
  }

  // Source is the user's own vocabulary — a filename, a conversation, "chat".
  // Shown as stored, never prettified.
  keys.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  return keys.map((k) => ({ key: k, label: k, records: buckets.get(k)! }));
}
