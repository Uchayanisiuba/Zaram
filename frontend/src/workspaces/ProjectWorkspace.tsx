/**
 * Project — the organisation of work, not the work itself.
 *
 * The sixth node, added 10 August 2026. It earned one rather than being a
 * filter inside Work because `project:<id>` scopes **facts**, not only files:
 * it reaches the Spine and, later, the plan. A filter living inside Work cannot
 * own something that scopes Memory. The precedent is Memory and Knowledge —
 * similar enough to group, and separate because they are not the same thing.
 *
 * **Work is the output; Project is the organisation of it.** Work browses and
 * previews what was made. Here you create a project, name it, choose the type
 * that activates a pack, and remove one.
 *
 * **There is no folder tree, and there will not be one.** One level of
 * grouping. A hierarchy would be a second organising system competing with
 * scope, provenance and recall — and if a tree were needed to find your own
 * work, recall has failed and the tree hides that rather than fixing it.
 *
 * The screen someone lands on when they have no projects is the important one,
 * so it says what a project is *for* rather than showing an empty table.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Layers,
  Plus,
  Trash2,
  Check,
  X,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  CornerUpLeft,
} from 'lucide-react';
import {
  assignToProject,
  listArtifacts,
  type Artifact,
} from '@/services/artifactsClient';
import {
  PROJECT_TYPES,
  useProjectStore,
  type DeleteContents,
  type Project,
  type ProjectType,
} from '@/stores/projectStore';

/** What each type means, in the user's terms rather than ours. Shown at
 *  creation because that is the moment the choice is made and the only moment
 *  the user can be told what it does. */
const TYPE_BLURB: Record<ProjectType, string> = {
  general: 'No pack. Documents, notes, whatever this turns out to be.',
  business: 'Invoices, quotes, receipts and expenses.',
  coding: 'Repositories, reviews, and the decisions behind them.',
  '3d': 'Unreal and Blender scenes, read-only for now.',
  mcp: 'Tools and servers you are wiring up.',
};

function typeLabel(type: ProjectType): string {
  return type === '3d' ? '3D' : type[0].toUpperCase() + type.slice(1);
}

export default function ProjectWorkspace() {
  const projects = useProjectStore((s) => s.projects);
  const loading = useProjectStore((s) => s.loading);
  const error = useProjectStore((s) => s.error);
  const load = useProjectStore((s) => s.load);

  const [creating, setCreating] = useState(false);
  const [confirming, setConfirming] = useState<Project | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7" style={{ color: 'var(--color-text)' }}>
      <header className="flex items-start justify-between gap-6 mb-7">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <Layers size={18} aria-hidden />
            Project
          </h1>
          <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            How your work is grouped. Files live in Work; this decides what belongs where.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors"
          style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.08)' }}
        >
          <Plus size={13} aria-hidden />
          New project
        </button>
      </header>

      {error && (
        <p className="mb-4 text-[11px]" style={{ color: '#fca5a5' }}>
          {error}
        </p>
      )}

      {creating && <CreateRow onDone={() => setCreating(false)} />}

      {!loading && projects.length === 0 && !creating && <EmptyState />}

      {projects.length > 0 && (
        <ul className="flex flex-col gap-2">
          {projects.map((project) => (
            <ProjectRow
              key={project.id}
              project={project}
              onDelete={() => setConfirming(project)}
            />
          ))}
        </ul>
      )}

      {confirming && (
        <DeleteDialog project={confirming} onClose={() => setConfirming(null)} />
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="rounded-xl px-6 py-10 text-center"
      style={{ background: 'var(--color-glass)', border: '1px dashed rgba(255,255,255,.08)' }}
    >
      <p className="text-sm font-medium">No projects yet</p>
      {/* Says what it is for, not "nothing here". Someone landing on an empty
          surface needs to know why they would fill it. */}
      <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
        A project keeps one piece of work together — what Zaram remembers about
        it, and the files it produced. Facts learned inside a project stay with
        that project instead of mixing into everything else.
      </p>
    </div>
  );
}

function CreateRow({ onDone }: { onDone: () => void }) {
  const create = useProjectStore((s) => s.create);
  const [name, setName] = useState('');
  const [type, setType] = useState<ProjectType>('general');
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    const created = await create(name, type);
    setBusy(false);
    if (created) onDone();
  }, [busy, create, name, onDone, type]);

  return (
    <div
      className="mb-4 rounded-xl p-4"
      style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.1)' }}
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') void submit();
          if (e.key === 'Escape') onDone();
        }}
        placeholder="What is this project called?"
        aria-label="Project name"
        className="w-full bg-transparent text-sm outline-none placeholder-slate-500"
      />

      <div className="mt-3 flex flex-wrap gap-1.5">
        {PROJECT_TYPES.map((candidate) => (
          <button
            key={candidate}
            type="button"
            onClick={() => setType(candidate)}
            aria-pressed={type === candidate}
            className="rounded px-2 py-1 text-[10px] transition-colors"
            style={{
              background: type === candidate ? 'var(--color-cyan-dim, rgba(120,220,240,.16))' : 'transparent',
              border: '1px solid rgba(255,255,255,.08)',
              color: type === candidate ? 'var(--color-cyan)' : 'var(--color-text-muted)',
            }}
          >
            {typeLabel(candidate)}
          </button>
        ))}
      </div>
      {/* The type is chosen once, at creation, and activates a pack — so this is
          the only moment the user can be told what they are choosing. */}
      <p className="mt-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        {TYPE_BLURB[type]}
      </p>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!name.trim() || busy}
          className="inline-flex items-center gap-1 rounded px-2.5 py-1.5 text-[11px] disabled:opacity-40"
          style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.1)' }}
        >
          <Check size={12} aria-hidden />
          Create
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded px-2.5 py-1.5 text-[11px]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function ProjectRow({ project, onDelete }: { project: Project; onDelete: () => void }) {
  const rename = useProjectStore((s) => s.rename);
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(project.name);

  return (
    <li
      className="rounded-xl px-4 py-3"
      style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.06)' }}
    >
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={`${open ? 'Hide' : 'Show'} what is in ${project.name}`}
          className="shrink-0 rounded p-1 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
        </button>

        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => {
                setEditing(false);
                if (draft.trim() && draft !== project.name) void rename(project.id, draft);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') e.currentTarget.blur();
                if (e.key === 'Escape') {
                  setDraft(project.name);
                  setEditing(false);
                }
              }}
              aria-label={`Rename ${project.name}`}
              className="w-full bg-transparent text-sm outline-none"
            />
          ) : (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="truncate text-sm font-medium hover:underline"
              title="Rename"
            >
              {project.name}
            </button>
          )}
          <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
            {/* The id is shown because it is what appears in the egress log and
                on every fact as `project:<id>`. A user reading their own logs
                should be able to match them up. */}
            {typeLabel(project.type)} · <code>{project.id}</code> · {project.artifacts} file
            {project.artifacts === 1 ? '' : 's'} ·{' '}
            {project.facts < 0 ? 'facts unknown' : `${project.facts} fact${project.facts === 1 ? '' : 's'}`}
          </p>
        </div>

        <button
          type="button"
          onClick={onDelete}
          aria-label={`Delete ${project.name}`}
          title="Delete"
          className="shrink-0 rounded p-1.5 transition-colors hover:text-red-300"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <Trash2 size={14} aria-hidden />
        </button>
      </div>

      {open && <ProjectContents project={project} />}
    </li>
  );
}

/**
 * What is in a project, and the only place a file is put into one.
 *
 * `CLAUDE.md` splits the two surfaces: **Work is the output, Project is the
 * organisation of it.** Work browses and previews; assigning, moving and
 * removing belong here. Project shipped on 10 August with everything except
 * this — a group you could create and could not fill, so the only way in was to
 * pick the project in the composer *before* the file existed. That is rule 7h
 * inverted: it made the user decide in advance of the work instead of at the
 * moment the answer is obvious.
 *
 * **Adding a file that belongs to another project moves it.** A file has one
 * project, so the button says so rather than reading as a copy and quietly
 * emptying somewhere else.
 *
 * Nothing here touches the disk. A project is a label; the output directory
 * stays flat, and there is no folder tree to keep in step with it.
 */
function ProjectContents({ project }: { project: Project }) {
  const load = useProjectStore((s) => s.load);
  const [files, setFiles] = useState<Artifact[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState('');

  const refresh = useCallback(async () => {
    try {
      // Everything, not just this project's: the picker needs the files that
      // are somewhere else, and one request answers both halves.
      const listing = await listArtifacts();
      setFiles(listing.artifacts);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your files.');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const move = useCallback(
    async (id: string, destination: string) => {
      setBusy(id);
      try {
        await assignToProject(id, destination);
        await refresh();
        // The counts on every row are derived from the artifacts table on the
        // server, so they are re-read rather than adjusted here. A number kept
        // in two places is a number that disagrees with itself, and this one
        // ends up on a delete confirmation.
        await load();
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not move that file.');
      } finally {
        setBusy(null);
      }
    },
    [load, refresh],
  );

  const mine = useMemo(
    () => (files ?? []).filter((f) => f.project_id === project.id),
    [files, project.id],
  );

  const elsewhere = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (files ?? [])
      .filter((f) => f.project_id !== project.id)
      .filter((f) => !needle || `${f.filename} ${f.conversation_title}`.toLowerCase().includes(needle));
  }, [files, project.id, query]);

  return (
    <div className="mt-3 border-t pt-3" style={{ borderColor: 'rgba(255,255,255,.06)' }}>
      {error && (
        <p className="mb-2 text-[11px]" style={{ color: '#fca5a5' }}>
          {error}
        </p>
      )}

      {files === null && !error && (
        <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          Loading files…
        </p>
      )}

      {files !== null && mine.length === 0 && (
        <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          No files in this project yet.
        </p>
      )}

      {mine.length > 0 && (
        <ul className="flex flex-col gap-1">
          {mine.map((file) => (
            <li key={file.id} className="flex items-center justify-between gap-3">
              <span className="truncate text-[11px]" title={file.filename}>
                {file.filename}
              </span>
              <button
                type="button"
                onClick={() => void move(file.id, '')}
                disabled={busy === file.id}
                aria-label={`Remove ${file.filename} from ${project.name}`}
                title="Remove from this project. The file is not deleted."
                className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-1 text-[10px] transition-colors disabled:opacity-40"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <CornerUpLeft size={11} aria-hidden />
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {files !== null && !picking && (
        <button
          type="button"
          onClick={() => setPicking(true)}
          className="mt-2 inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] transition-colors"
          style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.08)' }}
        >
          <Plus size={11} aria-hidden />
          Add files
        </button>
      )}

      {picking && (
        <div className="mt-2">
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setPicking(false);
              }}
              placeholder="Find a file"
              aria-label={`Find a file to add to ${project.name}`}
              className="flex-1 bg-transparent text-[11px] outline-none placeholder-slate-500"
            />
            <button
              type="button"
              onClick={() => setPicking(false)}
              aria-label="Done adding files"
              className="rounded p-1"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <X size={12} aria-hidden />
            </button>
          </div>

          {elsewhere.length === 0 ? (
            <p className="mt-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {query.trim() ? 'Nothing matches that.' : 'Every file is already in this project.'}
            </p>
          ) : (
            <ul className="mt-2 flex max-h-56 flex-col gap-1 overflow-y-auto">
              {elsewhere.map((file) => (
                <li key={file.id} className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate text-[11px]" title={file.filename}>
                    {file.filename}
                    {file.project_id && (
                      /* Naming where it currently lives is what makes the
                         button below honest: this is a move, and somewhere
                         else loses the file. */
                      <span style={{ color: 'var(--color-text-muted)' }}> · in {file.project_id}</span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => void move(file.id, project.id)}
                    disabled={busy === file.id}
                    className="shrink-0 rounded px-1.5 py-1 text-[10px] transition-colors disabled:opacity-40"
                    style={{ color: 'var(--color-cyan)' }}
                  >
                    {file.project_id ? 'Move here' : 'Add'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Deleting states what it will do, then does exactly that.
 *
 * A project holds facts the user cannot get back. Rule 4 gives *them* power
 * over their facts — a container exercising it on their behalf is how someone
 * loses a client's rates by tidying a sidebar. So there is no default that
 * destroys, the counts are on screen, and the two outcomes are separate
 * buttons rather than a checkbox someone can miss.
 */
function DeleteDialog({ project, onClose }: { project: Project; onClose: () => void }) {
  const remove = useProjectStore((s) => s.remove);
  const [busy, setBusy] = useState(false);

  const go = useCallback(
    async (contents: DeleteContents) => {
      setBusy(true);
      await remove(project.id, contents);
      setBusy(false);
      onClose();
    },
    [onClose, project.id, remove],
  );

  const factsUnknown = project.facts < 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: 'rgba(0,0,0,.55)' }}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Delete ${project.name}`}
        className="w-full max-w-md rounded-2xl p-5"
        style={{ background: 'var(--color-surface, #12161b)', border: '1px solid rgba(255,255,255,.1)' }}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-sm font-semibold">Delete “{project.name}”?</h2>
          <button type="button" onClick={onClose} aria-label="Cancel" style={{ color: 'var(--color-text-muted)' }}>
            <X size={15} aria-hidden />
          </button>
        </div>

        <p className="mt-3 text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          This project holds <strong>{project.artifacts}</strong> file
          {project.artifacts === 1 ? '' : 's'} and{' '}
          {factsUnknown ? <strong>an unknown number of</strong> : <strong>{project.facts}</strong>} fact
          {project.facts === 1 ? '' : 's'}.
        </p>

        {/* Unknown is shown as unknown. "0 facts" on a confirmation that then
            destroys eleven of them is the precise failure the -1 exists for. */}
        {factsUnknown && (
          <p className="mt-2 flex items-start gap-1.5 text-[11px]" style={{ color: '#fcd34d' }}>
            <AlertTriangle size={12} className="mt-0.5 shrink-0" aria-hidden />
            Zaram could not count the facts in this project, so it cannot tell you what
            deleting them would remove.
          </p>
        )}

        <p className="mt-3 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          Files are never deleted — Zaram cannot remove a file from your disk.
        </p>

        <div className="mt-5 flex flex-col gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void go('keep')}
            className="rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-40"
            style={{ background: 'var(--color-glass)', border: '1px solid rgba(255,255,255,.12)' }}
          >
            Delete the project, keep what it knows
            <span className="mt-0.5 block text-[10px] font-normal" style={{ color: 'var(--color-text-muted)' }}>
              Facts move to global memory. Nothing is lost, only the grouping.
            </span>
          </button>

          <button
            type="button"
            disabled={busy || factsUnknown}
            onClick={() => void go('delete')}
            className="rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-40"
            style={{ border: '1px solid rgba(252,165,165,.35)', color: '#fca5a5' }}
          >
            Delete the project and its facts
            <span className="mt-0.5 block text-[10px] font-normal" style={{ color: 'rgba(252,165,165,.7)' }}>
              {factsUnknown
                ? 'Unavailable while the fact count is unknown.'
                : 'This cannot be undone.'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
