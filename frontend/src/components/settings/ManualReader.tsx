/**
 * The manual, readable — Settings → Help → Open the manual.
 *
 * The same ten pages the Zaram domain recalls from, for the person who wants
 * the page rather than the answer. Pages down the left, the page on the
 * right, rendered with the renderer the chat already uses so headings, lists
 * and pictures look like the rest of the product. Pictures come from the
 * backend's own `/manual/assets/` route, never from anywhere else.
 *
 * A dialog rather than a seventh node: the manual is help, not a place, and
 * `CLAUDE.md` guards the count.
 */

import { onOpen } from '@/lib/openInBrowser';
import { useCallback, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { X } from 'lucide-react';

import { fetchManual, fetchManualPage, manualAssetUrl, type ManualIndex } from '@/services/manualClient';

export interface ManualReaderProps {
  onClose: () => void;
  /** Overrides, for tests. */
  load?: () => Promise<ManualIndex>;
  loadPage?: (slug: string) => Promise<string>;
  /** Open on this page rather than the first. */
  initialSlug?: string;
}

export default function ManualReader({ onClose, load = fetchManual, loadPage = fetchManualPage, initialSlug }: ManualReaderProps) {
  const [index, setIndex] = useState<ManualIndex | null>(null);
  const [slug, setSlug] = useState<string | null>(initialSlug ?? null);
  const [markdown, setMarkdown] = useState<string>('');
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((idx) => {
        if (cancelled) return;
        setIndex(idx);
        setSlug((current) => current ?? idx.pages[0]?.slug ?? null);
      })
      .catch((e) => !cancelled && setProblem(e instanceof Error ? e.message : 'The manual could not be read.'));
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    loadPage(slug)
      .then((md) => !cancelled && setMarkdown(md))
      .catch((e) => !cancelled && setProblem(e instanceof Error ? e.message : 'The page could not be read.'));
    return () => {
      cancelled = true;
    };
  }, [slug, loadPage]);

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  const behind = index && index.indexedVersion !== null && index.indexedVersion !== index.version;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="The Zaram manual"
      className="fixed inset-0 z-[95] flex items-center justify-center p-6"
      style={{ background: 'rgba(5, 6, 12, 0.72)' }}
      onKeyDown={onKey}
    >
      <div
        className="rounded-2xl flex overflow-hidden"
        style={{
          width: 'min(1040px, 100%)',
          height: 'min(760px, 100%)',
          // Opaque on purpose: the surface material is translucent glass, and a
          // manual read through the settings behind it is not readable.
          background: 'var(--color-surface, #12151c)',
          border: '1px solid var(--color-border-subtle)',
          color: 'var(--color-text)',
        }}
      >
        <nav
          className="flex flex-col shrink-0 py-4"
          style={{ width: 232, borderRight: '1px solid var(--color-border-subtle)' }}
          aria-label="Pages"
        >
          <span className="t-kicker px-5 pb-3" style={{ color: 'var(--color-text-muted)' }}>
            The manual
          </span>
          {index?.pages.map((p) => (
            <button
              key={p.slug}
              type="button"
              onClick={() => setSlug(p.slug)}
              className="text-left px-5 py-2 text-sm"
              style={{
                color: p.slug === slug ? 'var(--color-text)' : 'var(--color-text-muted)',
                background: p.slug === slug ? 'rgba(255,255,255,0.05)' : 'transparent',
              }}
              aria-current={p.slug === slug ? 'page' : undefined}
              data-testid={`manual-page-${p.slug}`}
            >
              {p.title}
            </button>
          ))}
          {behind && (
            <p className="px-5 pt-4 text-xs" style={{ color: 'var(--color-text-faint)' }}>
              Zaram is still reading the new pages into its memory.
            </p>
          )}
        </nav>
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex items-center justify-end px-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close the manual"
              className="p-2 rounded-lg"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <X size={16} />
            </button>
          </div>
          <article className="manual-article reading-column flex-1 overflow-auto px-8 pb-10" data-testid="manual-article">
            {problem ? (
              <p className="text-sm" style={{ color: 'var(--color-amber, #fbbf24)' }}>
                {problem}
              </p>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  img: ({ src, alt }) => (
                    <figure className="my-4">
                      <img src={manualAssetUrl(String(src ?? ''))} alt={alt ?? ''} style={{ maxWidth: '100%', borderRadius: 10 }} />
                      {alt && (
                        <figcaption className="text-xs mt-2" style={{ color: 'var(--color-text-faint)' }}>
                          {alt}
                        </figcaption>
                      )}
                    </figure>
                  ),
                  // Through the shell bridge: the packaged app denies a
                  // window-open, so a plain `target="_blank"` here was a
                  // dead link on every page of the manual.
                  a: ({ href, children }) => (
                    <a href={href} onClick={onOpen(href)} rel="noreferrer" style={{ color: 'var(--color-indigo-light)' }}>
                      {children}
                    </a>
                  ),
                }}
              >
                {markdown}
              </ReactMarkdown>
            )}
          </article>
        </div>
      </div>
    </div>
  );
}
