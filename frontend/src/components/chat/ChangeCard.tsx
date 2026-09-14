/**
 * A change Zaram made to a file, shown as the diff, with the one button that
 * reverses it.
 *
 * The code pack's write tools land as a git commit each — that is the undo,
 * and the checkbox in Project says so in as many words: *"each change is a
 * git commit you can revert"*. A promise that needs the terminal is not kept
 * for the people this is for, so the card carries the button.
 *
 * **Never folded.** Every other tool call sits behind a summary line; a change
 * to somebody's repository does not. Claude Code, Cursor and Cline all put the
 * diff in front of the person without a click, and they are right: it is the
 * one output of an agentic reply that a reader must be able to judge at a
 * glance. A diff card is not an editor — Work gains no sub-apps for editing —
 * and there is no per-hunk accept: consent was given once, per project, and
 * the review is after the fact with revert as the answer. That is also what
 * lets a local model work uninterrupted, which is the whole point of it.
 *
 * The diff is text from the user's own file and the model's edit, bounded by
 * the backend and rendered into a `<pre>`; colour comes from the first
 * character of each line and nothing in the text can become an element.
 */
import { useMemo, useState } from 'react';
import { Undo2 } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';
import { useChatStore } from '../../stores/chatStore';
import { useProjectStore } from '../../stores/projectStore';

const VERB: Record<string, string> = {
  write_file: 'wrote',
  edit_file: 'edited',
};

function lineColor(line: string): string | undefined {
  if (line.startsWith('+++') || line.startsWith('---')) return 'var(--color-text-faint)';
  if (line.startsWith('@@')) return 'var(--color-cyan-light)';
  if (line.startsWith('+')) return 'var(--color-green, #4ade80)';
  if (line.startsWith('-')) return 'var(--color-red, #f87171)';
  return undefined;
}

export default function ChangeCard({ call }: { call: ChatToolCall }) {
  const projectId = useChatStore((s) => s.projectId);
  const revertCommit = useProjectStore((s) => s.revertCommit);
  const [phase, setPhase] = useState<'idle' | 'working' | 'reverted' | 'failed'>('idle');
  const [failure, setFailure] = useState('');

  const lines = useMemo(() => (call.diff ?? '').split('\n'), [call.diff]);
  const added = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length;
  const removed = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length;
  const canRevert = Boolean(projectId && call.commit) && phase !== 'reverted';

  async function revert() {
    if (!projectId || !call.commit) return;
    setPhase('working');
    const error = await revertCommit(projectId, call.commit);
    if (error) {
      setFailure(error);
      setPhase('failed');
    } else {
      setPhase('reverted');
    }
  }

  return (
    <div
      className="mt-2 rounded-lg surface"
      data-testid="change-card"
      data-commit={call.commit}
    >
      <div className="flex items-center gap-2 px-3 py-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <span>{VERB[call.tool] ?? call.tool}</span>
        <code className="truncate" style={{ fontFamily: 'var(--font-mono)' }}>
          {call.target}
        </code>
        <span style={{ color: 'var(--color-green, #4ade80)' }}>+{added}</span>
        <span style={{ color: 'var(--color-red, #f87171)' }}>−{removed}</span>
        {call.commit && (
          <code style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>{call.commit}</code>
        )}
        <span className="flex-1" />
        {phase === 'reverted' ? (
          <span style={{ color: 'var(--color-text-faint)' }} data-testid="change-reverted">
            reverted
          </span>
        ) : (
          canRevert && (
            <button
              type="button"
              onClick={() => void revert()}
              disabled={phase === 'working'}
              className="flex items-center gap-1 disabled:opacity-50"
              style={{ color: 'var(--color-cyan-light)' }}
              data-testid="change-revert"
              title="git revert this commit"
            >
              <Undo2 size={11} aria-hidden />
              {phase === 'working' ? 'Reverting…' : 'Revert'}
            </button>
          )
        )}
      </div>
      {phase === 'failed' && (
        <p className="px-3 pb-1 text-xs" style={{ color: '#fbbf24' }} data-testid="change-revert-failed">
          {failure}
        </p>
      )}
      {call.diff && (
        <pre
          className="text-[10.5px] leading-snug"
          style={{
            fontFamily: 'var(--font-mono)',
            color: 'var(--color-text-muted)',
            borderTop: '1px solid var(--color-border-subtle)',
            padding: '6px 8px',
            margin: 0,
            maxHeight: 320,
            overflow: 'auto',
            overscrollBehavior: 'contain',
            whiteSpace: 'pre',
          }}
          data-testid="change-diff"
        >
          {lines.map((line, i) => (
            <span key={i} style={{ color: lineColor(line), display: 'block' }}>
              {line}
            </span>
          ))}
        </pre>
      )}
    </div>
  );
}
