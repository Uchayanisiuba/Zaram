/**
 * Memory — what Zaram actually knows, and how to change it.
 *
 * This screen previously showed a fabricated knowledge graph: 1,847 nodes, 284
 * conversations, "+23 today", and invented entities including a person who does
 * not exist. The Spine held about twenty records. Every number was made up.
 *
 * It now reports the Spine, and — the point of this pass — lets the user change
 * it. Rule 4 says a stored fact can be corrected and the affected answers must
 * change. A screen that could only display would make that a promise; the
 * Correct, Forget and Pin controls make it a thing the user can do.
 *
 * Correction produces supersession, never deletion. The old fact stays here,
 * struck through and dated, marked as something the user corrected. It is
 * excluded from recall but never hidden — a correction you cannot see is
 * indistinguishable from a deletion, and the visible one is the trust artifact.
 * A system that shows you where it was wrong is one you will believe when it
 * says it is right.
 *
 * **Commitments are the second view, and they are here rather than in a node
 * of their own.** `CLAUDE.md` fixes the navigation at six and says a pack adds
 * no screens; obligations are the first pack. The division it does draw is
 * that Memory holds derived facts about the user and Knowledge holds the
 * documents those came from — and an obligation is a derived, correctable
 * claim carrying provenance back to a source. Same store of belief, same
 * correction loop, a different shape of record. See
 * `components/memory/Commitments.tsx`.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import SurfaceHeader from '../components/common/SurfaceHeader';
import Commitments from '../components/memory/Commitments';
import {
  countObligations,
  fetchObligations,
  type ObligationCounts,
} from '@/services/obligationsClient';
import {
  Brain,
  Search,
  RefreshCw,
  AlertCircle,
  Pin,
  PinOff,
  Pencil,
  Trash2,
  CornerDownRight,
  X,
  Check,
} from 'lucide-react';
import {
  correctMemory,
  deleteMemory,
  fetchMemoryList,
  fetchMemoryStats,
  pinMemory,
  scopeProjectId,
  setMemoryScope,
  type MemoryRecord,
  type MemoryStats,
} from '@/services/memoryClient';
import { useSourceStore } from '@/stores/sourceStore';
import { useProjectStore } from '@/stores/projectStore';

const relative = (seconds: number) => {
  const delta = Date.now() / 1000 - seconds;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} hr ago`;
  return new Date(seconds * 1000).toLocaleDateString();
};

const shortDate = (seconds: number) =>
  new Date(seconds * 1000).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  });

/**
 * What the curator is doing to each fact, in rule 7e's own words.
 *
 * The state is the backend's — it asks the decay engine's own predicate, so
 * the thresholds are not spelled a second time here. This file only decides
 * how to say it.
 */
const STANDING_NOTE: Record<string, string> = {
  provisional:
    'It is here provisionally: nothing has needed it yet, and it will fade if nothing does.',
  durable: 'Using it is what keeps it — it has earned its place.',
  fading: 'Nothing has used it, so it is on its way out. Pin it if it should stay.',
  pinned: 'Pinned, so it is exempt from fading.',
};

/** Amber for the one that is going, so it can be found by scanning. The other
 *  two are ordinary states and are not worth a colour each. */
const standingColour = (standing: string) =>
  standing === 'fading' ? 'var(--color-amber, #fbbf24)' : undefined;

const bytes = (n: number) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

type Filter = 'all' | 'pinned' | 'corrected';

/** The two kinds of thing Zaram believes: facts it was told, and
 *  commitments it read out of a document. Both are corrected the same way,
 *  which is why they share a surface, and they are separate views because
 *  they are separate shapes of record rather than two filters over one. */
type View = 'facts' | 'commitments';

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div
      className="flex-1 rounded-xl px-4 py-3"
      style={{ background: 'var(--color-glass)', border: '1px solid var(--color-border-subtle)' }}
    >
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className="mt-1 text-2xl"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}
      >
        {value}
      </div>
      {note && <div className="mt-0.5 text-[10px] text-slate-500">{note}</div>}
    </div>
  );
}

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
      {/* A live count, not a static label. An empty filter should say so
          before the user clicks it and finds nothing. */}
      <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.6 }}>{count}</span>
    </button>
  );
}

export default function MemoryWorkspace() {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [confirmForget, setConfirmForget] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<View>('facts');
  // Reported up from Commitments after each of its loads, so the metric
  // row is a measurement rather than a second request that could disagree
  // with the list under it. Null until one has happened — an unmeasured
  // count must not render as a measured zero.
  const [commitments, setCommitments] = useState<ObligationCounts | null>(null);

  const openSource = useSourceStore((s) => s.openSource);
  const forgotten = useSourceStore((s) => s.forgotten);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    try {
      const [listing, s] = await Promise.all([
        fetchMemoryList({ q, limit: 200 }),
        fetchMemoryStats(),
      ]);
      setRecords(listing.records);
      setStats(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load memory.');
      setRecords([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(query), query ? 250 : 0);
    return () => clearTimeout(t);
  }, [query, load]);

  // The commitments count, read once when Memory opens. Commitments keeps it
  // current afterwards; this is only so the badge exists before the tab has
  // been opened, which is the whole point of a badge. A failure is silent
  // here on purpose — the count stays null and renders as nothing rather
  // than
  // as zero, and the tab reports the error properly when it is opened.
  useEffect(() => {
    let live = true;
    void fetchObligations()
      .then((listing) => {
        if (live) setCommitments(countObligations(listing));
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // The projects a fact can be moved to. Read from `/projects` — the list of
  // projects that *exist* — rather than from the ones that happen to hold
  // files, because a fact is often the first thing a new project holds.
  const projects = useProjectStore((s) => s.projects);
  const loadProjects = useProjectStore((s) => s.load);
  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const present = useMemo(
    () => records.filter((r) => !forgotten.has(`memory:${r.id}`)),
    [records, forgotten],
  );

  const counts = useMemo(
    () => ({
      all: present.length,
      pinned: present.filter((r) => r.pinned).length,
      corrected: present.filter((r) => r.superseded_by).length,
    }),
    [present],
  );

  const visible = useMemo(() => {
    if (filter === 'pinned') return present.filter((r) => r.pinned);
    if (filter === 'corrected') return present.filter((r) => r.superseded_by);
    return present;
  }, [present, filter]);

  /** The replacement for a superseded fact, so the old one can point at it. */
  const replacementOf = useCallback(
    (id: string | null | undefined) => records.find((r) => r.id === id) ?? null,
    [records],
  );

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load(query);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.');
    } finally {
      setBusy(false);
    }
  };

  const submitCorrection = (id: string) => {
    const text = draft.trim();
    if (!text) return;
    void act(async () => {
      await correctMemory(id, text);
      setEditing(null);
      setDraft('');
      setExpanded(null);
    });
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <SurfaceHeader icon={Brain} title="Memory" iconColor="var(--color-indigo-light)">
        {view === 'facts' && (
          <button
            onClick={() => void load(query)}
            aria-label="Refresh memory"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        )}
      </SurfaceHeader>

      {/* Facts and commitments, not a seventh node. Two views over one store
          of belief, both corrected the same way. */}
      <div
        className="px-8 pb-4 flex items-center gap-5"
        role="tablist"
        aria-label="What Zaram knows"
      >
        {([
          ['facts', 'Facts'],
          ['commitments', 'Commitments'],
        ] as [View, string][]).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={view === id}
            onClick={() => setView(id)}
            className="pb-1 text-[13px] transition-colors"
            style={{
              color: view === id ? 'var(--color-text)' : 'var(--color-text-muted)',
              borderBottom: `1px solid ${view === id ? 'var(--color-indigo-light)' : 'transparent'}`,
            }}
          >
            {label}
            {/* The count is the reason to look. It is shown only once
                Commitments has actually loaded, so an unmeasured count never
                renders as a measured zero. */}
            {id === 'commitments' && commitments && commitments.open > 0 && (
              <span className="ml-1.5" style={{ fontFamily: 'var(--font-mono)', opacity: 0.6 }}>
                {commitments.open}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Measured counts only. */}
      <div className="px-8 flex gap-3">
        {view === 'facts' ? (
          <>
            <Metric label="Facts stored" value={stats ? String(stats.total_records) : '—'} />
            <Metric label="Sessions" value={stats ? String(stats.sessions) : '—'} />
            <Metric
              label="Left device today"
              // Now measured from the egress log. Null still means unknown rather
              // than zero — an absent measurement must never read as a measured
              // zero on a privacy claim.
              value={
                stats?.bytes_left_device_today == null
                  ? 'unknown'
                  : bytes(stats.bytes_left_device_today)
              }
              note={stats?.bytes_left_device_today == null ? 'egress log unreachable' : undefined}
            />
          </>
        ) : (
          <>
            <Metric label="Live" value={commitments ? String(commitments.open) : '—'} />
            <Metric
              label="Late"
              value={commitments ? String(commitments.overdue) : '—'}
              note={commitments && commitments.overdue > 0 ? 'past the date in the clause' : undefined}
            />
            <Metric
              label="Needs a date"
              value={commitments ? String(commitments.questions) : '—'}
              note={
                commitments && commitments.questions > 0
                  ? 'read, but not datable on its own'
                  : undefined
              }
            />
          </>
        )}
      </div>

      {view === 'facts' ? (
        <>
        <div className="px-8 pt-5 pb-3 flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search what Zaram remembers…"
              aria-label="Search memory"
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg outline-none transition-colors"
              style={{
                background: 'var(--color-glass)',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text)',
              }}
            />
          </div>
          <Chip label="All" count={counts.all} active={filter === 'all'} onClick={() => setFilter('all')} />
          <Chip label="Pinned" count={counts.pinned} active={filter === 'pinned'} onClick={() => setFilter('pinned')} />
          <Chip label="Corrected" count={counts.corrected} active={filter === 'corrected'} onClick={() => setFilter('corrected')} />
        </div>

        <div className="flex-1 overflow-y-auto px-8 pb-8">
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg px-4 py-3 text-xs mb-3"
              style={{ background: 'rgba(248,113,113,0.08)', color: '#fca5a5' }}
            >
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!error && !loading && visible.length === 0 && (
            <div className="py-16 text-center">
              <p className="text-sm text-slate-400">
                {query
                  ? 'Nothing matches that.'
                  : filter === 'pinned'
                    ? 'Nothing is pinned.'
                    : filter === 'corrected'
                      ? 'Nothing has been corrected.'
                      : 'Zaram has not learned anything yet.'}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {query
                  ? 'Try a different word, or clear the search.'
                  : filter !== 'all'
                    ? 'Switch back to All to see everything stored.'
                    : 'Open the conversation and tell it something — it will appear here.'}
              </p>
            </div>
          )}

          {visible.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {visible.map((r) => {
                const superseded = Boolean(r.superseded_by);
                const isOpen = expanded === r.id;
                const replacement = replacementOf(r.superseded_by);

                return (
                  <li
                    key={r.id}
                    className="rounded-lg transition-colors"
                    style={{
                      border: `1px solid ${isOpen ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
                      background: isOpen ? 'rgba(255,255,255,0.03)' : 'transparent',
                      // A superseded fact recedes but is never hidden.
                      opacity: superseded ? 0.55 : 1,
                    }}
                  >
                    <button
                      onClick={() => setExpanded(isOpen ? null : r.id)}
                      className="w-full text-left px-4 py-3"
                    >
                      <div className="flex items-start gap-2">
                        {r.pinned && (
                          <Pin
                            size={12}
                            className="mt-1 shrink-0"
                            style={{ color: 'var(--color-amber, #fbbf24)' }}
                            aria-label="Pinned"
                          />
                        )}
                        <p
                          className="text-sm leading-snug flex-1"
                          style={{
                            color: 'var(--color-text)',
                            textDecoration: superseded ? 'line-through' : undefined,
                          }}
                        >
                          {r.content}
                        </p>
                        {/* Only project facts are badged. Global is the default
                            and badging it would put a label on every row that
                            says nothing — the interesting state is the one that
                            narrows where a fact applies and who could see it. */}
                        {scopeProjectId(r.scope) && (
                          <span
                            className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px]"
                            style={{
                              fontFamily: 'var(--font-mono)',
                              border: '1px solid var(--color-border-subtle)',
                              color: 'var(--color-text-muted)',
                            }}
                            title={`Scoped to the ${scopeProjectId(r.scope)} project`}
                          >
                            {scopeProjectId(r.scope)}
                          </span>
                        )}
                      </div>

                      <p
                        className="mt-1.5 text-[10px] text-slate-500"
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {superseded && r.superseded_at ? (
                          <span style={{ color: 'var(--color-amber, #fbbf24)' }}>
                            superseded {shortDate(r.superseded_at)} · you corrected this
                          </span>
                        ) : (
                          <>
                            {r.source} · {relative(r.created_at)} · recalled {r.access_count}×
                            {r.standing && (
                              <>
                                {' · '}
                                <span style={{ color: standingColour(r.standing) }}>
                                  {r.standing}
                                </span>
                              </>
                            )}
                          </>
                        )}
                      </p>

                      {superseded && replacement && (
                        <p className="mt-1 flex items-start gap-1.5 text-[11px] text-slate-400">
                          <CornerDownRight size={11} className="mt-0.5 shrink-0" />
                          <span>{replacement.content}</span>
                        </p>
                      )}
                    </button>

                    {isOpen && (
                      <div
                        className="px-4 pb-3 pt-1"
                        style={{ borderTop: '1px solid var(--color-border-subtle)' }}
                      >
                        {/* Why it is here, in plain language rather than a score. */}
                        <p className="text-[11px] leading-relaxed text-slate-400 mb-3">
                          {superseded ? (
                            <>
                              You corrected this on{' '}
                              {r.superseded_at ? shortDate(r.superseded_at) : 'an earlier date'}. It
                              is kept so you can see what changed, and is never used to answer
                              anything.
                            </>
                          ) : (
                            <>
                              Learned {relative(r.created_at)} from {r.source}, and used in{' '}
                              {r.access_count} {r.access_count === 1 ? 'answer' : 'answers'} since.
                              {r.pinned && ' Pinned, so recall prefers it over more recent facts.'}
                              {/* Rule 7e has been running daily since it
                                  landed and nothing on this screen said so. A
                                  Spine you cannot watch curating itself is one
                                  you assume is hoarding — which is most of why
                                  saving everything by hand feels necessary. */}
                              {!r.pinned && r.standing && ` ${STANDING_NOTE[r.standing]}`}
                            </>
                          )}
                        </p>

                        {editing === r.id ? (
                          <div>
                            <textarea
                              value={draft}
                              onChange={(e) => setDraft(e.target.value)}
                              rows={3}
                              autoFocus
                              aria-label="Corrected fact"
                              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                              style={{
                                background: 'var(--color-glass)',
                                border: '1px solid var(--color-border)',
                                color: 'var(--color-text)',
                              }}
                            />
                            <p className="mt-1.5 text-[10px] text-slate-500">
                              The original is kept and struck through. Answers that relied on it
                              will change.
                            </p>
                            <div className="mt-2 flex gap-2">
                              <button
                                disabled={busy || !draft.trim()}
                                onClick={() => submitCorrection(r.id)}
                                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40"
                                style={{
                                  border: '1px solid var(--color-border)',
                                  background: 'rgba(255,255,255,0.08)',
                                  color: 'var(--color-text)',
                                }}
                              >
                                <Check size={12} />
                                Save correction
                              </button>
                              <button
                                onClick={() => {
                                  setEditing(null);
                                  setDraft('');
                                }}
                                className="rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : confirmForget === r.id ? (
                          <div>
                            <p className="text-[11px] text-slate-300 mb-2">
                              Delete this for good? Unlike correcting, this leaves no record that
                              Zaram ever knew it.
                            </p>
                            <div className="flex gap-2">
                              <button
                                disabled={busy}
                                onClick={() =>
                                  void act(async () => {
                                    await deleteMemory(r.id);
                                    setConfirmForget(null);
                                    setExpanded(null);
                                  })
                                }
                                className="rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40"
                                style={{
                                  border: '1px solid rgba(248,113,113,0.4)',
                                  color: 'rgb(248,113,113)',
                                }}
                              >
                                Delete for good
                              </button>
                              <button
                                onClick={() => setConfirmForget(null)}
                                className="rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-2 flex-wrap">
                            {/* A superseded fact cannot be corrected again — the
                                chain would fork — so it only offers deletion. */}
                            {!superseded && (
                              <>
                                <button
                                  disabled={busy}
                                  onClick={() => {
                                    setEditing(r.id);
                                    setDraft(r.content);
                                  }}
                                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                                  style={{ border: '1px solid var(--color-border-subtle)' }}
                                >
                                  <Pencil size={12} />
                                  Correct
                                </button>
                                <button
                                  disabled={busy}
                                  onClick={() => void act(() => pinMemory(r.id, !r.pinned))}
                                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
                                  style={{ border: '1px solid var(--color-border-subtle)' }}
                                >
                                  {r.pinned ? <PinOff size={12} /> : <Pin size={12} />}
                                  {r.pinned ? 'Unpin' : 'Pin'}
                                </button>
                                {/* Where the fact belongs. Rule 7i keeps this as
                                    one field on one store, so this is a move and
                                    not a copy — and it is the multiplayer
                                    boundary, since project memory is shareable
                                    and global memory never is. The label says
                                    what global *means* rather than naming the
                                    scope string, because "about you" is the part
                                    that decides whether it belongs there. */}
                                <label
                                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-300"
                                  style={{ border: '1px solid var(--color-border-subtle)' }}
                                >
                                  <span className="text-slate-500">Belongs to</span>
                                  <select
                                    disabled={busy}
                                    value={scopeProjectId(r.scope) ?? ''}
                                    onChange={(e) => void act(() => setMemoryScope(r.id, e.target.value))}
                                    aria-label="Which project this fact belongs to"
                                    className="bg-transparent text-[11px] outline-none disabled:opacity-40"
                                    style={{ color: 'var(--color-text)' }}
                                  >
                                    <option value="" style={{ color: '#000' }}>
                                      you (global)
                                    </option>
                                    {projects.map((p) => (
                                      <option key={p.id} value={p.id} style={{ color: '#000' }}>
                                        {p.name}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              </>
                            )}
                            <button
                              disabled={busy}
                              onClick={() => setConfirmForget(r.id)}
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] transition-colors disabled:opacity-40 hover:bg-white/5"
                              style={{
                                border: '1px solid var(--color-border-subtle)',
                                color: 'rgb(248,113,113)',
                              }}
                            >
                              <Trash2 size={12} />
                              Forget
                            </button>
                            <div className="flex-1" />
                            <button
                              onClick={(e) => openSource(`memory:${r.id}`, e.currentTarget)}
                              className="rounded-lg px-3 py-1.5 text-[11px] text-slate-400 hover:bg-white/5 transition-colors"
                            >
                              Open source
                            </button>
                            <button
                              onClick={() => setExpanded(null)}
                              aria-label="Collapse"
                              className="p-1.5 rounded-lg text-slate-500 hover:bg-white/5 transition-colors"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        </>
      ) : (
        <Commitments onCounts={setCommitments} />
      )}
    </div>
  );
}
