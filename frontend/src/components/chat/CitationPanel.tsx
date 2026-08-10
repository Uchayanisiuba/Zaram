/**
 * Every source behind one reply, grouped by whether bytes left the machine.
 *
 * `docs/UI-SPEC.md` → Citations. Right side, **the same anchor and animation as
 * fact detail — one pattern, not two**. Escape closes.
 *
 * Grouped by egress rather than by kind, because egress is the question the
 * user actually has. Headings state it in bytes, not in source counts: the
 * egress log counts bytes and so does this, and two different units for the
 * same fact is how a number stops being checkable.
 *
 * The web card links to its row in Activity. **That link is the citation and
 * the egress log being the same object viewed twice, and it is the thing
 * nobody else can build.**
 */
import { useEffect, useRef } from 'react';
import { motion, type Variants } from 'framer-motion';
import { X, FileText, Diamond, Globe, ExternalLink } from 'lucide-react';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { type ChatSource, sourceLeftDevice } from '@/services/chatClient';

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

const KIND_ICON = { document: FileText, memory: Diamond, web: Globe } as const;

function formatBytes(n: number): string {
  return n.toLocaleString();
}

/** Whether the excerpt would only repeat the title.
 *
 *  True for a `memory`, whose title is the fact itself truncated to chip
 *  length — printing both shows the same sentence twice. False for a
 *  `document`, whose title is a filename and whose excerpt is the passage that
 *  actually bore on the answer, which is the whole point. */
function addsNothing(source: ChatSource): boolean {
  const title = (source.title ?? '').replace(/\.\.\.$/, '').trim();
  if (!title || !source.excerpt) return true;
  return source.excerpt.trim().startsWith(title);
}

function SourceCard({
  source,
  forgotten,
  onCorrect,
  onOpenActivity,
}: {
  source: ChatSource;
  forgotten: boolean;
  onCorrect: (source: ChatSource) => void;
  onOpenActivity: () => void;
}) {
  const Icon = KIND_ICON[source.kind];
  const left = sourceLeftDevice(source);

  return (
    <li className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
      <div className="flex items-start gap-2">
        {/* The number matches the inline chip exactly, so a chip maps to its
            card instantly. Assigned server-side for that reason. */}
        <span
          className="shrink-0 mt-0.5 inline-flex items-center gap-1 text-[10px]"
          style={{ color: left ? 'rgb(196,152,252)' : 'rgb(120,220,240)' }}
        >
          <Icon size={10} aria-hidden />
          {source.number ?? '·'}
        </span>
        <div className="min-w-0 flex-1">
          <p
            className="text-[11px] text-slate-300 break-words"
            style={{ textDecoration: forgotten ? 'line-through' : 'none' }}
          >
            {source.title ?? source.url}
            {forgotten && <span className="ml-1 text-slate-600">— forgotten</span>}
          </p>

          {/* The passage, quoted with a left border. Without it a citation
              cannot be checked, which is the only thing a citation is for.
              But for a `memory` the title *is* the fact, so an excerpt would
              print the same sentence twice — and an equality check does not
              catch it, because the title is truncated at 120 characters and
              the excerpt at 400, so the two are never equal. Compared on the
              prefix instead. Found by driving it: the panel showed one fact
              twice, which reads as a bug in recall rather than in layout. */}
          {source.excerpt && !addsNothing(source) && (
            <p className="mt-1.5 pl-2 border-l border-white/10 text-[10px] leading-relaxed text-slate-500 break-words">
              {source.excerpt}
            </p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
            {source.relevance != null && (
              <span title="Similarity to your question, not a ranking blend">
                relevance {source.relevance.toFixed(2)}
              </span>
            )}
            {source.origin && <span>{source.origin.replace(/_/g, ' ')}</span>}
            {source.bytesSent != null && (
              <span style={{ color: 'rgb(196,152,252)' }}>
                {formatBytes(source.bytesSent)} bytes sent
              </span>
            )}
          </div>

          <div className="mt-1.5 flex items-center gap-3">
            {/* The fastest correction path in the product, sitting exactly
                where the user is already checking. */}
            {source.kind !== 'web' && source.recordId && (
              <button
                type="button"
                onClick={() => onCorrect(source)}
                className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
              >
                Correct or forget
              </button>
            )}
            {source.kind === 'web' && (
              <button
                type="button"
                onClick={onOpenActivity}
                className="inline-flex items-center gap-1 text-[10px] transition-colors hover:opacity-80"
                style={{ color: 'rgb(196,152,252)' }}
              >
                <ExternalLink size={9} aria-hidden />
                {source.egressId ? 'See what left, in Activity' : 'Open Activity'}
              </button>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

export default function CitationPanel({
  sources,
  deleted,
  returnFocusTo,
  onClose,
  onCorrect,
  onOpenActivity,
}: {
  sources: ChatSource[];
  deleted: Set<string>;
  returnFocusTo?: HTMLElement | null;
  onClose: () => void;
  onCorrect: (source: ChatSource) => void;
  onOpenActivity: () => void;
}) {
  const reduced = useIsReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', onKey);
    ref.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      // A dialog that drops focus at the top of the page is unusable with a
      // keyboard, so it goes back to the control that opened this.
      returnFocusTo?.focus?.();
    };
  }, [onClose, returnFocusTo]);

  const cited = sources.filter((s) => s.cited);
  const uncited = sources.filter((s) => !s.cited);
  const stayed = cited.filter((s) => !sourceLeftDevice(s));
  const left = cited.filter(sourceLeftDevice);
  const bytesLeft = left.reduce((sum, s) => sum + (s.bytesSent ?? 0), 0);

  return (
    <motion.div
      ref={ref}
      tabIndex={-1}
      role="dialog"
      aria-label="Sources for this reply"
      variants={reduced ? panelReduced : panel}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="pointer-events-auto w-[22rem] max-h-[70vh] overflow-y-auto rounded-2xl border border-white/10 p-3 outline-none"
      style={{
        background: 'var(--color-glass, rgba(15,18,26,0.92))',
        backdropFilter: 'blur(24px) saturate(1.4)',
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <h2
          className="text-[11px] uppercase text-slate-400"
          style={{ letterSpacing: '0.08em', fontFamily: 'var(--font-display)' }}
        >
          Sources
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close sources"
          className="p-1 rounded hover:bg-white/5 text-slate-400"
        >
          <X size={13} />
        </button>
      </div>

      {stayed.length > 0 && (
        <section className="mb-3">
          <p
            className="text-[10px] mb-1.5 text-slate-500"
            style={{ fontFamily: 'var(--font-mono, monospace)' }}
          >
            nothing left this device
          </p>
          <ul className="flex flex-col gap-1.5">
            {stayed.map((s, i) => (
              <SourceCard
                key={s.url ?? `stayed-${i}`}
                source={s}
                forgotten={s.url != null && deleted.has(s.url)}
                onCorrect={onCorrect}
                onOpenActivity={onOpenActivity}
              />
            ))}
          </ul>
        </section>
      )}

      {left.length > 0 && (
        <section className="mb-3">
          <p
            className="text-[10px] mb-1.5"
            style={{
              fontFamily: 'var(--font-mono, monospace)',
              color: 'rgb(196,152,252)',
            }}
          >
            {/* Bytes, not "1 source". The egress log counts bytes and so does
                this. When the search path did not report a size we say the
                count instead of inventing a number. */}
            {bytesLeft > 0
              ? `${formatBytes(bytesLeft)} bytes left this device`
              : `${left.length} request${left.length === 1 ? '' : 's'} left this device`}
          </p>
          <ul className="flex flex-col gap-1.5">
            {left.map((s, i) => (
              <SourceCard
                key={s.url ?? `left-${i}`}
                source={s}
                forgotten={s.url != null && deleted.has(s.url)}
                onCorrect={onCorrect}
                onOpenActivity={onOpenActivity}
              />
            ))}
          </ul>
        </section>
      )}

      {/* Quieter, and present. Nothing is hidden — it is simply not
          interrupting the prose. This is where the gap between
          MIN_RECALL_SCORE and MIN_CITATION_SCORE becomes visible and therefore
          arguable. */}
      {uncited.length > 0 && (
        <section className="pt-2 border-t border-white/5">
          <p className="text-[10px] text-slate-500 mb-1.5">
            Recalled but not cited — read, and not what carried the answer
          </p>
          <ul className="flex flex-col gap-1">
            {uncited.map((s, i) => (
              <li
                key={s.url ?? `uncited-${i}`}
                className="text-[10px] text-slate-500 truncate"
                title={s.excerpt ?? s.title ?? ''}
              >
                {s.title ?? s.url}
                {s.relevance != null && (
                  <span className="text-slate-600"> · {s.relevance.toFixed(2)}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </motion.div>
  );
}
