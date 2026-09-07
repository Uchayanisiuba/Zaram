/**
 * Work's toolbar: find it, arrange it, choose how dense it looks.
 *
 * **What this replaced, and why.** Work filtered through two wrapping rows of
 * chips — one per project, one per type — and showed the result as a single
 * flat list ordered by date, with no way to search it, no way to arrange it,
 * and no headings. That is fine for nine files and unusable at two hundred,
 * which is where a surface for everything you have ever made ends up. It also
 * had a specific failure at the top: projects are unbounded, so the project row
 * grows without limit and pushes the type row off the fold.
 *
 * The shape here is the one every mature files view has converged on — search,
 * arrange, density, in that order, on one line — and the convergence is the
 * argument. `CLAUDE.md` asks for *density over animation on any surface used
 * daily* and for the primary path to stay untechnical; a familiar toolbar is
 * both, and a novel one would spend the user's attention on learning the
 * furniture.
 *
 * **A select for projects, chips for types.** Not a style preference: the type
 * list is closed and short — `KIND_LABELS` has seven entries and adding one is
 * a compile error somewhere — so chips show every option and its count at once,
 * which is what makes an empty filter say so before it is clicked. Projects are
 * the user's own strings and there can be any number, so the same treatment
 * would be a control that reflows the page as work accumulates.
 */
import { LayoutGrid, List, Search, X } from 'lucide-react';

import { KIND_LABELS, type ArtifactKind } from '@/services/artifactsClient';

import {
  GROUP_LABELS,
  SORT_LABELS,
  type GroupBy,
  type SortBy,
} from './organise';

/** How the listing is drawn. `auto` lets the contents decide — see `WorkView`. */
export type ViewMode = 'auto' | 'list' | 'grid';

const selectStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-border-subtle)',
  color: 'var(--color-text-muted)',
  borderRadius: 8,
  padding: '5px 8px',
  fontSize: 11,
};

function Chip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-[11px] transition-colors hover:bg-white/5"
      style={{
        border: `1px solid ${active ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
        background: active ? 'rgba(255,255,255,0.08)' : 'transparent',
        color: active ? 'var(--color-text)' : 'var(--color-text-muted)',
      }}
    >
      {label}
      {/* Live, so an empty filter says so before it is clicked. */}
      <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.6 }}>{count}</span>
    </button>
  );
}

export interface WorkToolbarProps {
  query: string;
  onQuery: (q: string) => void;

  project: string;
  projects: Array<{ id: string; count: number }>;
  onProject: (id: string) => void;

  kind: ArtifactKind | 'all';
  /** Counts for every type under the current project filter, including zeros. */
  kindCounts: Record<ArtifactKind, number>;
  totalInProject: number;
  onKind: (k: ArtifactKind | 'all') => void;

  groupBy: GroupBy;
  onGroupBy: (g: GroupBy) => void;
  sortBy: SortBy;
  onSortBy: (s: SortBy) => void;

  view: ViewMode;
  onView: (v: ViewMode) => void;
  /** What `auto` currently resolves to, so the toggle can show which of the two
   *  is actually in effect rather than leaving both unlit. A control that does
   *  not report the state it governs is the invented-value rule inverted. */
  resolvedView: 'list' | 'grid';
}

export default function WorkToolbar({
  query,
  onQuery,
  project,
  projects,
  onProject,
  kind,
  kindCounts,
  totalInProject,
  onKind,
  groupBy,
  onGroupBy,
  sortBy,
  onSortBy,
  view,
  onView,
  resolvedView,
}: WorkToolbarProps) {
  const kinds = Object.keys(KIND_LABELS) as ArtifactKind[];

  return (
    <div className="px-8 pb-3 pt-1 flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="relative flex-1" style={{ minWidth: 180 }}>
          <span className="sr-only">Search your work</span>
          <Search
            size={13}
            aria-hidden
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--color-text-faint)' }}
          />
          <input
            type="search"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            // Names what is searched, because "Search" alone would suggest
            // filenames and the conversation is the thing people remember.
            placeholder="Search by name, conversation or project"
            className="w-full rounded-lg py-1.5 pl-8 pr-7 text-xs"
            style={{
              background: 'transparent',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text)',
            }}
          />
          {query && (
            <button
              type="button"
              onClick={() => onQuery('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 hover:bg-white/10"
              style={{ color: 'var(--color-text-faint)' }}
            >
              <X size={11} />
            </button>
          )}
        </label>

        <select
          aria-label="Group by"
          value={groupBy}
          onChange={(e) => onGroupBy(e.target.value as GroupBy)}
          style={selectStyle}
        >
          {(Object.keys(GROUP_LABELS) as GroupBy[]).map((g) => (
            <option key={g} value={g}>
              Group by {GROUP_LABELS[g].toLowerCase()}
            </option>
          ))}
        </select>

        <select
          aria-label="Sort by"
          value={sortBy}
          onChange={(e) => onSortBy(e.target.value as SortBy)}
          style={selectStyle}
        >
          {(Object.keys(SORT_LABELS) as SortBy[]).map((s) => (
            <option key={s} value={s}>
              {SORT_LABELS[s]}
            </option>
          ))}
        </select>

        {/* Density. Two buttons rather than one that toggles, so the current
            state is visible without being pressed — and so `auto` has
            somewhere to land: pressing the one already in effect returns the
            choice to the contents rather than doing nothing. */}
        <div
          role="group"
          aria-label="How the list is shown"
          className="flex shrink-0 items-center rounded-lg overflow-hidden"
          style={{ border: '1px solid var(--color-border-subtle)' }}
        >
          {([
            ['list', List, 'Show as a list'],
            ['grid', LayoutGrid, 'Show as a grid'],
          ] as const).map(([mode, Icon, label]) => {
            const on = resolvedView === mode;
            return (
              <button
                key={mode}
                type="button"
                aria-label={label}
                aria-pressed={on}
                title={label}
                onClick={() => onView(view === mode ? 'auto' : mode)}
                className="p-1.5 transition-colors hover:bg-white/5"
                style={{
                  background: on ? 'rgba(255,255,255,0.08)' : 'transparent',
                  color: on ? 'var(--color-text)' : 'var(--color-text-faint)',
                }}
              >
                <Icon size={13} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <select
          aria-label="Project"
          value={project}
          onChange={(e) => onProject(e.target.value)}
          style={{ ...selectStyle, maxWidth: 200 }}
        >
          <option value="all">All projects</option>
          {projects.map((p) => (
            // Not prettified — a slug turned into a title is a value nobody
            // entered, and this surface does not invent any.
            <option key={p.id} value={p.id}>
              {p.id} ({p.count})
            </option>
          ))}
        </select>

        {/* One line that scrolls rather than a block that wraps. The row above
            is fixed height, so the listing below starts at the same place
            whatever is installed — a filter bar that changes height as work
            accumulates makes the surface feel unstable on exactly the machines
            that have the most in it. */}
        <div
          className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto"
          style={{ scrollbarWidth: 'thin' }}
        >
          <Chip
            label="All types"
            count={totalInProject}
            active={kind === 'all'}
            onClick={() => onKind('all')}
          />
          {kinds.map((k) => (
            <Chip
              key={k}
              label={KIND_LABELS[k]}
              count={kindCounts[k] ?? 0}
              active={kind === k}
              onClick={() => onKind(k)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
