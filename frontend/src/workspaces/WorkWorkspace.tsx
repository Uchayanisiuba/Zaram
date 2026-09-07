/**
 * Work — where output lives.
 *
 * It exists because a navigation made only of Memory, Knowledge and Activity is
 * entirely about the system and holds nothing the user made. Nobody pays for a
 * memory browser. Memory matters because it is memory *of work*.
 *
 * Which is why every row carries the conversation that produced it. Strip that
 * and this is a file browser, and the operating system already ships one.
 *
 * Reads real artifacts from the backend. The sample module this used to import
 * is deleted — if nothing has been generated, this surface says so and shows
 * how to make something, which is a truthful empty state rather than a
 * convincing populated lie.
 *
 * **The layout, rebuilt 7 September 2026.** It was two wrapping rows of filter
 * chips over one flat date-ordered list with no headings, no search and no way
 * to arrange it. That is fine for nine files and unusable at two hundred, which
 * is where a surface holding everything a person has ever made ends up — and it
 * had a specific failure at the top, since the project chip row is unbounded
 * and pushes the type row off the fold as work accumulates.
 *
 * Now: a toolbar (search · group · sort · density), a single-line type filter,
 * aligned columns, and **grouped rows under sticky headings**. That is the
 * shape every mature files view has converged on, and the convergence is the
 * argument: a novel arrangement would spend the user's attention on learning
 * the furniture instead of on finding their invoice.
 *
 * **Grouping is not a folder tree, and the difference is the whole reason it is
 * allowed here.** `CLAUDE.md` refuses a hierarchy — *"a second organising
 * system competing with the one that is the product"*, and *"if a tree is
 * needed to find your own work then recall has failed"*. A group is not a
 * place: nothing is ever filed anywhere, a file is in one bucket under Type and
 * a different one under Date, and switching the control re-cuts the same set.
 * Nobody is asked in advance where anything goes, which is rule 7h.
 *
 * **And it is still not a file browser.** Every row carries the conversation
 * that produced it, the search looks *through* that conversation, and the
 * detail panel opens it. Strip those and the operating system already ships
 * this screen.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import {
  AlertCircle,
  BarChart3,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  ImageIcon,
  MessageSquare,
  Presentation,
  Quote,
  Receipt,
  RefreshCw,
  UserRound,
  X,
} from 'lucide-react';

import ArtifactPreview from '@/components/ArtifactPreview';
import SurfaceHeader from '@/components/common/SurfaceHeader';
import { useArtifactImage } from '@/hooks/useArtifactImage';
import {
  KIND_LABELS,
  PICTORIAL_KINDS,
  downloadArtifact,
  getArtifact,
  listArtifacts,
  type Artifact,
  type ArtifactKind,
} from '@/services/artifactsClient';
import WorkToolbar, { type ViewMode } from './work/WorkToolbar';
import { group, search, type GroupBy, type SortBy } from './work/organise';

// The second copy of this map, and the reason `ArtifactKind` is a union rather
// than a string: adding `deck` and `cv` to it broke both copies at compile
// time, which is how a kind that had shipped on the backend for weeks with no
// icon here was found at all.
const KIND_ICON: Record<ArtifactKind, React.ReactNode> = {
  invoice: <Receipt size={16} />,
  document: <FileText size={16} />,
  spreadsheet: <FileSpreadsheet size={16} />,
  chart: <BarChart3 size={16} />,
  deck: <Presentation size={16} />,
  cv: <UserRound size={16} />,
  image: <ImageIcon size={16} />,
};

// One accent per kind, drawn from the existing token set. No new hues.
const KIND_COLOUR: Record<ArtifactKind, string> = {
  invoice: 'var(--color-emerald)',
  document: 'var(--color-cyan-light)',
  spreadsheet: 'var(--color-amber)',
  chart: 'var(--color-violet)',
  deck: 'var(--color-indigo-light)',
  cv: 'var(--color-cyan-light)',
  image: 'var(--color-indigo-light)',
};

const relative = (seconds: number) => {
  const delta = Date.now() / 1000 - seconds;
  if (delta < 86400) return 'today';
  const days = Math.floor(delta / 86400);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? 'last month' : `${months} months ago`;
};

const bytes = (n: number) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

/** The project id as stored. Not prettified — a slug turned into a title is a
 *  value nobody entered, and this surface does not invent any. */
const projectLabel = (id: string) => id || 'No project';

/**
 * The columns, in one place, so the header and the rows cannot drift apart.
 *
 * A grid template rather than a flex row, which is the change that makes this
 * scannable: the previous layout right-aligned a two-line block per row, so
 * project and date sat at a different x on every row depending on how long the
 * filename was. Aligned columns are the whole reason a list view beats a stack
 * of cards for finding something.
 *
 * Project and size collapse on a narrow surface — Work is often open beside the
 * conversation, which takes a third of the width. The name and the conversation
 * never collapse: they are what the row is *for*.
 */
const ROW_GRID = 'minmax(0,1fr) 140px 96px 72px';

interface WorkWorkspaceProps {
  /** Leave Work and open the conversation. The shell owns that transition. */
  onOpenConversation?: () => void;
}

export default function WorkWorkspace({ onOpenConversation }: WorkWorkspaceProps) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<string>('all');
  const [kind, setKind] = useState<ArtifactKind | 'all'>('all');
  const [selected, setSelected] = useState<Artifact | null>(null);
  const [query, setQuery] = useState('');
  // Type is the default because it is the categorisation a person means when
  // they say their files are not organised — what a thing *is*, before when it
  // happened. Date is one control away for the days when recency is the
  // question.
  const [groupBy, setGroupBy] = useState<GroupBy>('type');
  const [sortBy, setSortBy] = useState<SortBy>('newest');
  const [view, setView] = useState<ViewMode>('auto');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Everything, then filtered here. The backend supports filters, but the
      // chips have to show counts for options the current filter excludes, and
      // one request beats a request per chip.
      const listing = await listArtifacts();
      setArtifacts(listing.artifacts);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your work');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const projects = useMemo(() => {
    const seen = new Map<string, number>();
    for (const a of artifacts) {
      if (a.project_id) seen.set(a.project_id, (seen.get(a.project_id) ?? 0) + 1);
    }
    return [...seen.entries()].map(([id, count]) => ({ id, count }));
  }, [artifacts]);

  const byProject = useMemo(
    () =>
      project === 'all' ? artifacts : artifacts.filter((a) => a.project_id === project),
    [artifacts, project],
  );

  const visible = useMemo(
    () => search(kind === 'all' ? byProject : byProject.filter((a) => a.kind === kind), query),
    [byProject, kind, query],
  );

  const groups = useMemo(
    () => group(visible, groupBy, sortBy),
    [visible, groupBy, sortBy],
  );

  // Whether this listing is entirely pictures, which is what earns the grid.
  // Computed from what is actually showing rather than from the filter, so
  // "all kinds" on a machine that has only ever generated images gets the grid
  // too — the density should follow the contents, not the control.
  const allPictures = useMemo(
    () => visible.length > 0 && visible.every((a) => PICTORIAL_KINDS.has(a.kind)),
    [visible],
  );

  // `auto` is what shipped before this toolbar existed and it stays the
  // default, because it is right almost always. What it was missing is a way
  // to disagree with it: a listing of forty pictures is sometimes a list of
  // names you want to read, and a listing of documents is sometimes worth
  // seeing as tiles. Pressing the mode already in effect returns the choice to
  // the contents.
  const resolvedView: 'list' | 'grid' =
    view === 'auto' ? (allPictures ? 'grid' : 'list') : view;

  const kindCounts = useMemo(() => {
    const counts = {} as Record<ArtifactKind, number>;
    for (const k of Object.keys(KIND_LABELS) as ArtifactKind[]) counts[k] = 0;
    for (const a of byProject) counts[a.kind] = (counts[a.kind] ?? 0) + 1;
    return counts;
  }, [byProject]);

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">
        <SurfaceHeader
          icon={FileText}
          title="Work"
          meta={
            <span
              className="text-xs"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
            >
              {loading ? 'loading…' : `${visible.length} of ${artifacts.length}`}
            </span>
          }
        >
          <button
            onClick={() => void load()}
            disabled={loading}
            aria-label="Refresh"
            className="p-1 rounded-md text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : undefined} />
          </button>
        </SurfaceHeader>

        {/* The filter block keeps the header's horizontal rhythm; the vertical
            padding above it now belongs to SurfaceHeader. */}
        <div className="px-8 pb-3">
          {error && (
            <div
              className="mt-3 flex items-start gap-2 rounded-lg px-3 py-2 text-[11px] leading-relaxed"
              style={{
                border: '1px solid var(--color-border-subtle)',
                background: 'var(--color-glass)',
                color: 'var(--color-text-muted)',
              }}
            >
              <AlertCircle
                size={13}
                className="mt-0.5 shrink-0"
                style={{ color: 'var(--color-amber)' }}
              />
              <span>
                {error}{' '}
                <button
                  onClick={() => void load()}
                  className="underline underline-offset-2"
                  style={{ color: 'var(--color-text)' }}
                >
                  Try again
                </button>
              </span>
            </div>
          )}

        </div>

        <WorkToolbar
          query={query}
          onQuery={setQuery}
          project={project}
          projects={projects}
          onProject={setProject}
          kind={kind}
          kindCounts={kindCounts}
          totalInProject={byProject.length}
          onKind={setKind}
          groupBy={groupBy}
          onGroupBy={setGroupBy}
          sortBy={sortBy}
          onSortBy={setSortBy}
          view={view}
          onView={setView}
          resolvedView={resolvedView}
        />

        <div className="flex-1 overflow-y-auto px-8 pb-8">
          {loading && artifacts.length === 0 ? (
            <LoadingState />
          ) : visible.length === 0 ? (
            <EmptyState
              filtered={artifacts.length > 0}
              onClear={() => {
                setProject('all');
                setKind('all');
                setQuery('');
              }}
            />
          ) : (
            <div className="flex flex-col gap-5">
              {/* The column header, rendered once above every group rather
                  than repeated per heading. Repeating it would turn a list
                  into a stack of tables, which is what a spreadsheet looks
                  like and not what a person scanning for one file needs.
                  List view only: a grid has no columns to name. */}
              {resolvedView === 'list' && <ColumnHeader />}

              {groups.map((g) => (
                <section key={g.key} aria-labelledby={`work-group-${g.key}`}>
                  {g.label && (
                    <h3
                      id={`work-group-${g.key}`}
                      // Sticky, because the heading is the answer to "what am
                      // I looking at" and scrolling past it in a long listing
                      // takes that answer away at exactly the moment it is
                      // being used.
                      className="sticky top-0 z-10 mb-2 flex items-baseline gap-2 py-1 text-[11px] uppercase tracking-wider"
                      style={{
                        fontFamily: 'var(--font-display)',
                        color: 'var(--color-text-muted)',
                        background: 'var(--color-bg, #060911)',
                      }}
                    >
                      {g.label}
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--color-text-faint)',
                          letterSpacing: 0,
                        }}
                      >
                        {g.artifacts.length}
                      </span>
                    </h3>
                  )}

                  {resolvedView === 'grid' ? (
                    <div
                      className="grid gap-3"
                      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}
                    >
                      {g.artifacts.map((a) => (
                        <Thumbnail
                          key={a.id}
                          artifact={a}
                          selected={selected?.id === a.id}
                          onSelect={() => setSelected(a)}
                        />
                      ))}
                    </div>
                  ) : (
                    <div
                      className="rounded-xl overflow-hidden"
                      style={{ border: '1px solid var(--color-border-subtle)' }}
                    >
                      {g.artifacts.map((a) => (
                        <Row
                          key={a.id}
                          artifact={a}
                          selected={selected?.id === a.id}
                          onSelect={() => setSelected(a)}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <DetailPanel
          key={selected.id}
          artifact={selected}
          onClose={() => setSelected(null)}
          onOpenConversation={onOpenConversation}
        />
      )}
    </div>
  );
}

/** The column names, aligned to `ROW_GRID`.
 *
 *  Labels rather than sort buttons. Sorting lives in the toolbar, where it
 *  applies to a grid view too — click-a-column-to-sort would be a second
 *  control for one setting, and the two would disagree the first time somebody
 *  sorted in grid view and switched back. */
function ColumnHeader() {
  return (
    <div
      className="grid items-center gap-3 px-4 pb-1.5 text-[10px] uppercase tracking-wider"
      style={{
        gridTemplateColumns: ROW_GRID,
        fontFamily: 'var(--font-display)',
        color: 'var(--color-text-faint)',
        // Indent matching the row's icon column, so "Name" sits over the
        // filename rather than over the icon.
        paddingLeft: 43,
      }}
    >
      <span>Name and conversation</span>
      <span className="hidden lg:block">Project</span>
      <span>Made</span>
      <span className="hidden lg:block text-right">Size</span>
    </div>
  );
}

/** One artifact as a row. */
function Row({
  artifact: a,
  selected,
  onSelect,
}: {
  artifact: Artifact;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      aria-current={selected || undefined}
      className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.04]"
      style={{
        borderBottom: '1px solid var(--color-border-subtle)',
        background: selected ? 'rgba(255,255,255,0.05)' : 'transparent',
      }}
    >
      <span className="shrink-0" style={{ color: KIND_COLOUR[a.kind] }}>
        {KIND_ICON[a.kind]}
      </span>

      <span className="grid min-w-0 flex-1 items-center gap-3" style={{ gridTemplateColumns: ROW_GRID }}>
        <span className="min-w-0">
          <span className="block truncate text-sm" style={{ color: 'var(--color-text)' }}>
            {a.filename}
          </span>
          {/* The conversation that produced it, on the row rather than hidden
              in the panel. It is the reason this surface is not a file
              browser. */}
          <span
            className="mt-0.5 flex items-center gap-1.5 text-[11px] truncate"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <MessageSquare size={10} className="shrink-0" />
            <span className="truncate">
              {a.conversation_title || 'No conversation recorded'}
            </span>
          </span>
        </span>

        <span
          className="hidden lg:block truncate text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
        >
          {projectLabel(a.project_id)}
        </span>

        <span
          className="truncate text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}
        >
          {relative(a.created_at)}
        </span>

        <span
          className="hidden lg:block text-right text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
        >
          {bytes(a.size_bytes)}
        </span>
      </span>
    </button>
  );
}


/** One picture in Work's grid.
 *
 *  Its own component because the image fetch is a hook, and a hook cannot be
 *  called inside the `visible.map` that draws the tiles.
 */
function Thumbnail({
  artifact,
  selected,
  onSelect,
}: {
  artifact: Artifact;
  selected: boolean;
  onSelect: () => void;
}) {
  const image = useArtifactImage(artifact.id, artifact.exists);

  return (
    <button
      onClick={onSelect}
      className="overflow-hidden rounded-xl text-left transition-colors"
      style={{
        border: selected
          ? '1px solid var(--color-indigo-light)'
          : '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
      }}
    >
      <span
        className="block w-full"
        style={{
          aspectRatio: '1 / 1',
          background: 'var(--color-surface-sunken, #0b1120)',
        }}
      >
        {image.url ? (
          <img
            src={image.url}
            alt={artifact.filename}
            className="h-full w-full"
            style={{ objectFit: 'cover' }}
          />
        ) : (
          <span
            className="flex h-full w-full items-center justify-center"
            style={{ color: 'var(--color-text-faint)' }}
            title={image.error ?? undefined}
          >
            {KIND_ICON[artifact.kind]}
          </span>
        )}
      </span>
      <span className="block px-2.5 py-2">
        <span className="block truncate text-[11px]" style={{ color: 'var(--color-text)' }}>
          {artifact.filename}
        </span>
        <span
          className="block truncate text-[10px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}
        >
          {relative(artifact.created_at)}
        </span>
      </span>
    </button>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <span
        className="text-[11px]"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
      >
        Reading what you have made…
      </span>
    </div>
  );
}

/** Designed empty state with a recovery action. Never a dead end. */
function EmptyState({ filtered, onClear }: { filtered: boolean; onClear: () => void }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div style={{ maxWidth: 420, textAlign: 'center' }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 12,
            margin: '0 auto 20px',
            display: 'grid',
            placeItems: 'center',
            background: 'var(--color-glass)',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          <FileText size={26} />
        </div>

        <h2
          className="text-lg"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          {filtered ? 'Nothing matches those filters' : 'Nothing here yet'}
        </h2>

        <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {filtered
            ? 'No artifact in this project has that type.'
            : 'Documents, spreadsheets and charts you make will appear here — each with the conversation that produced it and the sources it drew on.'}
        </p>

        {filtered ? (
          <button
            onClick={onClear}
            className="mt-5 rounded-lg px-3 py-1.5 text-xs transition-colors hover:bg-white/5"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            Clear filters
          </button>
        ) : (
          <p
            className="mt-5 text-[11px] leading-relaxed"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
          >
            Ask a question in the conversation, then say
            <br />
            &ldquo;write that up as a proposal&rdquo;.
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Detail panel, from the right.
 *
 * Same anchor and pattern as fact detail. Glass on the frame; the document
 * itself sits on an opaque surface, because reading a document through a
 * translucent layer over a scrolling list is unpleasant.
 */
function DetailPanel({
  artifact,
  onClose,
  onOpenConversation,
}: {
  artifact: Artifact;
  onClose: () => void;
  onOpenConversation?: () => void;
}) {
  const [full, setFull] = useState<Artifact | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const pictorial = PICTORIAL_KINDS.has(artifact.kind);
  const picture = useArtifactImage(artifact.id, pictorial && artifact.exists);

  useEffect(() => {
    let cancelled = false;
    // The list omits `html` — it is the re-export source and can be large, and
    // twenty documents fetched to draw twenty rows is waste. Fetch it when a
    // row is actually opened.
    getArtifact(artifact.id, true)
      .then((a) => {
        if (!cancelled) setFull(a);
      })
      .catch((e) => {
        if (!cancelled) {
          setPreviewError(e instanceof Error ? e.message : 'Preview unavailable');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [artifact.id]);

  const claims = full?.claims ?? artifact.claims;

  return (
    <aside
      className="flex flex-col overflow-hidden"
      style={{
        width: 520,
        flexShrink: 0,
        borderLeft: '1px solid var(--color-border-subtle)',
        background: 'rgba(19, 22, 32, 0.72)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        animation: 'slide-in-right 0.2s ease',
      }}
    >
      <div
        className="flex items-start gap-3 px-5 py-4"
        style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      >
        <span className="mt-0.5 shrink-0" style={{ color: KIND_COLOUR[artifact.kind] }}>
          {KIND_ICON[artifact.kind]}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm break-all" style={{ color: 'var(--color-text)' }}>
            {artifact.filename}
          </div>
          <div
            className="mt-1 text-[11px]"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
          >
            {projectLabel(artifact.project_id)} · {relative(artifact.created_at)} ·{' '}
            {bytes(artifact.size_bytes)}
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="p-1 rounded-md text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-colors"
        >
          <X size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        <section>
          <SectionLabel>Preview</SectionLabel>
          {/* The preview *is* the HTML the file was rendered from, so what is
              shown here is what downloads. Sandboxed with no permissions: the
              markup is ours, but the prose inside it was written by a model,
              and defence in depth costs nothing here. */}
          {pictorial ? (
            // The picture itself, matching the overlay. For every other kind
            // the HTML *is* the faithful preview, because it is what the
            // exporters render from; for an image the file that downloads is
            // the PNG and the HTML is the envelope it travelled in. Showing
            // the envelope here and the picture in the overlay would be the
            // drift the comment above this section warns about.
            <div
              className="flex items-center justify-center rounded-lg"
              style={{
                height: 320,
                border: '1px solid var(--color-border-subtle)',
                background: 'var(--color-surface-sunken, #0b1120)',
              }}
            >
              {picture.url ? (
                <img
                  src={picture.url}
                  alt={artifact.filename}
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                />
              ) : (
                <span
                  className="text-[11px]"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
                >
                  {picture.error ?? 'Loading preview…'}
                </span>
              )}
            </div>
          ) : previewError ? (
            <p className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
              {previewError}
            </p>
          ) : full ? (
            <iframe
              title={`Preview of ${artifact.filename}`}
              srcDoc={full.html}
              sandbox=""
              className="w-full rounded-lg"
              style={{
                height: 320,
                border: '1px solid var(--color-border-subtle)',
                background: '#fff',
              }}
            />
          ) : (
            <div
              className="rounded-lg px-4 py-6 text-[11px]"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text-faint)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              Loading preview…
            </div>
          )}
        </section>

        {claims.length > 0 && (
          <section>
            <SectionLabel>Claims</SectionLabel>
            {/* What makes a generated document defensible rather than merely
                attributed: which sentence came from which fact. */}
            <ul className="space-y-1.5">
              {claims.map((c) => (
                <li
                  key={c.id}
                  className="rounded-lg px-3 py-2 text-[11px]"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text-muted-light)',
                  }}
                >
                  <span className="flex items-start gap-2">
                    <Quote
                      size={11}
                      className="mt-0.5 shrink-0"
                      style={{ color: 'var(--color-cyan-light)' }}
                    />
                    <span className="min-w-0">
                      <span className="block">{c.excerpt}</span>
                      {c.source_excerpt && (
                        <span
                          className="mt-1 block"
                          style={{ color: 'var(--color-text-secondary)' }}
                        >
                          {c.source_excerpt}
                        </span>
                      )}
                      <span
                        className="mt-1 block truncate"
                        style={{
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--color-text-faint)',
                        }}
                      >
                        {c.source_id}
                      </span>
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <SectionLabel>Sources</SectionLabel>
          {artifact.sources.length === 0 ? (
            // Zero sources is a real and meaningful state, not a loading one.
            <p className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
              Nothing recalled. This was made from what you typed, not from
              anything in the Spine.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {artifact.sources.map((s, index) => (
                <li
                  key={`${s.kind}-${s.url ?? s.title ?? index}`}
                  className="flex items-start gap-2 rounded-lg px-3 py-2 text-[11px]"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text-muted-light)',
                  }}
                >
                  <span
                    className="mt-1 shrink-0 rounded-full"
                    style={{ width: 5, height: 5, background: 'var(--color-cyan-light)' }}
                  />
                  <span className="min-w-0">
                    <span className="block">{s.title ?? 'Untitled source'}</span>
                    <span
                      className="block truncate"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
                    >
                      {s.url ?? s.kind}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div
        className="px-5 py-4 space-y-2"
        style={{ borderTop: '1px solid var(--color-border-subtle)' }}
      >
        <button
          onClick={onOpenConversation}
          disabled={!onOpenConversation || !artifact.conversation_id}
          title={
            artifact.conversation_id
              ? undefined
              : 'No conversation was recorded for this artifact'
          }
          className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-white/5 disabled:opacity-40"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <MessageSquare size={13} />
          Open the conversation that made this
        </button>

        {/* Real, because there is a real file. When the record outlives the
            file — the user moved it — the button says so rather than offering a
            download that fails. */}
        {artifact.exists ? (
          <>
            {/* Preview belongs on both surfaces or neither. Work is where a
                file is *browsed* — the conversation card is where it was made —
                and a control that exists in one place and not the other is the
                kind of inconsistency users read as a bug in the surface that
                lacks it. Same component, so the two cannot drift. */}
            <button
              type="button"
              onClick={() => setPreviewing(true)}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-white/5"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <Eye size={13} />
              Preview
            </button>
            {/* A button, not a link. Every request to the backend is
                authenticated against this launch's credential, and that
                credential rides on a wrapper around `fetch` — an anchor
                navigates without it and gets 401. See `downloadUrl`. */}
            <button
              type="button"
              onClick={() => {
                setDownloadError(null);
                downloadArtifact(artifact.id, artifact.filename).catch((err: unknown) =>
                  setDownloadError(
                    err instanceof Error ? err.message : 'Could not download that file.',
                  ),
                );
              }}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-white/5"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <Download size={13} />
              Download {artifact.filename.split('.').pop()?.toUpperCase()}
            </button>
            {downloadError && (
              <p className="text-[11px]" style={{ color: '#fca5a5' }} role="alert">
                {downloadError}
              </p>
            )}
          </>
        ) : (
          <button
            disabled
            title="The record is here but the file is not at the path it was written to"
            className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs disabled:cursor-not-allowed"
            style={{
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text-faint)',
            }}
          >
            <Download size={13} />
            File not found where it was written
          </button>
        )}
      </div>

      <AnimatePresence>
        {previewing && (
          <ArtifactPreview artifact={artifact} onClose={() => setPreviewing(false)} />
        )}
      </AnimatePresence>
    </aside>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="mb-2 text-[10px] uppercase tracking-wider"
      style={{ color: 'var(--color-text-secondary)' }}
    >
      {children}
    </div>
  );
}
