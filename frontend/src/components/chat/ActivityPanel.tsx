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
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { Check, CircleAlert, Clock, X } from 'lucide-react';
import { useLayoutStore } from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useViewport } from '@/hooks/useViewport';
import type { ChatToolCall } from '@/stores/chatStore';

const VERDICTS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  allow: { Icon: Check, color: 'var(--color-text-faint)', label: 'ran' },
  confirm: { Icon: Clock, color: 'var(--color-amber, #d97706)', label: 'waiting on you' },
  refuse: { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: 'did not run' },
};

const UNKNOWN = { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: '' };

export default function ActivityPanel({
  calls,
  onClose,
}: {
  calls: ChatToolCall[];
  onClose: () => void;
}) {
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
          <span className="text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
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

        <ol className="flex-1 overflow-y-auto px-4 py-3">
          {calls.map((call, i) => {
            const { Icon, color, label } = VERDICTS[call.verdict] ?? UNKNOWN;
            return (
              <li
                key={`${call.server}/${call.tool}/${i}`}
                className="flex items-start gap-2 py-1.5"
                data-verdict={call.verdict}
                style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
              >
                <span
                  className="w-5 shrink-0 pt-px text-right text-[10px] tabular-nums"
                  style={{ color: 'var(--color-text-faint)' }}
                >
                  {i + 1}
                </span>
                <Icon size={12} className="mt-0.5 shrink-0" style={{ color }} aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 text-[11px]">
                    <span
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}
                    >
                      {call.server}/{call.tool}
                    </span>
                    {label && (
                      <span style={{ color: 'var(--color-text-faint)' }}>{label}</span>
                    )}
                  </div>
                  {/* What it was aimed at. Rendered as text — it is written by
                      the model, and `call_target` has already bounded it. */}
                  {call.target && (
                    <div
                      className="mt-0.5 break-all text-[11px]"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
                      data-testid="call-target"
                    >
                      {call.target}
                    </div>
                  )}
                  {call.reason && call.verdict !== 'allow' && (
                    <div className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
                      {call.reason}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        {/* Said once, at the bottom, rather than as a column that would have to
            be empty. Reading is the whole capability today. */}
        <div
          className="px-4 py-2 text-[11px]"
          style={{
            borderTop: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          Zaram read these. It does not edit files — every mutative tool is out
          of scope until v1.
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
