/**
 * A generated document, shown before it is opened anywhere else.
 *
 * Why this is cheap to be faithful about
 * --------------------------------------
 * `CLAUDE.md` makes **HTML the source of truth for every generated document** —
 * WeasyPrint converts it to PDF, a second export produces .docx — specifically
 * so that a preview is not a second renderer that can drift. What is shown here
 * is the same HTML the file was built from, so "what you see is what
 * downloads" is structural rather than a promise somebody has to maintain.
 *
 * Sandboxed, and that is not paranoia about our own output
 * -------------------------------------------------------
 * The HTML is *model-generated*. `dangerouslySetInnerHTML` would run any
 * `<script>` and load any `<img src="https://…">` inside it, with the second
 * being the more likely and the worse: an external URL in generated markup is a
 * request the egress gate cannot see, because that gate intercepts what the
 * **backend** sends. Exactly the hole `vrmSafety` was written to close for
 * avatar files, arriving by a different route.
 *
 * So the document renders in an `<iframe srcDoc>` with an empty `sandbox`
 * attribute: no scripts, no forms, no same-origin access, no top-level
 * navigation. Remote sub-resources are additionally refused by a CSP in the
 * injected head, so a stray image URL fails to load rather than quietly
 * reporting to whoever wrote it.
 *
 * Over the orb, not beside it
 * ---------------------------
 * The maintainer asked for the panel to sit over the avatar with the background
 * blurred, which is the treatment `CitationPanel` already uses when a citation
 * is opened. Same idea reused rather than a second overlay invented: one way to
 * bring something forward is a thing users learn once.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, Download, FileWarning, Loader2 } from 'lucide-react';
import {
  downloadArtifact,
  getArtifact,
  PICTORIAL_KINDS,
  type Artifact,
} from '@/services/artifactsClient';
import { useArtifactImage } from '@/hooks/useArtifactImage';
import { useLayoutStore } from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useViewport } from '@/hooks/useViewport';
import { wrapForPreview } from '@/lib/previewableCode';

/** The CSP and page styling now live in `lib/previewableCode`, shared with the
 *  in-conversation code preview.
 *
 *  Two copies of a security header is drift waiting to happen: the one that
 *  gets read is edited and the other keeps a weaker rule, with nothing
 *  reporting the difference. One definition, both surfaces. */

export default function ArtifactPreview({
  artifact,
  onClose,
}: {
  artifact: Artifact;
  onClose: () => void;
}) {
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The panel occupies **the orb's half of the window**, not the whole of it.
  //
  // Covering everything would hide the conversation the file came from, which
  // is the context that makes the document make sense — and it would put the
  // preview over the message you clicked, so closing it is the only way to see
  // what you asked for. Sitting where the orb is keeps both on screen: the
  // document on the left, the exchange that produced it on the right.
  //
  // The width is derived from the same fraction the conversation panel and the
  // orb's own offset are derived from, so the three cannot disagree — the
  // panel is resizable, and a hardcoded 55% would drift the moment anybody
  // dragged the divider.
  const context = useChatModeStore((s) => s.context);
  const landingFraction = useLayoutStore((s) => s.chatFraction);
  const workspaceFraction = useLayoutStore((s) => s.chatFractionWorkspace);
  const chatFraction = context === 'workspace' ? workspaceFraction : landingFraction;
  const { width: viewportWidth } = useViewport();
  const panelWidth = viewportWidth * chatFraction;

  // **A picture previews as itself, not as the page it was embedded in.**
  //
  // For every other kind the HTML *is* the faithful preview, because the HTML
  // is what WeasyPrint and the .docx exporter render from — so what is on
  // screen is what downloads, structurally rather than by promise.
  //
  // For an image that reasoning inverts. The file that downloads is the PNG;
  // the HTML is the envelope it was carried in, complete with an A4 sheet, a
  // title and a "How this was made" list. Rendering the envelope would put a
  // *document about the picture* in a panel opened to look at the picture, and
  // would be the less faithful of the two — the exported file is the image
  // itself.
  const pictorial = PICTORIAL_KINDS.has(artifact.kind);
  const picture = useArtifactImage(artifact.id, pictorial && artifact.exists);

  useEffect(() => {
    if (pictorial) return;

    let cancelled = false;
    setHtml(null);
    setError(null);

    getArtifact(artifact.id, true)
      .then((full) => {
        if (cancelled) return;
        const source = full.html ?? '';
        if (!source.trim()) {
          // A record with no HTML is a real state — an artifact produced by a
          // path that did not keep its source. Saying so beats an empty white
          // rectangle, which reads as a broken preview.
          setError('This document has no stored HTML, so it cannot be previewed here.');
          return;
        }
        setHtml(wrapForPreview(source));
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not read the document.');
      });

    return () => {
      cancelled = true;
    };
  }, [artifact.id, pictorial]);

  // Escape closes it, matching the citation panel. Registered on the window
  // because focus is inside a sandboxed iframe most of the time, where a
  // React key handler on the panel would never see the event.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Rendered into `document.body`, not into the tree that mounted it.
  //
  // Every `position: fixed` measurement below assumes the **viewport** is the
  // containing block. That is not this component's assumption to make: an
  // ancestor carrying `transform`, `filter` or `backdrop-filter` becomes the
  // containing block for fixed descendants instead, and then an ancestor's
  // `overflow: hidden` clips them too - which it does not do to an element
  // that is genuinely fixed to the viewport.
  //
  // `WorkWorkspace`'s detail sidebar is exactly that: `backdrop-filter:
  // blur(24px)` on a 520px column with `overflow: hidden`. Mounted inside it,
  // this panel resolved `right: panelWidth` - a fraction of the *viewport* -
  // against 520px and was clipped to a sliver; above a viewport of ~1857px
  // `panelWidth` exceeds 520 outright and the panel collapses to zero width,
  // which is a preview that opens onto nothing.
  //
  // Measured rather than reasoned about: the same element reported width 816
  // against the viewport and width 202 inside the blurred aside, with the blur
  // as the only variable.
  //
  // The portal makes the guarantee structural instead of a rule every future
  // mount site has to remember. The blur on that sidebar is deliberate and
  // stays.
  return createPortal(
    <motion.div
      className="fixed top-0 bottom-0 left-0 z-[90] flex items-center justify-center p-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
      // Stops where the conversation panel begins. `right` rather than a width,
      // so the two meet exactly however the divider has been dragged.
      //
      // The orb or the avatar recedes behind this rather than being hidden —
      // the same treatment a citation gets, so "something came forward" reads
      // the same way wherever it happens.
      style={{
        right: panelWidth,
        background: 'rgba(2,6,23,0.55)',
        backdropFilter: 'blur(24px) saturate(1.4)',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Preview of ${artifact.filename}`}
    >
      <motion.div
        className="flex flex-col overflow-hidden rounded-2xl"
        style={{
          // Fills the orb's region rather than assuming a desktop-width dialog:
          // that space is roughly 55% of the window by default and narrower on
          // a working surface, so a fixed 880px would overflow it.
          width: '100%',
          maxWidth: 880,
          height: 'min(80vh, 100%)',
          background: 'var(--color-glass)',
          border: '1px solid var(--color-border)',
        }}
        initial={{ scale: 0.98, y: 8 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ duration: 0.22 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          className="flex items-center gap-3 px-4 py-3"
          style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
        >
          <span className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
            {artifact.filename}
          </span>
          <span className="text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
            preview
          </span>
          <div className="flex-1" />
          {/* A button rather than an anchor. `RequireApiSecret` authenticates
              every request and the credential rides on a wrapper around
              `fetch`; a link navigates without it and gets 401. */}
          <button
            type="button"
            onClick={() => {
              setError(null);
              downloadArtifact(artifact.id, artifact.filename).catch((err: unknown) =>
                setError(
                  err instanceof Error ? err.message : 'Could not download that file.',
                ),
              );
            }}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] hover:bg-white/5"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            <Download size={12} />
            Download
          </button>
          <button
            onClick={onClose}
            aria-label="Close preview"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          {pictorial ? (
            picture.error ? (
              <div
                className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <FileWarning size={20} />
                <p className="text-xs leading-relaxed">{picture.error}</p>
              </div>
            ) : picture.url ? (
              // Checkerboard-free flat ground rather than white: a generated
              // image is as likely to be dark as light, and a white surround
              // makes a dark one look like a hole in the panel.
              <div
                className="flex h-full items-center justify-center p-4"
                style={{ background: 'var(--color-surface-sunken, #0b1120)' }}
              >
                <img
                  src={picture.url}
                  alt={artifact.filename}
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                />
              </div>
            ) : (
              <div
                className="flex h-full items-center justify-center"
                style={{ color: 'var(--color-text-faint)' }}
              >
                <Loader2 size={16} className="animate-spin" />
              </div>
            )
          ) : error ? (
            <div
              className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <FileWarning size={20} />
              <p className="text-xs leading-relaxed">{error}</p>
              <p className="text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
                Download it and open it in the app that owns it.
              </p>
            </div>
          ) : html === null ? (
            <div className="flex h-full items-center justify-center" style={{ color: 'var(--color-text-faint)' }}>
              <Loader2 size={16} className="animate-spin" />
            </div>
          ) : (
            <iframe
              title={`Preview of ${artifact.filename}`}
              srcDoc={html}
              // Empty sandbox: every capability denied. Adding
              // `allow-same-origin` here would let the document reach this
              // app's storage, and `allow-scripts` would let model-generated
              // markup execute — see the header.
              sandbox=""
              className="h-full w-full"
              style={{ border: 0, background: '#fff' }}
            />
          )}
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
