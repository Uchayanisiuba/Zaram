/**
 * Sources — where Zaram's knowledge comes from, and what it could not read.
 *
 * The second half is the point. Ingest already produced a reason and a remedy
 * per file; until this screen drew them, a file that gave nothing back was
 * *recorded* rather than loud, and silent ingestion failure is the most likely
 * reason a user concludes the product doesn't know their material and leaves.
 *
 * So problems sort first, every one states what happened in a sentence, every
 * one that has a fix names it with its cost, and every one can be retried —
 * because the commonest reason a file failed is that it was open in Word.
 *
 * `docs/UI-SPEC.md` calls this screen Sources and gives it an indexing target,
 * progress and a per-folder scope toggle. All three are here.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Check,
  ClipboardPaste,
  FileWarning,
  FolderOpen,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import SurfaceHeader from '../components/common/SurfaceHeader';
import {
  fetchOutcomes,
  fetchSources,
  ingestFolder,
  ingestText,
  isProblem,
  removeSource,
  retryOutcome,
  setSourcePolicy,
  uploadFiles,
  STATUS_LABELS,
  type IngestEvent,
  type IngestOutcome,
  type IngestSource,
} from '../services/ingestClient';

interface Progress {
  root: string;
  index: number;
  total: number;
  current: string;
}

/** Below this, a paste is far more likely to be a path or a filename the user
 *  meant for the field below than a document. Offering to index every short
 *  paste would tax every interaction to serve a minority of them — rule 7h —
 *  and the offer above it costs nothing when it is not wanted. */
const MIN_PASTE_CHARS = 40;

/**
 * The real filesystem path of a dropped file, when the desktop host offers one.
 *
 * **The one place that knows how to ask.** Electron adds a non-standard `path`
 * to `File`, which is how a dropped *folder* becomes something the existing
 * folder route can index — the browser hands a directory over as a zero-byte
 * file that is useless on its own. Electron 32 removed it in favour of
 * `webUtils.getPathForFile` behind the preload bridge, so that upgrade changes
 * this function and nothing else.
 *
 * `null` in a browser tab, which is the honest answer there: a web page is not
 * allowed to know where a file came from, and the interface says so rather
 * than failing at the parser.
 */
function desktopPathOf(file: File): string | null {
  const path = (file as File & { path?: unknown }).path;
  return typeof path === 'string' && path ? path : null;
}

const STATUS_COLOR: Record<string, string> = {
  indexed: 'var(--color-emerald)',
  sparse: 'var(--color-amber, #d97706)',
  empty: 'var(--color-amber, #d97706)',
  failed: 'var(--color-rose, #e11d48)',
  unsupported: 'var(--color-text-dim, #64748b)',
};

export default function KnowledgeWorkspace() {
  const [sources, setSources] = useState<IngestSource[]>([]);
  const [outcomes, setOutcomes] = useState<IngestOutcome[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [pathInput, setPathInput] = useState('');
  const [retrying, setRetrying] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  /** A gap, not a failure — a dropped folder. Separate from `error` because
   *  starting an ingest clears the error, and a drop of a folder *and* some
   *  files would otherwise lose the one thing the user needs to be told. */
  const [notice, setNotice] = useState<string | null>(null);
  /** The staged source awaiting a yes before its documents are deleted. */
  const [confirming, setConfirming] = useState<string | null>(null);
  const [pasted, setPasted] = useState<string | null>(null);
  const [pasteName, setPasteName] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [nextSources, nextOutcomes] = await Promise.all([
        fetchSources(),
        fetchOutcomes(),
      ]);
      setSources(nextSources);
      setOutcomes(nextOutcomes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach Zaram.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => abortRef.current?.abort();
  }, [load]);

  /**
   * One ingest, whichever way it started.
   *
   * Folder, drop and paste differ only in the call they make: the stream is
   * one shape, so the progress, the error handling and the reload are written
   * once. Returns whether it finished, which is the only thing the callers
   * differ on afterwards.
   */
  const run = useCallback(
    async (
      label: string,
      operation: (
        onEvent: (event: IngestEvent) => void,
        signal: AbortSignal,
      ) => Promise<void>,
    ): Promise<boolean> => {
      if (progress) return false;

      abortRef.current = new AbortController();
      setError(null);
      setProgress({ root: label, index: 0, total: 0, current: 'Looking…' });

      try {
        await operation((event: IngestEvent) => {
          if (event.type === 'start') {
            setProgress({ root: event.root, index: 0, total: event.total, current: '' });
          } else if (event.type === 'file') {
            setProgress((p) =>
              p ? { ...p, index: event.index, total: event.total, current: event.name } : p,
            );
          } else if (event.type === 'error') {
            setError(event.message);
          }
        }, abortRef.current.signal);
        await load();
        return true;
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          // The backend's own sentence when it sent one — "that file is larger
          // than 100 MB" is actionable and "413" is not.
          setError(err instanceof Error ? err.message : 'Indexing failed.');
        }
        return false;
      } finally {
        setProgress(null);
      }
    },
    [progress, load],
  );

  // The notice is cleared by whatever the user did *next*, not by `run` — a
  // drop of a folder and some files would otherwise clear its own message on
  // the way to uploading the files. `onDrop` sets it for the same reason.
  const startIngest = useCallback(async () => {
    const path = pathInput.trim();
    if (!path) return;
    setNotice(null);
    if (await run(path, (onEvent, signal) => ingestFolder(path, onEvent, signal))) {
      setPathInput('');
    }
  }, [pathInput, run]);

  const addFiles = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      const label = files.length === 1 ? files[0].name : `${files.length} files`;
      await run(label, (onEvent, signal) => uploadFiles(files, onEvent, signal));
    },
    [run],
  );

  /** Dropped folders, indexed through the route a typed path already uses. */
  const addFolders = useCallback(
    async (paths: string[]) => {
      if (!paths.length) return;
      const label = paths.length === 1 ? paths[0] : `${paths.length} folders`;
      await run(label, async (onEvent, signal) => {
        // Sequential, not parallel: two scans writing source rows at once is a
        // race for no gain, and the progress line can only describe one file.
        for (const path of paths) await ingestFolder(path, onEvent, signal);
      });
    },
    [run],
  );

  const addPastedText = useCallback(async () => {
    const text = pasted;
    if (!text) return;
    setNotice(null);
    const name = pasteName.trim();
    if (await run(name || 'Pasted text', (onEvent, signal) => ingestText(text, name, onEvent, signal))) {
      setPasted(null);
      setPasteName('');
    }
  }, [pasted, pasteName, run]);

  /**
   * A drop. Files are uploaded; folders are scanned where that is possible.
   *
   * The `DataTransfer` is read entirely before the first `await` — it is
   * emptied once the handler yields, so a file list gathered afterwards is
   * silently empty.
   *
   * Directories are separated out because the browser hands one over as a
   * zero-byte file: uploaded, it would be indexed as an empty document, which
   * is a wrong answer. In the desktop app it resolves to a real path and goes
   * to the folder route instead — the same route the field below uses. In a
   * browser tab it cannot, and the interface says which and why rather than
   * quietly doing nothing.
   */
  const onDrop = useCallback(
    async (event: React.DragEvent) => {
      event.preventDefault();
      setDragging(false);

      const items = Array.from(event.dataTransfer.items ?? []).filter((i) => i.kind === 'file');
      const entries = items.map((item) => item.webkitGetAsEntry?.() ?? null);
      const all = Array.from(event.dataTransfer.files ?? []);

      const files: File[] = [];
      const folderPaths: string[] = [];
      let unresolvedFolders = 0;

      all.forEach((file, index) => {
        if (entries[index]?.isDirectory !== true) {
          files.push(file);
          return;
        }
        const path = desktopPathOf(file);
        if (path) folderPaths.push(path);
        else unresolvedFolders += 1;
      });

      setNotice(
        unresolvedFolders === 0
          ? null
          : unresolvedFolders === 1
            ? "A folder can't be read from a browser tab — put its path in the field below, or drop it into the Zaram app."
            : "Folders can't be read from a browser tab — put a path in the field below, or drop them into the Zaram app.",
      );

      // Folders first: a drop of a folder and some loose files is one intent,
      // and the folder is the larger half of it.
      await addFolders(folderPaths);
      await addFiles(files);
    },
    [addFiles, addFolders],
  );

  /**
   * A paste, anywhere on this screen that is not a field.
   *
   * The guard matters: without it, pasting a folder path into the input below
   * would also offer to index the path as a document. Files on the clipboard
   * go straight in — the user copied a file, and there is nothing to decide —
   * while text is *offered*, because a paste is far more often a path, and an
   * offer at the moment of doubt costs nothing when it is not wanted.
   */
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      ) {
        return;
      }

      const data = event.clipboardData;
      if (!data) return;

      const files = Array.from(data.files ?? []);
      if (files.length) {
        event.preventDefault();
        void addFiles(files);
        return;
      }

      const text = data.getData('text/plain');
      if (text.trim().length >= MIN_PASTE_CHARS) {
        event.preventDefault();
        setPasted(text);
      }
    };

    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [addFiles]);

  const onRetry = useCallback(async (outcome: IngestOutcome) => {
    setRetrying(outcome.id);
    try {
      const updated = await retryOutcome(outcome.id);
      setOutcomes((current) =>
        current.map((o) => (o.id === updated.id ? updated : o)),
      );
      setSources(await fetchSources());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed.');
    } finally {
      setRetrying(null);
    }
  }, []);

  const onTogglePolicy = useCallback(async (source: IngestSource) => {
    const next = source.policy === 'local_only' ? 'cloud_allowed' : 'local_only';
    await setSourcePolicy(source.id, next);
    setSources((current) =>
      current.map((s) => (s.id === source.id ? { ...s, policy: next } : s)),
    );
  }, []);

  /**
   * Withdraw a source.
   *
   * **A staged source is asked about first, because withdrawing it deletes
   * documents.** The files under Zaram's uploads directory are copies it wrote
   * when things were dropped or pasted, and taking the source out now takes
   * them with it — otherwise the button's own promise, "everything Zaram
   * learned from it", is not kept and the bytes become unreachable. That makes
   * it irreversible, and CLAUDE.md is explicit that deleting something holding
   * facts and files is never one button.
   *
   * A scanned folder is not asked about: nothing on disk is touched, its facts
   * are removable by design under rule 4, and a confirmation on every removal
   * would be the tax rule 7h warns against.
   */
  const onRemove = useCallback(async (source: IngestSource) => {
    const result = await removeSource(source.id);
    if (selected === source.id) setSelected(null);
    setConfirming(null);
    if (result.files_deleted > 0) {
      setNotice(
        result.files_deleted === 1
          ? 'Forgotten, and the copy Zaram kept was deleted. Your original is untouched.'
          : `Forgotten, and the ${result.files_deleted} copies Zaram kept were deleted. Your originals are untouched.`,
      );
    }
    await load();
  }, [selected, load]);

  const visible = selected
    ? outcomes.filter((o) => o.source_id === selected)
    : outcomes;
  const problems = visible.filter((o) => isProblem(o.status));
  const fine = visible.filter((o) => !isProblem(o.status));

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="knowledge-workspace">
      {/* BookOpen, not FolderOpen: the left rail draws this node as BookOpen,
          and the icon you clicked should be the icon you arrive at. */}
      <SurfaceHeader icon={BookOpen} title="Sources" />

      <div className="flex-1 overflow-y-auto px-8 pb-8">
        {/* --- add documents ------------------------------------------------ */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={(e) => {
            // Moving over a child fires dragleave on the parent, which would
            // flicker the highlight off under the cursor.
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
          }}
          onDrop={onDrop}
          data-testid="drop-zone"
          className="rounded-xl px-5 py-4"
          style={{
            border: `1px solid ${dragging ? 'var(--color-cyan-light)' : 'var(--color-border-subtle)'}`,
            background: 'var(--color-glass)',
          }}
        >
          <div className="flex items-center gap-3">
            <Upload size={16} style={{ color: 'var(--color-cyan-light)' }} />
            <div className="flex-1 min-w-0">
              <p className="text-sm" style={{ color: 'var(--color-text)' }} data-testid="drop-invitation">
                {dragging ? 'Drop them here' : 'Drop documents here'}
              </p>
              <p className="text-[11px] text-slate-500">
                Or paste — text or files — anywhere on this screen.
              </p>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={!!progress}
              data-testid="choose-files"
              className="text-xs px-3 py-1.5 rounded-lg disabled:opacity-40"
              style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
            >
              Choose files
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            data-testid="file-input"
            onChange={(e) => {
              const chosen = Array.from(e.target.files ?? []);
              // Cleared so choosing the same file twice still fires a change.
              e.target.value = '';
              setNotice(null);
              void addFiles(chosen);
            }}
          />

          <div
            className="mt-3 pt-3 flex items-center gap-3"
            style={{ borderTop: '1px solid var(--color-border-subtle)' }}
          >
            <FolderOpen size={15} style={{ color: 'var(--color-text-dim, #64748b)' }} />
            <input
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startIngest()}
              placeholder="…or the path to a whole folder"
              disabled={!!progress}
              data-testid="ingest-path"
              className="flex-1 bg-transparent text-sm outline-none"
              style={{ color: 'var(--color-text)' }}
            />
            <button
              onClick={startIngest}
              disabled={!pathInput.trim() || !!progress}
              data-testid="ingest-start"
              className="text-xs px-3 py-1.5 rounded-lg disabled:opacity-40"
              style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
            >
              Index
            </button>
          </div>

          {progress && (
            <div className="mt-3 flex items-center gap-2" data-testid="ingest-progress">
              <Loader2 size={13} className="animate-spin" style={{ color: 'var(--color-cyan-light)' }} />
              {/* Per file, not a percentage. A bar at 90% says nothing about
                  which document is missing. */}
              <span className="text-xs text-slate-400">
                {progress.total
                  ? `${progress.index} of ${progress.total} · ${progress.current}`
                  : progress.current}
              </span>
            </div>
          )}

          {/* A capability gap, stated rather than left silent. */}
          {notice && (
            <p className="mt-3 text-xs" style={{ color: 'var(--color-amber, #d97706)' }} data-testid="ingest-notice">
              {notice}
            </p>
          )}

          {error && (
            <p className="mt-3 text-xs" style={{ color: 'var(--color-rose, #e11d48)' }} data-testid="ingest-error">
              {error}
            </p>
          )}
        </div>

        {/* --- pasted text, offered rather than assumed ---------------------- */}
        {pasted && (
          <div
            className="mt-3 rounded-xl px-5 py-4"
            style={{ border: '1px solid var(--color-cyan-light)', background: 'var(--color-glass)' }}
            data-testid="paste-offer"
          >
            <div className="flex items-center gap-3">
              <ClipboardPaste size={15} style={{ color: 'var(--color-cyan-light)' }} />
              <p className="text-sm flex-1" style={{ color: 'var(--color-text)' }}>
                Keep {pasted.length.toLocaleString()} characters of pasted text?
              </p>
            </div>

            {/* What will actually be kept. The user pasted it, so showing it
                back is the only honest confirmation — and it is the real text,
                never a summary of it. */}
            <p
              className="mt-2 text-xs leading-relaxed text-slate-400 line-clamp-3"
              data-testid="paste-preview"
            >
              {pasted.slice(0, 240)}
              {pasted.length > 240 ? '…' : ''}
            </p>

            <div className="mt-3 flex items-center gap-2">
              <input
                value={pasteName}
                onChange={(e) => setPasteName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPastedText()}
                placeholder="Name it (optional)"
                data-testid="paste-name"
                className="flex-1 bg-transparent text-xs outline-none px-2 py-1.5 rounded-lg"
                style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
              />
              <button
                onClick={addPastedText}
                disabled={!!progress}
                data-testid="paste-add"
                className="text-xs px-3 py-1.5 rounded-lg disabled:opacity-40"
                style={{ border: '1px solid var(--color-cyan-light)', color: 'var(--color-text)' }}
              >
                Add
              </button>
              <button
                onClick={() => { setPasted(null); setPasteName(''); }}
                data-testid="paste-dismiss"
                className="text-xs px-3 py-1.5 rounded-lg"
                style={{ color: 'var(--color-text-dim, #64748b)' }}
              >
                Not now
              </button>
            </div>
          </div>
        )}

        {/* --- the folders -------------------------------------------------- */}
        {loading ? (
          <p className="mt-6 text-xs text-slate-500">Loading…</p>
        ) : sources.length === 0 ? (
          <div
            className="mt-4 rounded-xl px-6 py-10 text-center"
            style={{ border: '1px dashed var(--color-border-subtle)' }}
            data-testid="sources-empty"
          >
            <p className="text-sm" style={{ color: 'var(--color-text)' }}>No sources yet.</p>
            <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
              Drop a few documents above, or point Zaram at a whole folder. Every
              answer drawn from them will cite the document and passage it came
              from, and anything Zaram could not read will be listed here with
              the reason.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-2" data-testid="sources-list">
            {sources.map((source) => (
              <div
                key={source.id}
                className="rounded-xl px-5 py-3 flex items-center gap-3 cursor-pointer"
                style={{
                  border: '1px solid var(--color-border-subtle)',
                  background:
                    selected === source.id ? 'var(--color-glass)' : 'transparent',
                }}
                onClick={() => setSelected(selected === source.id ? null : source.id)}
                data-testid={`source-${source.id}`}
              >
                <FolderOpen size={15} style={{ color: 'var(--color-cyan-light)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                    {source.name}
                  </p>
                  <p className="text-[11px] text-slate-500 truncate">{source.root}</p>
                </div>

                <span className="text-[11px] text-slate-400 shrink-0">
                  {source.counts.indexed ?? 0} indexed
                </span>
                {source.problems > 0 && (
                  <span
                    className="text-[11px] shrink-0 flex items-center gap-1"
                    style={{ color: 'var(--color-amber, #d97706)' }}
                    data-testid={`source-problems-${source.id}`}
                  >
                    <AlertTriangle size={11} />
                    {source.problems} need attention
                  </span>
                )}

                <button
                  onClick={(e) => { e.stopPropagation(); void onTogglePolicy(source); }}
                  title={
                    source.policy === 'local_only'
                      ? 'Local only — nothing from this folder is sent to a cloud model'
                      : 'Cloud allowed for this folder'
                  }
                  className="text-[11px] px-2 py-1 rounded-md shrink-0 flex items-center gap-1"
                  style={{
                    border: '1px solid var(--color-border-subtle)',
                    color:
                      source.policy === 'local_only'
                        ? 'var(--color-emerald)'
                        : 'var(--color-text-dim, #64748b)',
                  }}
                  data-testid={`policy-${source.id}`}
                >
                  <ShieldCheck size={11} />
                  {source.policy === 'local_only' ? 'Local only' : 'Cloud allowed'}
                </button>

                {confirming === source.id ? (
                  // Named consequences, not "are you sure?". The count is the
                  // part that decides, and so is the sentence saying the
                  // originals survive — that is the thing a person is actually
                  // afraid of here.
                  <div
                    className="shrink-0 flex items-center gap-2"
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`confirm-${source.id}`}
                  >
                    <span className="text-[11px]" style={{ color: 'var(--color-amber, #d97706)' }}>
                      Delete {source.total} {source.total === 1 ? 'document' : 'documents'} Zaram
                      copied here? Your originals stay.
                    </span>
                    <button
                      onClick={() => void onRemove(source)}
                      className="text-[11px] px-2 py-1 rounded-md"
                      style={{ border: '1px solid var(--color-rose, #e11d48)', color: 'var(--color-rose, #e11d48)' }}
                      data-testid={`confirm-yes-${source.id}`}
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setConfirming(null)}
                      className="text-[11px] px-2 py-1 rounded-md"
                      style={{ color: 'var(--color-text-dim, #64748b)' }}
                      data-testid={`confirm-no-${source.id}`}
                    >
                      Keep
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      // Staged sources hold Zaram's own copies, so withdrawing
                      // deletes files and has to be asked. A scanned folder
                      // touches no disk and is not worth a dialog.
                      if (source.staged) setConfirming(source.id);
                      else void onRemove(source);
                    }}
                    title={
                      source.staged
                        ? 'Forget these documents and delete the copies Zaram kept'
                        : 'Forget this folder and everything Zaram learned from it'
                    }
                    className="shrink-0 opacity-60 hover:opacity-100"
                    data-testid={`remove-${source.id}`}
                  >
                    <Trash2 size={13} style={{ color: 'var(--color-text-dim, #64748b)' }} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* --- what needs attention ----------------------------------------- */}
        {problems.length > 0 && (
          <div className="mt-6" data-testid="problems-section">
            <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-2">
              Needs attention · {problems.length}
            </h2>
            <div className="space-y-2">
              {problems.map((outcome) => (
                <div
                  key={outcome.id}
                  className="rounded-xl px-5 py-4"
                  style={{ border: '1px solid var(--color-border-subtle)' }}
                  data-testid={`outcome-${outcome.id}`}
                >
                  <div className="flex items-start gap-3">
                    <FileWarning
                      size={15}
                      className="mt-0.5 shrink-0"
                      style={{ color: STATUS_COLOR[outcome.status] }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                          {outcome.name}
                        </p>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{
                            color: STATUS_COLOR[outcome.status],
                            border: `1px solid ${STATUS_COLOR[outcome.status]}`,
                          }}
                        >
                          {STATUS_LABELS[outcome.status]}
                        </span>
                      </div>

                      {/* The reason. Never a stack trace, never a status code. */}
                      {outcome.reason && (
                        <p
                          className="mt-1.5 text-xs leading-relaxed text-slate-400"
                          data-testid={`reason-${outcome.id}`}
                        >
                          {outcome.reason}
                        </p>
                      )}

                      {/* The fix, and what it costs. "Install the extra" on a
                          metered connection is not a decision without the size. */}
                      {outcome.remedy && (
                        <p
                          className="mt-1.5 text-xs leading-relaxed"
                          style={{ color: 'var(--color-cyan-light)' }}
                          data-testid={`remedy-${outcome.id}`}
                        >
                          {outcome.remedy}
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => void onRetry(outcome)}
                      disabled={retrying === outcome.id}
                      className="text-[11px] px-2 py-1 rounded-md shrink-0 flex items-center gap-1 disabled:opacity-40"
                      style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
                      data-testid={`retry-${outcome.id}`}
                    >
                      {retrying === outcome.id ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : (
                        <RefreshCw size={11} />
                      )}
                      Retry
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* --- what worked --------------------------------------------------- */}
        {fine.length > 0 && (
          <div className="mt-6" data-testid="indexed-section">
            <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-2">
              Indexed · {fine.filter((o) => o.status === 'indexed').length}
            </h2>
            <div className="space-y-1">
              {fine.map((outcome) => (
                <div
                  key={outcome.id}
                  className="px-4 py-2 flex items-center gap-3 rounded-lg"
                  style={{ border: '1px solid var(--color-border-subtle)' }}
                >
                  {outcome.status === 'indexed' ? (
                    <Check size={12} style={{ color: 'var(--color-emerald)' }} />
                  ) : (
                    <X size={12} style={{ color: 'var(--color-text-dim, #64748b)' }} />
                  )}
                  <span className="text-xs truncate flex-1" style={{ color: 'var(--color-text)' }}>
                    {outcome.name}
                  </span>
                  <span className="text-[11px] text-slate-500 shrink-0">
                    {outcome.status === 'indexed'
                      ? `${outcome.chars.toLocaleString()} characters`
                      : STATUS_LABELS[outcome.status]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
