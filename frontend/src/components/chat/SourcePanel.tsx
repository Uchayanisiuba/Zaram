/**
 * Source panel — what Zaram remembered, and the means to remove it.
 *
 * A citation you can only read is half of rule 2. This makes it inspectable,
 * and puts deletion in the same place, which is where rule 4's loop closes:
 * open the source, see the stored fact, delete it, ask again and watch the
 * answer change.
 *
 * Motion follows the platform convention for a presented panel — it scales up
 * slightly from behind while the backdrop blurs in, rather than sliding. Spring
 * physics on the way in, a quicker tween on the way out, because a dismissal
 * that lingers feels unresponsive. Honours reduced motion.
 *
 * Focus is trapped while open and returned to the citation that opened it. A
 * dialog that drops focus at the top of the page is unusable with a keyboard.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, type Variants } from 'framer-motion';
import { X, Trash2, Loader2, ExternalLink } from 'lucide-react';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { fetchMemory, deleteMemory, type MemoryRecord } from '@/services/memoryClient';

export interface SourcePanelProps {
  /** Provenance URL, e.g. "memory:1a2b-...". */
  url: string;
  /** Cascade placement, so several panels stay readable without overlapping. */
  offset?: { x: number; y: number };
  /** Stack order; later panels sit above earlier ones. */
  depth?: number;
  /** Element to restore focus to on close — the citation that opened this. */
  returnFocusTo?: HTMLElement | null;
  onClose: () => void;
  /** Called after a successful delete so the transcript can mark it removed. */
  onDeleted?: (id: string) => void;
}

/** Apple-style presentation: scale from slightly behind, spring in, tween out. */
const panel: Variants = {
  hidden: { opacity: 0, scale: 0.94, y: 8 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 380, damping: 30, mass: 0.8 },
  },
  exit: {
    opacity: 0,
    scale: 0.97,
    y: 4,
    transition: { duration: 0.16, ease: [0.4, 0, 1, 1] },
  },
};

const panelReduced: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.15 } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};

export default function SourcePanel({
  url,
  offset = { x: 0, y: 0 },
  depth = 0,
  returnFocusTo,
  onClose,
  onDeleted,
}: SourcePanelProps) {
  const reduced = useIsReducedMotion();
  const [record, setRecord] = useState<MemoryRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const memoryId = url.startsWith('memory:') ? url.slice('memory:'.length) : null;

  /** A cited page, as opposed to a remembered fact.
   *
   *  **Clicking one used to do nothing useful.** This panel only ever handled
   *  `memory:` URLs, so every web citation — the whole output of a search —
   *  fell into "This source is not a stored memory." and offered no way to
   *  reach the page. A citation you cannot open is not a citation, which is
   *  half of rule 2 missing precisely where the user is most likely to check:
   *  a claim Zaram made about the world. */
  const webUrl = /^https?:\/\//i.test(url) ? url : null;
  const host = (() => {
    try {
      return webUrl ? new URL(webUrl).host : null;
    } catch {
      return null;
    }
  })();

  /** Hand the page to the user's real browser.
   *
   *  Never in-app. A page opened inside Zaram would be a browser nobody
   *  audited, running third-party script beside the Spine, and the egress from
   *  it would be invisible to `EgressGate` — which intercepts what the
   *  *backend* sends. The system browser is the honest place for somebody
   *  else's page, and it is where the user's own blockers and sessions live.
   *
   *  `window.open` is the fallback for a plain browser tab during development,
   *  with `noopener` so the opened page cannot reach back through
   *  `window.opener`. */
  const openInBrowser = useCallback(() => {
    if (!webUrl) return;
    const shell = window.zaram?.shell?.openExternal;
    if (typeof shell === 'function') {
      void shell(webUrl);
      return;
    }
    window.open(webUrl, '_blank', 'noopener,noreferrer');
  }, [webUrl]);

  useEffect(() => {
    if (webUrl) {
      // Nothing to fetch: the panel shows where the claim came from and opens
      // it. The page itself is deliberately not retrieved here — see above.
      setLoading(false);
      setError(null);
      return;
    }
    if (!memoryId) {
      setError('This source is not a stored memory.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    fetchMemory(memoryId, controller.signal)
      .then((r) => {
        if (!cancelled) {
          setRecord(r);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load this source.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [memoryId, webUrl]);

  // Return focus where it came from. Without this, closing drops the caret at
  // the top of the document and the keyboard user loses their place.
  const close = useCallback(() => {
    onClose();
    // After the exit animation has begun; the element is still in the DOM.
    requestAnimationFrame(() => returnFocusTo?.focus?.());
  }, [onClose, returnFocusTo]);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close();
        return;
      }
      // Keep Tab inside the panel while it is open.
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [close]);

  const handleDelete = async () => {
    if (!memoryId) return;
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setDeleting(true);
    try {
      await deleteMemory(memoryId);
      onDeleted?.(memoryId);
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete this memory.');
      setDeleting(false);
      setConfirming(false);
    }
  };

  return (
    <motion.div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Source detail"
        className="glass-strong absolute flex flex-col rounded-2xl overflow-hidden pointer-events-auto"
        style={{
          width: 'min(400px, 82%)',
          maxHeight: '68%',
          left: '50%',
          top: '50%',
          x: '-50%',
          y: '-50%',
          marginLeft: offset.x,
          marginTop: offset.y,
          zIndex: 70 + depth,
          boxShadow: '0 24px 80px rgba(0,0,0,0.55)',
        }}
        variants={reduced ? panelReduced : panel}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-white/5">
          <span
            className="text-[10px] uppercase text-slate-500"
            style={{ letterSpacing: '0.08em', fontFamily: 'var(--font-display)' }}
          >
            {webUrl ? 'From the web' : 'Remembered'}
          </span>
          <div className="flex-1" />
          <button
            ref={closeRef}
            onClick={close}
            aria-label="Close source"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 size={14} className="animate-spin" />
              Loading source…
            </div>
          )}

          {error && !loading && (
            <p className="text-xs leading-relaxed" style={{ color: '#fca5a5' }}>
              {error}
            </p>
          )}

          {/* A cited page. The full URL is shown rather than only the host,
              because the whole reason to open a citation is to check it, and
              the path is the half that says which article. */}
          {webUrl && !loading && (
            <>
              {host && (
                <p className="text-sm text-slate-200" style={{ fontFamily: 'var(--font-display)' }}>
                  {host}
                </p>
              )}
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500 break-all">{webUrl}</p>
              <p className="mt-4 pt-3 border-t border-white/5 text-[11px] leading-relaxed text-slate-500">
                Zaram fetched this page to answer, so it is in your Activity log.
                Opening it now is a fresh visit, made by your browser rather than
                by Zaram.
              </p>
            </>
          )}

          {record && !loading && (
            <>
              <p className="text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
                {record.content}
              </p>
              <dl className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-y-1.5 text-[11px]">
                <dt className="text-slate-500">Stored</dt>
                <dd className="text-slate-400">
                  {new Date(record.created_at * 1000).toLocaleString()}
                </dd>
                <dt className="text-slate-500">Recalled</dt>
                <dd className="text-slate-400">
                  {record.access_count} time{record.access_count === 1 ? '' : 's'}
                </dd>
                <dt className="text-slate-500">Type</dt>
                <dd className="text-slate-400">{record.memory_type}</dd>
              </dl>
            </>
          )}
        </div>

        {/* Actions */}
        {webUrl && !loading && (
          <div className="px-5 py-3 border-t border-white/5 flex items-center gap-2">
            <button
              onClick={openInBrowser}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors hover:bg-white/5"
              style={{ color: 'var(--color-text)' }}
            >
              <ExternalLink size={14} />
              Open in your browser
            </button>
          </div>
        )}

        {record && !loading && (
          <div className="px-5 py-3 border-t border-white/5 flex items-center gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
              style={{
                color: confirming ? '#fca5a5' : 'var(--color-text-muted)',
                background: confirming ? 'rgba(248,113,113,0.10)' : 'transparent',
              }}
            >
              {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              {deleting ? 'Forgetting…' : confirming ? 'Delete for good?' : 'Forget this'}
            </button>
            {confirming && !deleting && (
              <button
                onClick={() => setConfirming(false)}
                className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
            )}
            <div className="flex-1" />
            {confirming && (
              <span className="text-[10px] text-slate-500">Answers will change</span>
            )}
          </div>
        )}
    </motion.div>
  );
}
