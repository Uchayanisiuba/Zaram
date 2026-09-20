/**
 * Tasks that outlive the thread — unfinished ones to continue, finished ones
 * to read — as one list, wherever it is shown.
 *
 * Lived inside `ProjectWorkspace` until 19 September 2026 (`docs/PLAN.md`
 * C3), which meant a task was only findable by first finding its project.
 * Activity now shows the same list across every project, at the top, as
 * *what is waiting on you*; Project keeps its own view. One component, two
 * mounts, so the two can never disagree about what a task looks like.
 */
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, ChevronRight, PlayCircle } from 'lucide-react';
import { discardTask, listUnfinished, type UnfinishedTask } from '@/services/plansClient';
import { useChatStore } from '@/stores/chatStore';

export function UnfinishedSection({
  projectId,
  onOpenConversation,
}: {
  projectId?: string;
  onOpenConversation?: () => void;
}) {
  const [tasks, setTasks] = useState<UnfinishedTask[]>([]);
  const [finished, setFinished] = useState<UnfinishedTask[]>([]);
  const [keptDays, setKeptDays] = useState(7);
  const send = useChatStore((s) => s.send);
  const setProject = useChatStore((s) => s.setProject);

  const load = useCallback(async () => {
    try {
      const answer = await listUnfinished(projectId);
      setTasks(answer.plans);
      setFinished(answer.finished ?? []);
      setKeptDays(answer.kept_for_days);
    } catch {
      // A list that cannot be read is not worth an error banner on a surface
      // whose main job is something else. It renders as nothing waiting, which
      // is what the user sees anyway when nothing is.
      setTasks([]);
      setFinished([]);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const resume = useCallback(
    (task: UnfinishedTask) => {
      // The project goes with it, because the task's tools are scoped to one —
      // a coding task resumed outside its project would have no folder to read.
      if (task.project_id) setProject(task.project_id);
      onOpenConversation?.();
      void send('Continue', { continueTask: true, planId: task.id });
    },
    [onOpenConversation, send, setProject],
  );

  const forget = useCallback(
    async (task: UnfinishedTask) => {
      await discardTask(task.id);
      void load();
    },
    [load],
  );

  if (!tasks.length && !finished.length) return null;

  if (!tasks.length) {
    return <FinishedTasks tasks={finished} keptDays={keptDays} />;
  }

  return (
    <>
    <section
      className="mb-5 rounded-xl px-4 py-4"
      style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.08)' }}
    >
      <h2 className="flex items-center gap-2 text-xs font-semibold">
        <PlayCircle size={13} aria-hidden style={{ color: 'var(--color-cyan-light)' }} />
        {tasks.length === 1 ? 'One task is unfinished' : `${tasks.length} tasks are unfinished`}
      </h2>
      <p className="mt-1.5 max-w-xl text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
        Zaram ran out of room before it finished these. It kept what it found —
        the results, not the conversation — and can carry on from there. Kept for{' '}
        {keptDays} days.
      </p>

      <ul className="mt-3 flex flex-col gap-2">
        {tasks.map((task) => (
          <li
            key={task.id}
            className="rounded-lg px-3 py-2.5"
            style={{ background: 'rgba(0,0,0,.16)', border: '1px solid rgba(255,255,255,.06)' }}
          >
            <p className="text-xs" style={{ color: 'var(--color-text)' }}>
              {task.question}
            </p>
            <p className="mt-1 text-xs leading-snug" style={{ color: 'var(--color-text-faint)' }}>
              {task.steps.length} {task.steps.length === 1 ? 'step' : 'steps'}
              {task.steps.length ? ` · ${task.steps.map((s) => s.tool).join(', ')}` : ''}
              {task.stopped_because ? ` · ${task.stopped_because}` : ''}
            </p>
            <TaskChecklist items={task.items} />
            <div className="mt-2 flex items-center gap-3">
              <button
                type="button"
                onClick={() => resume(task)}
                className="text-xs flex items-center gap-1"
                style={{ color: 'var(--color-cyan-light)' }}
                data-testid="resume-task"
              >
                Continue
                <ChevronRight size={10} aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => void forget(task)}
                className="text-xs"
                style={{ color: 'var(--color-text-faint)' }}
                data-testid="discard-task"
              >
                Discard
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
    {finished.length > 0 && <FinishedTasks tasks={finished} keptDays={keptDays} />}
    </>
  );
}

/**
 * The checklist on a task's row — what was done, what was skipped and why.
 *
 * Rendered from the record, the same list `PlanCard` shows under the reply,
 * so "what did Zaram do to this project on Tuesday" is answerable here on
 * Thursday rather than from scrollback. `docs/AGENT-UX.md`.
 */
function TaskChecklist({ items }: { items: UnfinishedTask['items'] }) {
  if (!items?.length) return null;
  const glyph: Record<string, string> = { done: '✓', doing: '›', todo: '·', skipped: '–' };
  return (
    <ol className="mt-1.5 flex flex-col gap-0.5" data-testid="task-checklist">
      {items.map((item, i) => (
        <li key={i} className="text-[10.5px] leading-snug flex gap-1.5" data-status={item.status}>
          <span
            style={{
              color: item.status === 'done' ? 'var(--color-green, #4ade80)' : 'var(--color-text-faint)',
              fontFamily: 'var(--font-mono)',
            }}
            aria-label={item.status}
          >
            {glyph[item.status] ?? '·'}
          </span>
          <span
            style={{
              color: item.status === 'done' ? 'var(--color-text-faint)' : 'var(--color-text-muted)',
              textDecoration: item.status === 'skipped' ? 'line-through' : 'none',
            }}
          >
            {item.text}
          </span>
          {item.reason && <span style={{ color: 'var(--color-text-faint)' }}>— {item.reason}</span>}
        </li>
      ))}
    </ol>
  );
}

/**
 * Tasks that finished and kept their checklist. No summary is generated —
 * the ticked list is the record of what happened, and a generated summary
 * could be wrong about it.
 */
function FinishedTasks({ tasks, keptDays }: { tasks: UnfinishedTask[]; keptDays: number }) {
  return (
    <section
      className="mb-5 rounded-xl px-4 py-4"
      style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.08)' }}
      data-testid="finished-tasks"
    >
      <h2 className="flex items-center gap-2 text-xs font-semibold">
        <CheckCircle2 size={13} aria-hidden style={{ color: 'var(--color-green, #4ade80)' }} />
        {tasks.length === 1 ? 'One task finished' : `${tasks.length} tasks finished`}
      </h2>
      <p className="mt-1.5 max-w-xl text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
        What Zaram did, as it ticked it off. Kept for {keptDays} days; the files it read are not.
      </p>
      <ul className="mt-3 flex flex-col gap-2">
        {tasks.map((task) => (
          <li
            key={task.id}
            className="rounded-lg px-3 py-2.5"
            style={{ background: 'rgba(0,0,0,.16)', border: '1px solid rgba(255,255,255,.06)' }}
          >
            <p className="text-xs" style={{ color: 'var(--color-text)' }}>
              {task.question}
            </p>
            <TaskChecklist items={task.items} />
          </li>
        ))}
      </ul>
    </section>
  );
}

