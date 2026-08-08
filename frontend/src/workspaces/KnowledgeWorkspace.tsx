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
  Check,
  FileWarning,
  FolderOpen,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';
import {
  fetchOutcomes,
  fetchSources,
  ingestFolder,
  isProblem,
  removeSource,
  retryOutcome,
  setSourcePolicy,
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
  const abortRef = useRef<AbortController | null>(null);

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

  const startIngest = useCallback(async () => {
    const path = pathInput.trim();
    if (!path || progress) return;

    abortRef.current = new AbortController();
    setError(null);
    setProgress({ root: path, index: 0, total: 0, current: 'Looking…' });

    try {
      await ingestFolder(
        path,
        (event: IngestEvent) => {
          if (event.type === 'start') {
            setProgress({ root: event.root, index: 0, total: event.total, current: '' });
          } else if (event.type === 'file') {
            setProgress((p) =>
              p ? { ...p, index: event.index, total: event.total, current: event.name } : p,
            );
          } else if (event.type === 'error') {
            setError(event.message);
          }
        },
        abortRef.current.signal,
      );
      setPathInput('');
      await load();
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err instanceof Error ? err.message : 'Indexing failed.');
      }
    } finally {
      setProgress(null);
    }
  }, [pathInput, progress, load]);

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

  const onRemove = useCallback(async (source: IngestSource) => {
    await removeSource(source.id);
    if (selected === source.id) setSelected(null);
    await load();
  }, [selected, load]);

  const visible = selected
    ? outcomes.filter((o) => o.source_id === selected)
    : outcomes;
  const problems = visible.filter((o) => isProblem(o.status));
  const fine = visible.filter((o) => !isProblem(o.status));

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="knowledge-workspace">
      <div className="px-8 pt-6 pb-4 flex items-center gap-3">
        <FolderOpen size={20} style={{ color: 'var(--color-cyan-light)' }} />
        <h1
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          Sources
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto px-8 pb-8">
        {/* --- add a folder ------------------------------------------------ */}
        <div
          className="rounded-xl px-5 py-4"
          style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
        >
          <div className="flex items-center gap-3">
            <input
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startIngest()}
              placeholder="Path to a folder…"
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

          {error && (
            <p className="mt-3 text-xs" style={{ color: 'var(--color-rose, #e11d48)' }} data-testid="ingest-error">
              {error}
            </p>
          )}
        </div>

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
              Point Zaram at a folder above. Every answer drawn from it will cite
              the document and passage it came from, and anything Zaram could not
              read will be listed here with the reason.
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

                <button
                  onClick={(e) => { e.stopPropagation(); void onRemove(source); }}
                  title="Forget this folder and everything Zaram learned from it"
                  className="shrink-0 opacity-60 hover:opacity-100"
                  data-testid={`remove-${source.id}`}
                >
                  <Trash2 size={13} style={{ color: 'var(--color-text-dim, #64748b)' }} />
                </button>
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
