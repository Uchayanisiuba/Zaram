/**
 * A draggable division between two panels.
 *
 * Shared by every adjustable boundary in the shell so they behave identically:
 * same hit area, same affordance, same keyboard behaviour, same reset.
 *
 * The visible line is 1px but the grab area is 9px. A 1px drag target is a
 * well-known usability failure — the divider should look thin and grab thick.
 *
 * Keyboard accessible deliberately. A resize handle that only responds to a
 * pointer is unusable for anyone who cannot use one, and `role="separator"`
 * with a value is the standard that assistive technology already understands.
 */
import { useCallback, useRef } from 'react';

export interface ResizeHandleProps {
  /** Which side of the handle the panel being resized sits on. */
  panelSide: 'left' | 'right';
  /** New size from a pointer position. Receives clientX. */
  onResize: (clientX: number) => void;
  /** Nudge by a step, in pixels. Positive always means "wider". */
  onNudge: (deltaPx: number) => void;
  /** Double-click and Home restore the default. */
  onReset: () => void;
  /** Reported to assistive technology, and used for the value text. */
  value: number;
  min: number;
  max: number;
  label: string;
  /** Called with true on grab, false on release. */
  onResizingChange?: (resizing: boolean) => void;
  /** Position override. Needed where the panel clips its overflow, so the
   *  handle has to be positioned against the viewport instead of the panel. */
  style?: React.CSSProperties;
}

const STEP = 16;
const STEP_LARGE = 64;

export default function ResizeHandle({
  panelSide,
  onResize,
  onNudge,
  onReset,
  value,
  min,
  max,
  label,
  onResizingChange,
  style,
}: ResizeHandleProps) {
  const dragging = useRef(false);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      dragging.current = true;
      onResizingChange?.(true);
      // Capture means the drag keeps working when the pointer outruns the
      // handle, which it always does.
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [onResizingChange],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return;
      onResize(e.clientX);
    },
    [onResize],
  );

  const endDrag = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return;
      dragging.current = false;
      onResizingChange?.(false);
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    },
    [onResizingChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      // Arrow direction is physical: left arrow moves the divider left. Whether
      // that widens or narrows depends on which side the panel is on.
      const toward = panelSide === 'right' ? -1 : 1;
      const step = e.shiftKey ? STEP_LARGE : STEP;

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          onNudge(step * toward);
          break;
        case 'ArrowRight':
          e.preventDefault();
          onNudge(-step * toward);
          break;
        case 'Home':
        case 'Enter':
          e.preventDefault();
          onReset();
          break;
        default:
          break;
      }
    },
    [onNudge, onReset, panelSide],
  );

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={Math.round(min)}
      aria-valuemax={Math.round(max)}
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onDoubleClick={onReset}
      onKeyDown={handleKeyDown}
      className="group absolute top-0 h-full z-50 flex items-center justify-center"
      style={{
        // Visible line is 1px; the grab area is wider so it can be hit.
        width: 9,
        [panelSide === 'right' ? 'left' : 'right']: -4,
        cursor: 'col-resize',
        touchAction: 'none',
        ...style,
      }}
    >
      {/* The line itself. Brightens on hover and focus so the affordance is
          discoverable without adding permanent visual noise. */}
      <div
        className="h-full transition-colors group-hover:bg-[var(--color-indigo)] group-focus-visible:bg-[var(--color-indigo)]"
        style={{ width: 1, background: 'var(--color-border-subtle)' }}
      />
    </div>
  );
}
