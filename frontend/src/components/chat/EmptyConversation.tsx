/**
 * The empty conversation: three things worth asking, and what each one gives you.
 *
 * Two kinds of row, one list. **Grounded prompts go first** — a question about
 * the person's own folder, project or obligations, resting on a measurement,
 * per `groundedPrompts`. **Starter tasks fill what is left** — see
 * `starterTasks`, added 15 September 2026 after reading OpenWorker's
 * `SessionIntro`, because this screen used to answer a fresh install with one
 * line telling somebody to go and configure Knowledge. That was true and it
 * was not an answer to *what is this for*, which is the only question a person
 * has before they have typed anything.
 *
 * A starter carries the outcome on its sub-line and a **dot in one
 * vocabulary**: lit means this works on this machine right now, measured;
 * unlit means something is needed first, and then the row's action *is* the
 * setup, pointing at the surface that fixes it. Nothing here is optimistic — a
 * signal the interface could not read counts as not ready, so a failed fetch
 * lights nothing.
 *
 * Read once when the state mounts, and again when the engine comes back: each
 * request is allowed to fail on its own, and a failed one contributes no row.
 */
import { useEffect, useState } from 'react';
import { fetchObligations, countObligations, type ObligationCounts } from '@/services/obligationsClient';
import { fetchSources, type IngestSource } from '@/services/ingestClient';
import { fetchReadiness } from '@/services/readinessClient';
import { listUnfinished, type UnfinishedTask } from '@/services/plansClient';
import { fetchConversations } from '@/services/conversationsClient';
import { fetchServers } from '@/services/toolsClient';
import { fetchWebSearch } from '@/services/settingsClient';
import type { Project } from '@/stores/projectStore';
import type { WorkspaceId } from '@/runtime/shortcuts/registry';
import { useSystemStore } from '@/stores/systemStore';
import { groundedPrompts, type GroundedPrompt, type PickAction } from './groundedPrompts';
import { starterTasks, fillTo, serverKinds, type Capabilities, type OfferedTask } from './starterTasks';

const API = import.meta.env.VITE_ZARAM_API ?? '';

async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API}/projects`);
  if (!res.ok) throw new Error(`Could not load projects (${res.status}).`);
  const body: { projects?: Project[] } = await res.json();
  return body.projects ?? [];
}

const settled = async <T,>(p: Promise<T>): Promise<T | null> => {
  try {
    return await p;
  } catch {
    return null;
  }
};

export default function EmptyConversation({
  onPick,
  onNavigate,
}: {
  onPick: (prompt: string, action?: PickAction) => void;
  /** Where a "Configure" row goes. The shell owns navigation. */
  onNavigate?: (id: WorkspaceId) => void;
}) {
  // `undefined` until read: the fallback must not flash before the prompts.
  // `null` when nothing could be read at all — an engine that is down is not
  // a Knowledge that is empty, and saying "nothing is indexed" off a failed
  // fetch would be a measured zero invented from an absent measurement.
  const [prompts, setPrompts] = useState<GroundedPrompt[] | null | undefined>(undefined);
  const [starters, setStarters] = useState<OfferedTask[]>([]);
  // Read again when the engine comes back: a list read while it was down is
  // `null`, and the prompts should appear the moment they can be measured.
  const backendOnline = useSystemStore((s) => s.backendOnline);

  useEffect(() => {
    let live = true;
    void (async () => {
      const [listing, sources, projects, waiting, conversations, readiness, servers, search] = await Promise.all([
        settled(fetchObligations()),
        settled(fetchSources()),
        settled(fetchProjects()),
        settled(listUnfinished()),
        settled(fetchConversations(undefined, 10)),
        settled(fetchReadiness()),
        settled(fetchServers()),
        settled(fetchWebSearch()),
      ]);
      if (!live) return;

      // Unread is not ready. Every one of these is `false` unless something
      // came back and said otherwise.
      const kinds = serverKinds(servers ?? []);
      const capabilities: Capabilities = {
        model: readiness?.canChat === true,
        documents: (sources ?? []).some((s) => s.total > 0),
        tools: (servers ?? []).some((s) => s.reachable),
        search: search?.on === true && readiness?.canChat === true,
        email: kinds.email && readiness?.canChat === true,
        github: kinds.github && readiness?.canChat === true,
      };
      setStarters(starterTasks(capabilities));

      if (listing === null && sources === null && projects === null && waiting === null && conversations === null) {
        setPrompts(null);
        return;
      }
      const obligations: ObligationCounts | null = listing ? countObligations(listing) : null;
      setPrompts(
        groundedPrompts({
          obligations,
          sources: sources as IngestSource[] | null,
          projects,
          plans: waiting?.plans ?? null,
          conversations,
        }),
      );
    })();
    return () => {
      live = false;
    };
  }, [backendOnline]);

  const grounded = prompts ?? [];
  // Three rows at first, as before; the rest of the use cases sit behind
  // one quiet line, so the screen stays calm and the list stays complete.
  const [more, setMore] = useState(false);
  // The waiting tasks, opened out. Only when there is more than one: with one
  // there is nothing to choose between and the row just does it.
  const [listOpen, setListOpen] = useState(false);
  const firstFew = starters.slice(0, fillTo(grounded.length));
  const rest = starters.slice(firstFew.length);
  const shown = more ? starters : firstFew;

  return (
    <div className="flex flex-col gap-3" data-testid="empty-conversation">
      <p className="t-kicker">Ask Zaram something</p>
      {prompts === undefined ? null : (
        /* Suggestive, not a card: a quiet line per row, in the faint tone,
           brightening under the pointer. The maintainer saw the boxed version
           and called it too visible (14 September) — a suggestion is something
           to take or leave, and a box asks to be dealt with. */
        <ul className="flex flex-col gap-2" aria-label="Things worth asking">
          {grounded.map((p) => (
            <li key={p.prompt}>
              <button
                type="button"
                onClick={() => {
                  if (p.action?.kind === 'continue-tasks' && p.action.tasks.length > 1) {
                    setListOpen((v) => !v);
                    return;
                  }
                  onPick(p.prompt, p.action);
                }}
                className="group text-left text-sm leading-snug transition-colors"
                style={{ color: 'var(--color-text-faint)', background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
                data-testid="grounded-prompt"
              >
                <span className="group-hover:text-[var(--color-text-muted-light)] transition-colors">
                  <span aria-hidden style={{ opacity: 0.6 }}>›  </span>
                  {p.prompt}
                </span>
                <span className="t-mono ml-2" style={{ color: 'var(--color-text-faint)', opacity: 0.8 }}>
                  {p.reason}
                </span>
              </button>
              {p.action?.kind === 'continue-tasks' && p.action.tasks.length > 1 && listOpen && (
                <WaitingTasks
                  action={p.action}
                  onRun={(tasks) =>
                    onPick(p.prompt, { kind: 'continue-tasks', projectId: p.action!.kind === 'continue-tasks' ? p.action!.projectId : '', tasks })
                  }
                />
              )}
            </li>
          ))}

          {shown.map((task) => (
            <li key={task.prompt} data-testid="starter-task" data-ready={task.ready ? 'true' : 'false'}>
              <button
                type="button"
                onClick={() => (task.ready ? onPick(task.prompt) : onNavigate?.(task.configure.node as WorkspaceId))}
                className="group text-left w-full transition-colors"
                style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
              >
                <span className="flex items-baseline gap-2 text-sm leading-snug">
                  {/* The dot, in the one vocabulary: lit = this works now. */}
                  <span
                    aria-hidden
                    data-testid="starter-dot"
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      flexShrink: 0,
                      transform: 'translateY(-1px)',
                      background: task.ready ? 'var(--color-cyan-light)' : 'var(--color-text-faint)',
                      opacity: task.ready ? 0.9 : 0.35,
                    }}
                  />
                  <span
                    className="group-hover:text-[var(--color-text-muted-light)] transition-colors"
                    style={{ color: 'var(--color-text-faint)' }}
                  >
                    {task.prompt.trim().split('\n')[0]}
                  </span>
                  {/* Ready: the action is quiet and appears on hover. Not
                      ready: the setup IS the row's meaning, so it is always
                      visible — OpenWorker's rule, and it is right. */}
                  {task.ready ? (
                    <span
                      className="t-mono opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: 'var(--color-cyan-light)' }}
                    >
                      Start →
                    </span>
                  ) : (
                    <span className="t-mono" style={{ color: 'var(--color-text-faint)', opacity: 0.8 }}>
                      {task.configure.label} ›
                    </span>
                  )}
                </span>
                <span
                  className="block text-xs leading-snug"
                  style={{ color: 'var(--color-text-faint)', opacity: 0.75, paddingLeft: 14 }}
                >
                  {task.outcome}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {prompts !== undefined && rest.length > 0 && (
        <button
          type="button"
          onClick={() => setMore((v) => !v)}
          aria-expanded={more}
          className="self-start text-xs t-mono transition-colors"
          style={{ color: 'var(--color-text-faint)', background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
          data-testid="starter-more"
        >
          {more ? 'Fewer' : rest.length + ' more things Zaram does ›'}
        </button>
      )}
    </div>
  );
}

/** The unfinished tasks of one project, laid out before anything runs: what
 *  each was asked, how far its checklist got, and a way to run one or all. */
function WaitingTasks({
  action,
  onRun,
}: {
  action: Extract<PickAction, { kind: 'continue-tasks' }>;
  onRun: (tasks: UnfinishedTask[]) => void;
}) {
  const linkStyle = {
    color: 'var(--color-cyan-light)',
    background: 'none',
    border: 0,
    padding: 0,
    cursor: 'pointer',
  } as const;
  return (
    <div className="mt-2" style={{ paddingLeft: 14 }} data-testid="waiting-tasks">
      <ul className="flex flex-col gap-1.5">
        {action.tasks.map((task) => {
          const done = task.items.filter((i) => i.status === 'done').length;
          return (
            <li key={task.id} className="flex items-baseline gap-2 text-xs" data-testid="waiting-task">
              <span className="min-w-0 truncate" style={{ color: 'var(--color-text-muted)', maxWidth: 420 }} title={task.question}>
                {task.question}
              </span>
              <span className="t-mono shrink-0" style={{ color: 'var(--color-text-faint)' }}>
                {task.items.length ? `${done} of ${task.items.length} done` : 'not planned yet'}
              </span>
              <button type="button" className="t-mono shrink-0" style={linkStyle} onClick={() => onRun([task])} data-testid="run-one-task">
                Continue
              </button>
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="t-mono mt-2 text-xs"
        style={linkStyle}
        onClick={() => onRun(action.tasks)}
        data-testid="run-all-tasks"
      >
        Run all {action.tasks.length} in order →
      </button>
    </div>
  );
}
