/**
 * The look of one control in the row under the composer.
 *
 * The row holds up to five of them in a panel that can be narrow. Without
 * `whitespace-nowrap` each one shrank and broke inside itself — "Prefer" over
 * "local", "Page" over "check on" — so the row read as a column of fragments.
 * A chip that never breaks moves to the next line whole instead, and the pill
 * edge is what keeps two of them from reading as one phrase once the dot
 * separators are gone (a dot left at the start of a wrapped line separates
 * nothing).
 */
export const BAR_CHIP =
  'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 ' +
  'border border-white/[0.06] text-xs text-slate-400 transition-colors ' +
  'hover:text-slate-200 hover:bg-white/[0.04]';
