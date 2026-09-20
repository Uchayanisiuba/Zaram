/**
 * Everything one exchange did, brought forward — the task, and what it read.
 *
 * Asked for on 7 September 2026 against Claude Code's *Background tasks* panel,
 * which is hidden until something is running and opens to the individual task.
 * Two things about that reference had to change on the way in.
 *
 * **It is the panel this product already has, not a new one.** `ArtifactPreview`,
 * `CitationPanel` and `CodePreviewPanel` all come forward over the orb with the
 * background blurred, and `CodePreviewPanel`'s own note gives the reason — *"one
 * way to bring something forward is a thing users learn once."* A dock on the
 * right would be a second mechanism for the same job and a seventh surface in a
 * navigation that is deliberately six.
 *
 * **It shows what was read, never what was written.** Claude Code lists files
 * being edited; Zaram's code pack is `list_files`, `read_lines` and
 * `search_code`, and `CLAUDE.md` holds every mutative tool out of scope until
 * v1 ships. A column headed "edited" would be a promise the product cannot
 * keep, and the person reading it would believe their repository had been
 * changed.
 *
 * **The target is the point.** That a tool ran is not a checkable claim;
 * `readiness.py:156-181` is, and it is why the code chunker keeps line ranges
 * at all. `ToolCalls` deliberately leaves targets out of the conversation —
 * a wall of line numbers under a reply tells a reader nothing they wanted —
 * so this is where they belong: asked for, one exchange at a time.
 *
 * A target is **model-written text**. It arrives bounded by `call_target` and
 * is rendered as text, never as markup: the tool-description rule applied one
 * layer along, since nothing a model writes may widen what a surface does.
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { Check, CircleAlert, Clock, X } from 'lucide-react';
import { useLayoutStore } from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useViewport } from '@/hooks/useViewport';
import type { ChatToolCall } from '@/stores/chatStore';
import StepOutput from './StepOutput';
import ChangeCard from './ChangeCard';
import AppCard from './AppCard';
import { fetchEgressForStep, type EgressEntry } from '@/services/egressClient';
import { DID } from '@/lib/workingLine';

const VERDICTS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  allow: { Icon: Check, color: 'var(--color-text-faint)', label: 'ran' },
  confirm: { Icon: Clock, color: 'var(--color-amber, #d97706)', label: 'waiting on you' },
  refuse: { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: 'did not run' },
};

const UNKNOWN = { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: '' };

/**
 * What one step sent off this machine, under its row — `docs/PLAN.md` C2.
 *
 * Asked of the log by the step's mark, never inferred from timing. Three
 * states and each is said: not yet read, nothing recorded (a real answer —
 * the gate logs every request), and the entries themselves with host,
 * bytes and decision. A call with no mark (an older history) shows nothing.
 */
function StepEgress({ stepId }: { stepId: string }) {
  const [entries, setEntries] = useState<EgressEntry[] | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    fetchEgressForStep(stepId)
      .then((found) => live && setEntries(found))
      .catch(() => live && setEntries(null));
    return () => {
      live = false;
    };
  }, [stepId]);
  if (entries === undefined) return null;
  if (entries === null) {
    return (
      <div className="trace-line">
        <span className="trace-k" />
        <span className="trace-v role-dim">The egress log could not be read.</span>
      </div>
    );
  }
  if (entries.length === 0) {
    return (
      <div className="trace-line" data-testid="step-egress-none">
        <span className="trace-k" />
        <span className="trace-v role-ok">Nothing left this device for this step.</span>
      </div>
    );
  }
  return (
    <ul className="mt-1 flex flex-col gap-0.5" data-testid="step-egress">
      {entries.map((e) => (
        <li key={e.id} className="trace-line">
          <span className="trace-k">{e.decision === 'allowed' ? 'sent' : e.decision}</span>
          <span className="trace-v" style={{ color: 'var(--color-text)' }}>
            {e.host}
          </span>
          <span className="role-dim">
            · {e.bytes} bytes{e.decision !== 'allowed' && e.reason ? ` · ${e.reason}` : ''}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function ActivityPanel({
  calls,
  onClose,
  focus,
}: {
  calls: ChatToolCall[];
  onClose: () => void;
  /** The call the person opened this from, scrolled to and opened out —
   *  its output, its change with Revert, what it sent. Absent when opened
   *  from the folded summary, where every call is listed and none is open. */
  focus?: ChatToolCall | null;
}) {
  // A row can be opened out from inside the panel too. Seen 20 September
  // 2026: once the rows in the conversation fold, their *open* goes with
  // them, and the panel reached from the summary listed every call with
  // none of them openable — so what a step *sent* was reachable only while
  // it was still running. The person's pick wins over the row this was
  // opened from; picking the same row again closes it.
  const [picked, setPicked] = useState<ChatToolCall | null>(null);
  const opened = picked ?? focus ?? null;
  const focused = useRef<HTMLLIElement | null>(null);
  useEffect(() => {
    focused.current?.scrollIntoView?.({ block: 'center' });
  }, [focus]);
  // The panel occupies the orb's half of the window, derived from the same
  // fraction the conversation uses so the two cannot disagree when the
  // divider is dragged. Copied in shape from `CodePreviewPanel` because they
  // are the same panel in two places, not two designs.
  const context = useChatModeStore((s) => s.context);
  const landingFraction = useLayoutStore((s) => s.chatFraction);
  const workspaceFraction = useLayoutStore((s) => s.chatFractionWorkspace);
  const chatFraction = context === 'workspace' ? workspaceFraction : landingFraction;
  const { width: viewportWidth } = useViewport();
  const panelWidth = viewportWidth * chatFraction;

  // Escape closes it, bound to the window because focus is usually in the
  // conversation behind. The same reason `CodePreviewPanel` binds it there.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Into `document.body`, so a blurred ancestor cannot become the containing
  // block for these fixed measurements — the failure that once collapsed the
  // artifact panel to a sliver.
  return createPortal(
    <motion.div
      className="fixed top-0 bottom-0 left-0 z-[90] flex items-center justify-center p-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
      style={{
        right: panelWidth,
        background: 'rgba(2,6,23,0.55)',
        backdropFilter: 'blur(24px) saturate(1.4)',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="What this reply did"
      data-testid="activity-panel"
    >
      <motion.div
        className="flex flex-col overflow-hidden rounded-2xl"
        style={{
          width: '100%',
          maxWidth: 880,
          height: 'min(80vh, 100%)',
          background: 'var(--color-glass)',
          border: '1px solid var(--color-border)',
        }}
        initial={{ scale: 0.98, y: 8 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ duration: 0.22 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          className="flex items-center gap-3 px-4 py-3"
          style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
        >
          <span className="text-sm" style={{ color: 'var(--color-text)' }}>
            What this reply did
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
            {calls.length === 1 ? '1 tool call' : `${calls.length} tool calls`}
          </span>
          <div className="flex-1" />
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-slate-400 hover:bg-white/5 hover:text-slate-200"
          >
            <X size={14} />
          </button>
        </div>

        {/* The site's trace, one call per line: a dim key column carrying the
            verb, the target as the value, and the verdict in a role colour —
            dim for ran, amber for anything that needs the person. */}
        <ol className="trace flex-1 overflow-y-auto px-4 py-3">
          {calls.map((call, i) => {
            const { Icon, color, label } = VERDICTS[call.verdict] ?? UNKNOWN;
            // A plan step carries its own phrase; a tool call is looked up.
            const verb = call.label ?? DID[call.tool] ?? `${call.server}/${call.tool}`;
            const isFocus = opened != null && call === opened;
            return (
              <li
                key={`${call.server}/${call.tool}/${i}`}
                ref={isFocus ? focused : undefined}
                className="flex items-start gap-2 py-1"
                data-verdict={call.verdict}
                data-focus={isFocus ? 'true' : undefined}
                data-testid="panel-call"
                onClick={() => setPicked(isFocus ? null : call)}
                style={{
                  borderBottom: '1px solid var(--color-border-subtle)',
                  cursor: 'pointer',
                  ...(isFocus ? { background: 'rgba(255,255,255,.03)' } : {}),
                }}
              >
                <span className="w-5 shrink-0 text-right tabular-nums role-dim">{i + 1}</span>
                <Icon size={12} className="mt-1 shrink-0" style={{ color }} aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="trace-line">
                    <span className="trace-k" title={`${call.server}/${call.tool}`}>{verb}</span>
                    {/* What it was aimed at. Rendered as text — it is written by
                        the model, and `call_target` has already bounded it. */}
                    {call.target ? (
                      <span className="trace-v" style={{ color: 'var(--color-text)' }} data-testid="call-target">
                        {call.target}
                      </span>
                    ) : (
                      <span className="trace-v role-dim">{call.server}/{call.tool}</span>
                    )}
                    {label && (
                      <span className={call.verdict === 'allow' ? 'role-dim' : 'role-warn'}>· {label}</span>
                    )}
                  </div>
                  {call.reason && call.verdict !== 'allow' && (
                    <div className="trace-line">
                      <span className="trace-k" />
                      <span className="trace-v role-warn">{call.reason}</span>
                    </div>
                  )}
                  {/* What came back, in its own scrolling pane, so a run that
                      read four files is four rows and any one can be checked
                      without unrolling the rest. */}
                  {call.output && <StepOutput text={call.output} />}
                  {/* The change and the app, on the step that made them,
                      with Revert where it belongs; and what the step sent,
                      only for the step opened out — one query, not one per
                      row. */}
                  {isFocus && call.diff ? <ChangeCard call={call} /> : null}
                  {isFocus && (call.image || call.appUrl) ? <AppCard call={call} /> : null}
                  {isFocus && call.stepId ? <StepEgress stepId={call.stepId} /> : null}
                </div>
              </li>
            );
          })}
        </ol>

        {/* Said once, at the bottom, rather than as a column that would have to
            be empty. Reading is the whole capability today. */}
        <div
          className="px-4 py-2 text-xs"
          style={{
            borderTop: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          Every change a call made has its diff and a Revert under the reply;
          anything a call sent off this machine is in the egress log.
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
