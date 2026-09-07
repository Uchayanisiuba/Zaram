/**
 * What is selected, and the one destructive thing Work can do with it.
 *
 * **Three states in one strip, never three strips.** Choosing, confirming and
 * having just done it are the same conversation at three moments, and giving
 * each its own bar would move the listing down the page twice while somebody is
 * aiming at a checkbox. The strip occupies the same line throughout.
 *
 * **Confirm is a step, not a dialog.** `CLAUDE.md` refuses the per-request
 * dialog as a pattern nobody opens twice — but that argument is about *repeated
 * consent for the same destination*, and this is the other case entirely: rule
 * 6 says tools confirm before acting, and the tier table names undo, confirm
 * and sandbox for anything mutative. A selection of forty files removed by a
 * mis-click is exactly what a confirm is for. It is inline rather than modal
 * because the thing being confirmed is on screen behind it, and a modal would
 * cover the list the user is checking.
 *
 * **The undo is offered, not merely possible.** The files are in a trash folder
 * either way, and that is the durable answer; this is the one that reaches
 * somebody who did not know there was a folder. It stays until the next action
 * rather than timing out — a countdown on the only visible route back turns a
 * recoverable mistake into a race.
 */
import { RotateCcw, Trash2, X } from 'lucide-react';

export type SelectionPhase = 'choosing' | 'confirming' | 'removed';

export interface SelectionBarProps {
  phase: SelectionPhase;
  /** How many are selected, or — after a removal — how many went. */
  count: number;
  /** The backend's own sentence about what a removal touches. Rendered as it
   *  stands so the wording tracks the behaviour. */
  note: string | null;
  /** Files that could not be removed or put back, with the reason. Never
   *  swallowed: a partial result the user cannot see is a partial result they
   *  will discover by missing something. */
  skipped: Array<{ id: string; reason: string }>;
  busy: boolean;

  onSelectAll: () => void;
  onClear: () => void;
  onAskToRemove: () => void;
  onConfirmRemove: () => void;
  onCancelRemove: () => void;
  onUndo: () => void;
  onDismiss: () => void;
}

const strip: React.CSSProperties = {
  border: '1px solid var(--color-border-subtle)',
  background: 'var(--color-glass)',
  borderRadius: 10,
};

function Action({
  children,
  onClick,
  disabled,
  danger,
  primary,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] transition-colors hover:bg-white/5 disabled:opacity-40"
      style={{
        border: `1px solid ${danger ? 'var(--color-red, #f87171)' : 'var(--color-border-subtle)'}`,
        background: primary ? 'rgba(255,255,255,0.06)' : 'transparent',
        color: danger ? 'var(--color-red, #f87171)' : 'var(--color-text)',
      }}
    >
      {children}
    </button>
  );
}

export default function SelectionBar({
  phase,
  count,
  note,
  skipped,
  busy,
  onSelectAll,
  onClear,
  onAskToRemove,
  onConfirmRemove,
  onCancelRemove,
  onUndo,
  onDismiss,
}: SelectionBarProps) {
  const files = `${count} ${count === 1 ? 'file' : 'files'}`;

  return (
    <div
      // Announced, because the strip appears in response to a checkbox that is
      // some distance away from it and a screen reader user would otherwise
      // tick a box and be told nothing.
      role="status"
      className="mx-8 mb-3 flex flex-col gap-1.5 px-3 py-2"
      style={strip}
    >
      <div className="flex flex-wrap items-center gap-2">
        {phase === 'choosing' && (
          <>
            <span className="text-[11px]" style={{ color: 'var(--color-text)' }}>
              {files} selected
            </span>
            <span className="flex-1" />
            <Action onClick={onSelectAll}>Select everything shown</Action>
            <Action onClick={onClear}>
              <X size={11} />
              Clear
            </Action>
            <Action onClick={onAskToRemove} danger>
              <Trash2 size={11} />
              Remove
            </Action>
          </>
        )}

        {phase === 'confirming' && (
          <>
            <span className="text-[11px]" style={{ color: 'var(--color-text)' }}>
              {/* Says what will happen, not "are you sure". A confirmation that
                  asks for certainty without describing the act is a dialog
                  people learn to click through. */}
              Remove {files}? They move to a trash folder beside your work — nothing is
              deleted, and you can put them back.
            </span>
            <span className="flex-1" />
            <Action onClick={onCancelRemove} disabled={busy}>
              Cancel
            </Action>
            <Action onClick={onConfirmRemove} disabled={busy} danger primary>
              <Trash2 size={11} />
              {busy ? 'Removing…' : `Remove ${files}`}
            </Action>
          </>
        )}

        {phase === 'removed' && (
          <>
            <span className="text-[11px]" style={{ color: 'var(--color-text)' }}>
              Removed {files}.
            </span>
            <span className="flex-1" />
            <Action onClick={onUndo} disabled={busy} primary>
              <RotateCcw size={11} />
              {busy ? 'Putting back…' : 'Undo'}
            </Action>
            <Action onClick={onDismiss} disabled={busy}>
              <X size={11} />
              Dismiss
            </Action>
          </>
        )}
      </div>

      {phase === 'removed' && note && (
        <p className="text-[11px] leading-snug" style={{ color: 'var(--color-text-secondary)', maxWidth: '72ch' }}>
          {note}
        </p>
      )}

      {skipped.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {skipped.map((s) => (
            <li key={s.id} className="text-[11px]" style={{ color: 'var(--color-amber)' }}>
              {s.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
