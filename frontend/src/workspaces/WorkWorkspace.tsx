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
 * ⚠️ The data here is SAMPLE data — see `@/data/sampleArtifacts`. Nothing is
 * generated yet, so this surface is designed against invented artifacts and says
 * so on screen. Session 4 replaces the import with real ones; the shape of what
 * it reads should not need to change.
 */
import { useMemo, useState } from 'react';
import {
  BarChart3,
  Download,
  FileSpreadsheet,
  FileText,
  MessageSquare,
  Receipt,
  X,
} from 'lucide-react';

import {
  KIND_LABELS,
  SAMPLE_ARTIFACTS,
  SAMPLE_PROJECTS,
  type Artifact,
  type ArtifactKind,
} from '@/data/sampleArtifacts';

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
  const [project, setProject] = useState<string>('all');
  const [kind, setKind] = useState<ArtifactKind | 'all'>('all');
  const [selected, setSelected] = useState<Artifact | null>(null);

  const projectName = (id: string) =>
    SAMPLE_PROJECTS.find((p) => p.id === id)?.name ?? id;

  const byProject = useMemo(
    () =>
      project === 'all'
        ? SAMPLE_ARTIFACTS
        : SAMPLE_ARTIFACTS.filter((a) => a.projectId === project),
    [project],
  );

  const visible = useMemo(
    () =>
      (kind === 'all' ? byProject : byProject.filter((a) => a.kind === kind))
        .slice()
        .sort((a, b) => b.createdAt - a.createdAt),
    [byProject, kind],
  );

  const kinds = Object.keys(KIND_LABELS) as ArtifactKind[];

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-8 pt-6 pb-3">
          <div className="flex items-baseline gap-3">
            <h1
              className="text-lg font-semibold"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
            >
              Work
            </h1>
            <span
              className="text-xs"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
            >
              {visible.length} of {SAMPLE_ARTIFACTS.length}
            </span>
          </div>

          {/* The surface says what it is. Without this line the screen is a
              convincing lie — twenty plausible filenames with real-looking
              dates, none of which exist. */}
          <div
            className="mt-3 rounded-lg px-3 py-2 text-[11px] leading-relaxed"
            style={{
              border: '1px solid var(--color-border-subtle)',
              background: 'var(--color-glass)',
              color: 'var(--color-text-muted)',
            }}
          >
            <strong style={{ color: 'var(--color-amber)' }}>Sample data.</strong>{' '}
            Nothing here was generated and no file exists on disk. This surface is
            designed against invented artifacts until the generative pipeline
            fills it.
          </div>

          <div className="mt-4 flex flex-wrap gap-1.5">
            <Chip
              label="All projects"
              count={SAMPLE_ARTIFACTS.length}
              active={project === 'all'}
              onClick={() => setProject('all')}
            />
            {SAMPLE_PROJECTS.map((p) => (
              <Chip
                key={p.id}
                label={p.name}
                count={SAMPLE_ARTIFACTS.filter((a) => a.projectId === p.id).length}
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
          {visible.length === 0 ? (
            <EmptyState
              filtered={SAMPLE_ARTIFACTS.length > 0}
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
                      <span className="truncate">{a.conversation.title}</span>
                    </span>
                  </span>

                  <span
                    className="shrink-0 text-[11px] text-right"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
                  >
                    <span className="block">{projectName(a.projectId)}</span>
                    <span className="block" style={{ color: 'var(--color-text-secondary)' }}>
                      {relative(a.createdAt)}
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
          artifact={selected}
          projectName={projectName(selected.projectId)}
          onClose={() => setSelected(null)}
          onOpenConversation={onOpenConversation}
        />
      )}
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
  projectName,
  onClose,
  onOpenConversation,
}: {
  artifact: Artifact;
  projectName: string;
  onClose: () => void;
  onOpenConversation?: () => void;
}) {
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
            {projectName} · {relative(artifact.createdAt)} · {bytes(artifact.sizeBytes)}
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
          {/* Opaque, per UI-SPEC — the document does not sit on glass. */}
          <pre
            className="rounded-lg p-4 text-[11px] leading-relaxed overflow-x-auto"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text-muted-light)',
              fontFamily: 'var(--font-mono)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {artifact.previewText}
          </pre>
        </section>

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
              {artifact.sources.map((s) => (
                <li
                  key={s.url ?? s.title ?? Math.random()}
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
          disabled={!onOpenConversation}
          className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-white/5 disabled:opacity-40"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <MessageSquare size={13} />
          Open the conversation that made this
        </button>

        {/* Inert, and says why. A download button on sample data that produced
            a plausible-looking invoice would be precisely the fabrication the
            "never render invented values" rule exists to prevent — worse than
            the button not being here, because the file would look real. */}
        <button
          disabled
          title="Sample data — there is no file to download"
          className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs disabled:cursor-not-allowed"
          style={{
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          <Download size={13} />
          Download — no file, this is sample data
        </button>
      </div>
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
