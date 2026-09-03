/**
 * Markup written in a reply, shown as a page rather than as characters.
 *
 * The same treatment `ArtifactPreview` and `CitationPanel` use: it comes
 * forward over the orb with the background blurred, stopping where the
 * conversation begins, so the exchange that produced the code stays on screen
 * beside what it produced. One way to bring something forward is a thing users
 * learn once.
 *
 * Sealed, not inert
 * -----------------
 * The frame runs the page's own script and can still reach nothing. That
 * combination is the whole design, and it is `APP_SANDBOX` plus `APP_CSP` in
 * `lib/previewableCode` that produces it: `allow-scripts` **without**
 * `allow-same-origin` gives the frame an opaque origin — no reach into this
 * app's DOM or storage — while `default-src 'none'` covers `connect-src`, so
 * `fetch`, `XHR`, `WebSocket` and `EventSource` are refused. No navigation, no
 * popups, no modals, no remote sub-resource.
 *
 * **This shipped inert first, and that was a misreading of our own rule.** The
 * first version used `sandbox=""` and justified it as "executing model-written
 * code is the mutative tier". The tier table grades by *consequence*: a script
 * that cannot touch state and cannot reach the network changes pixels, which
 * is the generative tier. The label had been applied instead of the test, and
 * what it produced was a calculator that could not add up — a preview that
 * makes working code look broken.
 *
 * `ArtifactPreview` is unchanged and still runs nothing. An invoice has no use
 * for a script, so granting it one would be surface bought for nothing.
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, Info } from 'lucide-react';
import { useLayoutStore } from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useViewport } from '@/hooks/useViewport';
import { APP_SANDBOX, wrapForPreview, type PreviewableBlock } from '@/lib/previewableCode';

export default function CodePreviewPanel({
  block,
  onClose,
}: {
  block: PreviewableBlock;
  onClose: () => void;
}) {
  // The panel occupies the orb's half of the window. Derived from the same
  // fraction the conversation panel uses, so the two cannot disagree when the
  // divider is dragged — a hardcoded percentage drifts the moment anyone moves
  // it. Copied in shape from `ArtifactPreview` because they are the same panel
  // in two places, not two designs.
  const context = useChatModeStore((s) => s.context);
  const landingFraction = useLayoutStore((s) => s.chatFraction);
  const workspaceFraction = useLayoutStore((s) => s.chatFractionWorkspace);
  const chatFraction = context === 'workspace' ? workspaceFraction : landingFraction;
  const { width: viewportWidth } = useViewport();
  const panelWidth = viewportWidth * chatFraction;

  // What the page reported about itself, if anything went wrong.
  //
  // The frame has an opaque origin, so nothing here can look inside it to find
  // out why a button did nothing. `ERROR_REPORTER` makes the page volunteer it
  // instead. Filtered by `source`, because a `message` listener on the window
  // hears every frame on the page and an unfiltered one would let any of them
  // write into this panel.
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [fault, setFault] = useState<string | null>(null);

  useEffect(() => {
    setFault(null);
    const onMessage = (event: MessageEvent) => {
      if (!frameRef.current || event.source !== frameRef.current.contentWindow) return;
      const data = event.data as { __zaramPreview?: boolean; kind?: string; detail?: string };
      if (!data || data.__zaramPreview !== true) return;
      // First fault only. A page that throws on every animation frame would
      // otherwise rewrite this line hundreds of times a second, and the first
      // one is the one that explains the rest.
      setFault((current) => current ?? `${data.kind === 'blocked' ? 'Blocked' : 'Error'}: ${data.detail ?? ''}`);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [block.code]);

  // Registered on the window because focus is inside a sandboxed iframe most of
  // the time, where a React key handler on the panel would never see the event.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Rendered into `document.body`. Every `position: fixed` measurement below
  // assumes the viewport is the containing block, and an ancestor carrying
  // `transform`, `filter` or `backdrop-filter` silently becomes that block
  // instead — which is how the artifact panel once collapsed to a sliver
  // inside a blurred sidebar. The portal makes the guarantee structural rather
  // than a rule every future mount site has to remember.
  return createPortal(
    <motion.div
      className="fixed top-0 bottom-0 left-0 z-[90] flex items-center justify-center p-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
      style={{
        right: panelWidth,
        background: 'rgba(2,6,23,0.55)',
        backdropFilter: 'blur(24px) saturate(1.4)',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${block.label} preview`}
    >
      <motion.div
        className="flex flex-col overflow-hidden rounded-2xl"
        style={{
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
            {block.label} from this reply
          </span>
          <span className="text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
            preview
          </span>
          <div className="flex-1" />
          <button
            onClick={onClose}
            aria-label="Close preview"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          <iframe
            ref={frameRef}
            title={`${block.label} preview`}
            srcDoc={wrapForPreview(block.code, 'app')}
            // `allow-scripts` and nothing else. Adding `allow-same-origin`
            // beside it would not widen the sandbox, it would dissolve it —
            // the frame could reach in and remove this very attribute. See
            // `APP_SANDBOX`, which is asserted against that in tests.
            sandbox={APP_SANDBOX}
            className="h-full w-full"
            style={{ border: 0, background: '#fff' }}
          />
        </div>

        {/* What the frame can and cannot do, stated where it is happening.
            This is the product's own claim about custody applied to itself:
            the user is watching model-written code run, and is entitled to
            know what it is sealed off from without opening a settings page. */}
        <div
          className="flex items-center gap-2 px-4 py-2"
          style={{
            borderTop: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          <Info size={12} />
          <span className="text-[11px]">
            {fault ?? "Runs here only — no network, and no access to your files or Zaram's data."}
          </span>
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
