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
  MessageSquare,
  Quote,
  Receipt,
  RefreshCw,
  X,
} from 'lucide-react';

import ArtifactPreview from '@/components/ArtifactPreview';
import SurfaceHeader from '@/components/common/SurfaceHeader';
import {
  KIND_LABELS,
  downloadUrl,
  getArtifact,
  listArtifacts,
  type Artifact,
  type ArtifactKind,
} from '@/services/artifactsClient';

const KIND_ICON: Record<ArtifactKind, React.ReactNode> = {
  invoice: <Receipt size={16} />,
  document: <FileText size={16} />,
  spreadsheet: <FileSpreadsheet size={16} />,
  chart: <BarChart3 size={16} />,
};

// One accent per kind, drawn from the existing token set. No new hues.
const KIND_COLOUR: Record<ArtifactKind, string> = {
  invoice: 'var(--color-emerald)',
  document: 'var(--color-cyan-light)',
  spreadsheet: 'var(--color-amber)',
  chart: 'var(--color-violet)',
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
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] transition-colors hover:bg-white/5"
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
    () =>
      (kind === 'all' ? byProject : byProject.filter((a) => a.kind === kind))
        .slice()
        .sort((a, b) => b.created_at - a.created_at),
    [byProject, kind],
  );

  const kinds = Object.keys(KIND_LABELS) as ArtifactKind[];

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

          <div className="mt-4 flex flex-wrap gap-1.5">
            <Chip
              label="All projects"
              count={artifacts.length}
              active={project === 'all'}
              onClick={() => setProject('all')}
            />
            {projects.map((p) => (
              <Chip
                key={p.id}
                label={projectLabel(p.id)}
                count={p.count}
                active={project === p.id}
                onClick={() => setProject(p.id)}
              />
            ))}
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip
              label="All types"
              count={byProject.length}
              active={kind === 'all'}
              onClick={() => setKind('all')}
            />
            {kinds.map((k) => (
              <Chip
                key={k}
                label={KIND_LABELS[k]}
                count={byProject.filter((a) => a.kind === k).length}
                active={kind === k}
                onClick={() => setKind(k)}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-8 pb-8">
          {loading && artifacts.length === 0 ? (
            <LoadingState />
          ) : visible.length === 0 ? (
            <EmptyState
              filtered={artifacts.length > 0}
              onClear={() => {
                setProject('all');
                setKind('all');
              }}
            />
          ) : (
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: '1px solid var(--color-border-subtle)' }}
            >
              {visible.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setSelected(a)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.04]"
                  style={{
                    borderBottom: '1px solid var(--color-border-subtle)',
                    background:
                      selected?.id === a.id ? 'rgba(255,255,255,0.05)' : 'transparent',
                  }}
                >
                  <span className="shrink-0" style={{ color: KIND_COLOUR[a.kind] }}>
                    {KIND_ICON[a.kind]}
                  </span>

                  <span className="flex-1 min-w-0">
                    <span
                      className="block truncate text-sm"
                      style={{ color: 'var(--color-text)' }}
                    >
                      {a.filename}
                    </span>
                    {/* The conversation that produced it, on the row rather
                        than hidden in the panel. It is the reason this surface
                        is not a file browser. */}
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
                    className="shrink-0 text-[11px] text-right"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
                  >
                    <span className="block">{projectLabel(a.project_id)}</span>
                    <span className="block" style={{ color: 'var(--color-text-secondary)' }}>
                      {relative(a.created_at)}
                    </span>
                  </span>
                </button>
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
          {previewError ? (
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
            <a
              href={downloadUrl(artifact.id)}
              download={artifact.filename}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-white/5"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <Download size={13} />
              Download {artifact.filename.split('.').pop()?.toUpperCase()}
            </a>
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
