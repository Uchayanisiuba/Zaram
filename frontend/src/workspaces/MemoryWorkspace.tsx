/**
 * Memory — what Zaram actually knows.
 *
 * This screen previously showed a fabricated knowledge graph: 1,847 nodes, 284
 * conversations, "+23 today", a "last synced" time, and invented entities
 * including a person who does not exist. The Spine held about twenty records.
 * Every number and every node was made up.
 *
 * It now reports the Spine. If there are four records it shows four records,
 * and if there are none it says so and explains how to add one. Nothing here is
 * estimated, and a measurement that does not exist is shown as unknown rather
 * than as zero.
 *
 * This is not yet the Memory screen in docs/UI-SPEC.md — no view toggle, filter
 * chips or recall weighting, because the data model has no recallCount or
 * supersededBy to drive them. It is the honest version of what can be shown
 * today.
 */
import { useCallback, useEffect, useState } from 'react';
import { Brain, Search, RefreshCw, AlertCircle } from 'lucide-react';
import {
  fetchMemoryList,
  fetchMemoryStats,
  type MemoryRecord,
  type MemoryStats,
} from '@/services/memoryClient';
import { useSourceStore } from '@/stores/sourceStore';

const relative = (seconds: number) => {
  const delta = Date.now() / 1000 - seconds;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} hr ago`;
  return new Date(seconds * 1000).toLocaleDateString();
};

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

export default function MemoryWorkspace() {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const visible = records.filter((r) => !forgotten.has(`memory:${r.id}`));

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-8 pt-6 pb-4 flex items-center gap-3">
        <Brain size={20} style={{ color: 'var(--color-indigo-light)' }} />
        <h1
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          Memory
        </h1>
        <div className="flex-1" />
        <button
          onClick={() => void load(query)}
          aria-label="Refresh memory"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Measured counts only */}
      <div className="px-8 flex gap-3">
        <Metric label="Facts stored" value={stats ? String(stats.total_records) : '—'} />
        <Metric label="Sessions" value={stats ? String(stats.sessions) : '—'} />
        <Metric
          label="Left device today"
          // Null is not zero. There is no egress log yet, so this is unknown,
          // and claiming zero would be a privacy assurance we cannot support.
          value={
            stats?.bytes_left_device_today == null
              ? 'unknown'
              : String(stats.bytes_left_device_today)
          }
          note={stats?.bytes_left_device_today == null ? 'no egress log yet' : undefined}
        />
      </div>

      {/* Search */}
      <div className="px-8 pt-5 pb-3">
        <div className="relative">
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
      </div>

      {/* Records */}
      <div className="flex-1 overflow-y-auto px-8 pb-8">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg px-4 py-3 text-xs"
            style={{ background: 'rgba(248,113,113,0.08)', color: '#fca5a5' }}
          >
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!error && !loading && visible.length === 0 && (
          // Every list needs a way out, not a dead end.
          <div className="py-16 text-center">
            <p className="text-sm text-slate-400">
              {query ? 'Nothing matches that.' : 'Zaram has not learned anything yet.'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {query
                ? 'Try a different word, or clear the search.'
                : 'Open the conversation and tell it something — it will appear here.'}
            </p>
          </div>
        )}

        {visible.length > 0 && (
          <>
            <div className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
              {query
                ? `${visible.length} of ${stats?.total_records ?? '?'} match`
                : `${visible.length} shown`}
            </div>
            <ul className="flex flex-col gap-1.5">
              {visible.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={(e) => openSource(`memory:${r.id}`, e.currentTarget)}
                    className="w-full text-left rounded-lg px-4 py-3 transition-colors hover:bg-white/5"
                    style={{ border: '1px solid var(--color-border-subtle)' }}
                  >
                    <p className="text-sm leading-snug" style={{ color: 'var(--color-text)' }}>
                      {r.content}
                    </p>
                    <p
                      className="mt-1.5 text-[10px] text-slate-500"
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {r.memory_type} · {relative(r.created_at)} · recalled {r.access_count}×
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
