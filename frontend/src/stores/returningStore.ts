/**
 * The returning state — what the front door says about you.
 *
 * `docs/UI-SPEC.md` 6h: *"One mono line, not a dashboard: 14 new facts from
 * 3 sources · the Meridian deploy target changed · 0 bytes left this device.
 * Dismissible and skippable. The composer stays focused."* The site's
 * argument is that Zaram remembers you; until 14 September 2026 the app's
 * landing said nothing about you at all — six nodes, an orb, and an
 * instruction to click it.
 *
 * Three measured numbers and one name, each from an endpoint that already
 * exists: facts since you were last here (`/memory/stats?since=`), projects
 * (`/projects`), the conversation you were last in (`/conversations`), and
 * bytes that left today (`/memory/stats`). **A segment whose fetch failed
 * is omitted, never rendered as zero** — an absent measurement on a privacy
 * claim must not read as a measured one, the rule `bytes_left_device_today`
 * already follows. And with nothing remembered at all the line is empty, so
 * the first-launch instruction shows instead.
 *
 * "Since" is the previous launch, captured once per launch and persisted
 * after it is read; reloading on every return to the landing keeps the
 * numbers true without moving the moment they are counted from.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { fetchMemoryStats } from '@/services/memoryClient';
import { fetchConversations } from '@/services/conversationsClient';

export interface Returning {
  /** Epoch seconds of the previous launch, or null on the first. */
  sinceAt: number | null;
  /** Facts entered since `sinceAt`; null when unmeasured or no moment. */
  newFacts: number | null;
  totalFacts: number | null;
  projects: number | null;
  last: { id: string; title: string } | null;
  bytesToday: number | null;
}

export interface Segment {
  key: 'facts' | 'projects' | 'last' | 'bytes';
  text: string;
  /** Where the segment goes when pressed. */
  target: 'memory' | 'project' | 'resume' | 'activity';
  conversationId?: string;
}

const API = import.meta.env.VITE_ZARAM_API ?? '';

/** How many projects exist — `/projects`, the ones a person made, not
 *  `/artifacts/projects`, which is the ones that happen to hold a file. */
async function countProjects(): Promise<number> {
  const res = await fetch(`${API}/projects`);
  if (!res.ok) throw new Error(`Could not load projects (${res.status}).`);
  const body: { projects?: unknown[] } = await res.json();
  return (body.projects ?? []).length;
}

const bytes = (n: number) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "earlier today", "yesterday", "Tuesday", or "3 Sep". */
export function sinceWord(sinceAt: number, now: number): string {
  const then = new Date(sinceAt * 1000);
  const today = new Date(now * 1000);
  const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((dayStart(today) - dayStart(then)) / 86_400_000);
  if (days <= 0) return 'earlier today';
  if (days === 1) return 'yesterday';
  if (days < 7) return DAYS[then.getDay()];
  return `${then.getDate()} ${MONTHS[then.getMonth()]}`;
}

const TITLE_MAX = 24;
const shorten = (t: string) => (t.length > TITLE_MAX ? `${t.slice(0, TITLE_MAX - 1).trimEnd()}…` : t);

/** The line, as segments. Empty when there is nothing remembered. */
export function returningSegments(r: Returning, now = Date.now() / 1000): Segment[] {
  const remembered = (r.totalFacts ?? 0) > 0 || r.last !== null || (r.projects ?? 0) > 0;
  if (!remembered) return [];

  const out: Segment[] = [];
  if (r.sinceAt !== null && r.newFacts !== null) {
    // "since earlier today" says nothing a person needs; a day does.
    const when = sinceWord(r.sinceAt, now);
    const since = when === 'earlier today' ? '' : ` since ${when}`;
    out.push({
      key: 'facts',
      target: 'memory',
      text:
        r.newFacts === 0
          ? `no new facts${since}`
          : `${r.newFacts} new ${r.newFacts === 1 ? 'fact' : 'facts'}${since}`,
    });
  } else if (r.totalFacts !== null && r.totalFacts > 0) {
    out.push({
      key: 'facts',
      target: 'memory',
      text: `${r.totalFacts} ${r.totalFacts === 1 ? 'fact' : 'facts'}`,
    });
  }
  if (r.projects !== null && r.projects > 0) {
    out.push({
      key: 'projects',
      target: 'project',
      text: `${r.projects} ${r.projects === 1 ? 'project' : 'projects'}`,
    });
  }
  if (r.last) {
    out.push({ key: 'last', target: 'resume', conversationId: r.last.id, text: `last: ${shorten(r.last.title)}` });
  }
  if (r.bytesToday !== null) {
    out.push({
      key: 'bytes',
      target: 'activity',
      text: r.bytesToday === 0 ? '0 bytes out today' : `${bytes(r.bytesToday)} out today`,
    });
  }
  return out;
}

interface ReturningState {
  /** Persisted: when this launch first read the line, for the next one. */
  lastSeenAt: number | null;
  returning: Returning | null;
  dismissed: boolean;
  load: () => Promise<void>;
  dismiss: () => void;
}

/** The moment this launch counts from — read once, then held. */
let launchSince: number | null | undefined;

const settled = async <T,>(p: Promise<T>): Promise<T | null> => {
  try {
    return await p;
  } catch {
    return null;
  }
};

export const useReturningStore = create<ReturningState>()(
  persist(
    (set, get) => ({
      lastSeenAt: null,
      returning: null,
      dismissed: false,

      load: async () => {
        if (launchSince === undefined) {
          launchSince = get().lastSeenAt;
          set({ lastSeenAt: Date.now() / 1000 });
        }
        const since = launchSince;
        const [stats, projects, conversations] = await Promise.all([
          settled(fetchMemoryStats(undefined, since === null ? {} : { since })),
          settled(countProjects()),
          settled(fetchConversations(undefined, 1)),
        ]);
        const last = conversations?.[0];
        set({
          returning: {
            sinceAt: since,
            newFacts: stats?.new_since ?? null,
            totalFacts: stats?.total_records ?? null,
            projects,
            last: last ? { id: last.id, title: last.title } : null,
            bytesToday: stats?.bytes_left_device_today ?? null,
          },
        });
      },

      dismiss: () => set({ dismissed: true }),
    }),
    {
      name: 'zaram-returning',
      partialize: (s) => ({ lastSeenAt: s.lastSeenAt }),
    },
  ),
);

/** For tests: forget the launch moment so the next load reads it again. */
export function _resetLaunch(): void {
  launchSince = undefined;
}
