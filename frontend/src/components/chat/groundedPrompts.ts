/**
 * What to ask, drawn from what is actually there.
 *
 * The empty conversation said "ASK ZARAM SOMETHING" — a kicker over a blank
 * column, on a product whose whole claim is that it already knows things
 * about you. Rule 7h: *offer at the moment of doubt*. The moment somebody
 * has nothing typed is that moment, and the offer is cheapest when it is
 * about their own material.
 *
 * Every prompt is grounded in a measured thing and says so on the line
 * beneath it — a count of obligations, a folder and when it was read, a
 * project and how many facts it holds. **No example is invented**: with
 * nothing indexed the list is empty and the caller says so, because a
 * prompt about a client who does not exist would be rule 9's failure
 * offered up before the person has even asked.
 */
import type { IngestSource } from '@/services/ingestClient';
import type { ObligationCounts } from '@/services/obligationsClient';
import type { Project } from '@/stores/projectStore';

export interface GroundedPrompt {
  /** Goes into the composer, ready to send or edit. */
  prompt: string;
  /** Why this one: the measurement it rests on. */
  reason: string;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function when(epoch: number, now: number): string {
  const days = Math.floor((now - epoch) / 86_400);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  const d = new Date(epoch * 1000);
  return `on ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function groundedPrompts(
  input: {
    obligations: ObligationCounts | null;
    sources: IngestSource[] | null;
    projects: Project[] | null;
  },
  now = Date.now() / 1000,
): GroundedPrompt[] {
  const out: GroundedPrompt[] = [];

  const o = input.obligations;
  if (o && o.open > 0) {
    out.push({
      prompt: 'What do I owe, and what am I owed, this month?',
      reason:
        o.overdue > 0
          ? `${o.open} open ${o.open === 1 ? 'obligation' : 'obligations'} in your documents · ${o.overdue} overdue`
          : `${o.open} open ${o.open === 1 ? 'obligation' : 'obligations'} in your documents`,
    });
  }

  const source = [...(input.sources ?? [])]
    .filter((s) => s.total > 0)
    .sort((a, b) => b.scanned_at - a.scanned_at)[0];
  if (source) {
    out.push({
      prompt: `What is in ${source.name}, in a few lines?`,
      reason: `${source.total} ${source.total === 1 ? 'file' : 'files'} read ${when(source.scanned_at, now)}`,
    });
  }

  const project = [...(input.projects ?? [])]
    .filter((p) => p.facts > 0)
    .sort((a, b) => b.facts - a.facts)[0];
  if (project) {
    out.push({
      prompt: `What has been decided on ${project.name} so far?`,
      reason: `${project.facts} ${project.facts === 1 ? 'fact' : 'facts'} scoped to that project`,
    });
  }

  return out.slice(0, 3);
}
