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
import type { UnfinishedTask } from '@/services/plansClient';
import type { ConversationSummary } from '@/services/conversationsClient';
import type { Project } from '@/stores/projectStore';

export interface GroundedPrompt {
  /** Goes into the composer, ready to send or edit. */
  prompt: string;
  /** Why this one: the measurement it rests on. */
  reason: string;
  /** Set on a row that is not a question for the model. Picking it does the
   *  thing instead of filling the composer. */
  action?: PickAction;
}

/** What a row does when it is not a prompt. `continue-tasks` opens the project
 *  and resumes its unfinished tasks, which is how the checklists are shown and
 *  ticked off;
 *  `reopen` brings a stored conversation back on screen. */
export type PickAction =
  | { kind: 'continue-tasks'; projectId: string; tasks: UnfinishedTask[] }
  | { kind: 'reopen'; conversationId: string };

/** A title is the first thing somebody typed, so it can be a paragraph. */
function short(title: string, limit = 48): string {
  const one = title.replace(/\s+/g, ' ').trim();
  return one.length <= limit ? one : `${one.slice(0, limit - 1).trimEnd()}…`;
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
    /** Tasks that stopped with work left. Optional: a caller that has not read
     *  them contributes no row, which is not the same as there being none. */
    plans?: UnfinishedTask[] | null;
    /** Stored conversations, newest activity first. */
    conversations?: ConversationSummary[] | null;
  },
  now = Date.now() / 1000,
): GroundedPrompt[] {
  const out: GroundedPrompt[] = [];

  // **First, and about the project that was touched last.** What is waiting
  // is the question a person returns to a project with, and "latest" is
  // measured -- the project of the most recently updated unfinished task --
  // rather than guessed from creation order. The name is looked up, never
  // taken from the task: a task whose project no longer exists would
  // otherwise put a bare id on the first line the person reads.
  const waiting = [...(input.plans ?? [])]
    .filter((t) => !t.finished && t.project_id)
    .sort((a, b) => b.updated_at - a.updated_at);
  const latest = waiting.find((t) => (input.projects ?? []).some((p) => p.id === t.project_id));
  if (latest) {
    const named = (input.projects ?? []).find((p) => p.id === latest.project_id)!;
    const count = waiting.filter((t) => t.project_id === latest.project_id).length;
    out.push({
      prompt: `What are the unfinished tasks in ${named.name}?`,
      reason: `${count} unfinished ${count === 1 ? 'task' : 'tasks'} · last touched ${when(latest.updated_at, now)}`,
      // Every one of them, oldest first: that is the order they were
      // asked in, and a later task may rest on an earlier one.
      action: {
        kind: 'continue-tasks',
        projectId: latest.project_id,
        tasks: waiting
          .filter((t) => t.project_id === latest.project_id)
          .sort((a, b) => a.created_at - b.created_at),
      },
    });
  }

  // **Then the thread they were last in.** Ordered by last activity, which is
  // what "the one I was just in" means, and only one that has something in it
  // -- the empty conversation being shown is itself the newest row in the
  // store. Named by its title, the person's own words, never a summary
  // Zaram wrote about it.
  const last = [...(input.conversations ?? [])]
    .filter((c) => c.messageCount > 0)
    .sort((a, b) => b.updatedAt - a.updatedAt)[0];
  if (last) {
    out.push({
      prompt: `Pick up where you left off: ${short(last.title)}`,
      reason: `${last.messageCount} ${last.messageCount === 1 ? 'message' : 'messages'} · ${when(last.updatedAt, now)}`,
      action: { kind: 'reopen', conversationId: last.id },
    });
  }

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
    // **Never Zaram's own manual.** These prompts are about the person's own
    // folder, and `manual.ensure_indexed` re-reads the manual at every start,
    // so it is the most recently scanned source on any fresh machine. That put
    // "What is in zaram-manual, in a few lines?" at the top of the first screen
    // a new user sees — a question about a folder they have never heard of,
    // named by its directory on disk, which recall then could not answer
    // because the pages say "Zaram" and never that. Rule 9's referential
    // failure, offered before the person had typed anything.
    .filter((s) => s.total > 0 && !s.builtin)
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
