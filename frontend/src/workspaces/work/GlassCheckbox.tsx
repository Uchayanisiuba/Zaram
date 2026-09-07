/**
 * A checkbox that belongs to this interface.
 *
 * A native `<input type="checkbox">` is painted by the operating system, so on
 * Windows it is an opaque white square — the one bright element on a dark glass
 * surface, and the first thing the eye lands on in a list where the filenames
 * are the point. `accentColor` only tints the *checked* fill; the unchecked box
 * stays the platform's own, which is exactly the state most rows are in.
 *
 * **It is still a real checkbox.** The input is present, focusable and
 * announced — moved out of sight rather than replaced. Building the control out
 * of a `div` and a click handler is the version of this that looks identical
 * and is unusable with a keyboard, and this surface is a list where selecting
 * with the keyboard is the fast path.
 *
 * The click behaviour and its feedback are unchanged: the same toggle, the same
 * moment, the same tick appearing. Only the box it is drawn in moved from the
 * platform's palette to this one.
 */
import { Check } from 'lucide-react';

export interface GlassCheckboxProps {
  checked: boolean;
  onChange: () => void;
  /** Required. Every one of these sits beside a filename or a heading whose
   *  text is not the checkbox's own name, so there is nothing for a screen
   *  reader to infer it from. */
  label: string;
  /** Slightly larger for a group heading than for a row, because the heading's
   *  box has no filename beside it to give it scale. */
  size?: number;
}

export default function GlassCheckbox({
  checked,
  onChange,
  label,
  size = 14,
}: GlassCheckboxProps) {
  return (
    <label
      className="relative inline-flex shrink-0 cursor-pointer items-center justify-center"
      style={{ width: size, height: size }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        aria-label={label}
        // Not `display: none` and not `visibility: hidden`: both remove the
        // input from the accessibility tree and from the tab order, which is
        // the whole thing this component is being careful to keep. It is
        // present, on top of the box, and transparent — so a pointer lands on
        // the real control and focus has somewhere to go.
        className="absolute inset-0 m-0 cursor-pointer opacity-0"
        style={{ width: size, height: size }}
      />
      <span
        aria-hidden
        className="pointer-events-none flex items-center justify-center rounded transition-colors"
        style={{
          width: size,
          height: size,
          // The same glass the panels and chips on this surface are made of,
          // and the same accent the selected row is tinted with, so ticking a
          // box and the row lighting up read as one event.
          background: checked ? 'rgba(129,140,248,0.22)' : 'var(--color-glass)',
          border: `1px solid ${checked ? 'var(--color-indigo-light)' : 'var(--color-border-subtle)'}`,
          backdropFilter: 'blur(6px)',
          color: 'var(--color-indigo-light)',
        }}
      >
        {checked && <Check size={size - 4} strokeWidth={3} />}
      </span>
    </label>
  );
}
