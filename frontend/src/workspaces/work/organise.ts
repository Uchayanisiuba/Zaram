/**
 * How Work arranges what you made: grouped, sorted, and searched.
 *
 * Extracted from `WorkWorkspace` because it is the part with answers that can
 * be wrong. A layout is a judgement; *"which bucket does a file made at 23:58
 * last night belong in"* is a question with a right answer, and the only way to
 * know it is right on the boundary is to ask it there.
 *
 * **Grouping is the categorisation, and it is not a folder tree.** `CLAUDE.md`
 * refuses a hierarchy outright — *"a hierarchy would be a second organising
 * system competing with the one that is the product"*, and *"if a tree is
 * needed to find your own work then recall has failed and the tree hides the
 * failure"*. Grouping is the opposite of a tree in the way that matters: a file
 * is in exactly one group under the current grouping and in a different one
 * under the next, nothing is ever *filed* anywhere, and switching the control
 * re-cuts the same set. Nobody decides in advance where anything goes, which is
 * rule 7h.
 *
 * **Three axes, and each is one the user already has words for.** Type is what
 * a thing *is*, project is what it is *for*, and date is when it happened.
 * There is deliberately no fourth: a control offering six ways to sort a list
 * of nine documents is a preferences screen wearing a toolbar.
 */
import {
  KIND_LABELS,
  type Artifact,
  type ArtifactKind,
} from '@/services/artifactsClient';

export type GroupBy = 'type' | 'project' | 'date' | 'none';
export type SortBy = 'newest' | 'oldest' | 'name' | 'largest';

export const GROUP_LABELS: Record<GroupBy, string> = {
  type: 'Type',
  project: 'Project',
  date: 'Date',
  none: 'Nothing',
};

export const SORT_LABELS: Record<SortBy, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  name: 'Name',
  largest: 'Largest first',
};

/** One heading and the rows under it. */
export interface ArtifactGroup {
  /** Stable across renders and unique within a listing — used as the React key
   *  and as the id of the heading a row is labelled by. */
  key: string;
  label: string;
  artifacts: Artifact[];
}

/**
 * The date buckets, coarsest last.
 *
 * **Boundaries are calendar days, not elapsed hours.** "Yesterday" has to mean
 * the day before this one, so a file made at 23:58 last night is *yesterday* at
 * 00:30 today rather than "today" for another twenty-three hours. Measuring in
 * 24-hour blocks from `now` gets that backwards, and it is wrong in the way
 * nobody reports — it merely makes the list feel unreliable.
 */
const DAY_MS = 86_400_000;

function startOfDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** Which date bucket `createdAt` (epoch **seconds**) falls in. */
export function dateBucket(createdAt: number, now: number = Date.now()): string {
  const today = startOfDay(now);
  const made = startOfDay(createdAt * 1000);
  const daysAgo = Math.round((today - made) / DAY_MS);

  // A file dated in the future is not a bucket, it is a clock disagreement —
  // a machine whose time moved, or a record written by another device. It goes
  // in Today rather than into a "Later" heading nobody can act on, because the
  // honest thing to show is the most recent bucket, not a claim about when it
  // will exist.
  if (daysAgo <= 0) return 'Today';
  if (daysAgo === 1) return 'Yesterday';
  if (daysAgo < 7) return 'Earlier this week';
  if (daysAgo < 30) return 'Earlier this month';
  if (daysAgo < 365) return 'Earlier this year';
  return 'Older';
}

/** The order the date buckets are shown in. Newest first, always — a date
 *  grouping ordered any other way is not a date grouping. */
const DATE_ORDER = [
  'Today',
  'Yesterday',
  'Earlier this week',
  'Earlier this month',
  'Earlier this year',
  'Older',
];

/** The order the type buckets are shown in: the order `KIND_LABELS` declares.
 *
 *  Read from there rather than restated, so a kind added to the union appears
 *  here without this file being touched. The second copy of a kind map is how
 *  `deck` and `cv` shipped on the backend for weeks with no icon in Work. */
const TYPE_ORDER = Object.keys(KIND_LABELS) as ArtifactKind[];

/** Compare two artifacts under `sort`. */
export function comparator(sort: SortBy): (a: Artifact, b: Artifact) => number {
  switch (sort) {
    case 'oldest':
      return (a, b) => a.created_at - b.created_at;
    case 'name':
      // `localeCompare` with `numeric`, so `image-2` sorts before `image-10`.
      // Plain string order puts `image-10` first, which is the one place a
      // filename list is obviously wrong to a person scanning it — and Zaram
      // names its own output with trailing numbers.
      return (a, b) =>
        a.filename.localeCompare(b.filename, undefined, { numeric: true, sensitivity: 'base' });
    case 'largest':
      return (a, b) => b.size_bytes - a.size_bytes;
    case 'newest':
    default:
      return (a, b) => b.created_at - a.created_at;
  }
}

/**
 * Rows whose filename or conversation title contains `query`.
 *
 * **The conversation is searched too, and that is not a nicety.** Work exists
 * to hold output *with* the exchange that produced it; someone looking for
 * "the invoice for the Northwind job" remembers the job, not
 * `invoice-0007.pdf`. Searching filenames alone would make this the file
 * browser the surface is explicitly not.
 *
 * An empty or whitespace query returns everything rather than nothing.
 */
export function search(artifacts: Artifact[], query: string): Artifact[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return artifacts;
  return artifacts.filter(
    (a) =>
      a.filename.toLowerCase().includes(needle) ||
      (a.conversation_title ?? '').toLowerCase().includes(needle) ||
      (a.project_id ?? '').toLowerCase().includes(needle),
  );
}

/**
 * Cut `artifacts` into headed groups, each internally sorted by `sort`.
 *
 * Returns a single unlabelled group for `none`, so a caller renders one code
 * path rather than branching on the grouping — a second rendering path for the
 * ungrouped case is how the two come to disagree about row markup.
 *
 * **Empty groups are never emitted.** A heading with nothing under it is a
 * claim that the bucket exists and is empty, which on this surface reads as
 * "your invoices are gone" rather than "you have not made any".
 */
export function group(
  artifacts: Artifact[],
  by: GroupBy,
  sort: SortBy,
  now: number = Date.now(),
): ArtifactGroup[] {
  const sorted = artifacts.slice().sort(comparator(sort));
  if (by === 'none') {
    return sorted.length ? [{ key: 'all', label: '', artifacts: sorted }] : [];
  }

  const buckets = new Map<string, Artifact[]>();
  for (const artifact of sorted) {
    const key =
      by === 'type'
        ? artifact.kind
        : by === 'project'
          ? artifact.project_id || ''
          : dateBucket(artifact.created_at, now);
    const existing = buckets.get(key);
    if (existing) existing.push(artifact);
    else buckets.set(key, [artifact]);
  }

  const keys = [...buckets.keys()];

  if (by === 'type') {
    keys.sort((a, b) => TYPE_ORDER.indexOf(a as ArtifactKind) - TYPE_ORDER.indexOf(b as ArtifactKind));
    return keys.map((k) => ({
      key: k,
      label: KIND_LABELS[k as ArtifactKind] ?? k,
      artifacts: buckets.get(k)!,
    }));
  }

  if (by === 'date') {
    keys.sort((a, b) => DATE_ORDER.indexOf(a) - DATE_ORDER.indexOf(b));
    return keys.map((k) => ({ key: k, label: k, artifacts: buckets.get(k)! }));
  }

  // Projects are the user's own strings, so they are ordered by name — except
  // the unassigned bucket, which goes last. It is not a project, it is the
  // absence of one, and sorting `''` alphabetically puts it first, where it
  // reads as the most important group on the surface.
  keys.sort((a, b) => {
    if (a === '') return 1;
    if (b === '') return -1;
    return a.localeCompare(b, undefined, { sensitivity: 'base' });
  });
  return keys.map((k) => ({
    key: k || '__none__',
    // Not prettified. A slug turned into a title is a value nobody entered.
    label: k || 'No project',
    artifacts: buckets.get(k)!,
  }));
}
