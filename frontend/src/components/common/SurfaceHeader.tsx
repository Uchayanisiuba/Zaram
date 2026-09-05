/**
 * The title block every surface wears.
 *
 * **It was six hand-rolled copies of nearly the same thing, and they drifted.**
 * Measured before this existed: `px-8 pt-6 pb-3` on Work and Activity against
 * `pb-4` on Memory, Knowledge and Settings; and Project's `<h1>` carried
 * neither `font-display` nor an explicit colour, so one surface in six rendered
 * its title in a different typeface from the other five. None of that was a
 * decision — it is what six near-copies become.
 *
 * This is the same fix, and the same reasoning, as `REGISTRY` in
 * `runtime/shortcuts`: the navigation list was restated in four components and
 * silently lost Activity. One declaration cannot drift from itself.
 *
 * Deliberately not a layout. It owns the header row only — the padding above
 * the first content, the icon, the title and the optional line under it —
 * because a component that also owned the scroll container would have to know
 * what each surface puts inside one, and that is where the copies start again.
 *
 * The surfaces are not meant to look like the landing, and this does not try
 * to make them. The landing is the shell — orb, orbit, no chrome — and these
 * are dense working screens. What they should share is a system, not a look.
 */
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface SurfaceHeaderProps {
  /**
   * The surface's icon.
   *
   * Three surfaces carried one and three did not, which is half of why the set
   * read as assembled rather than designed. Callers pass the icon the *left
   * rail* already uses for that node, so the thing you clicked and the thing
   * you arrived at are the same mark.
   */
  icon: LucideIcon;
  title: string;
  /** Sits beside the title — a count, a state. Not an action. */
  meta?: ReactNode;
  /** One line under the title. Optional; most surfaces need none. */
  description?: string;
  /** Actions, right-aligned on the title row. */
  children?: ReactNode;
  /** Defaults to the accent most surfaces already used. */
  iconColor?: string;
}

export default function SurfaceHeader({
  icon: Icon,
  title,
  meta,
  description,
  children,
  iconColor = 'var(--color-cyan-light)',
}: SurfaceHeaderProps) {
  return (
    <div
      className="px-8 pt-6 pb-4 flex items-start gap-3 shrink-0"
      data-testid="surface-header"
    >
      <Icon size={20} style={{ color: iconColor }} className="mt-0.5 shrink-0" aria-hidden />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-3">
          <h1
            className="text-lg font-semibold"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
          >
            {title}
          </h1>
          {meta}
        </div>
        {description && (
          <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {description}
          </p>
        )}
      </div>

      {children && <div className="flex items-center gap-2 shrink-0">{children}</div>}
    </div>
  );
}
