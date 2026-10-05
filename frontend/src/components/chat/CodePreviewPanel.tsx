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
 * **Then it shipped scriptable and storage-less, which was the same mistake
 * one layer down.** An opaque origin does not hand a frame an empty
 * `localStorage`; it hands it one that *throws* on the first read. A generated
 * Tetris opens by reading its high score, so it died on line one and rendered
 * a black canvas — working code made to look broken a second time, by the seal
 * rather than by the label. `SEALED_STORAGE` gives the frame a map of its own,
 * which is strictly less than real storage and discarded with the panel.
 *
 * `ArtifactPreview` is unchanged and still runs nothing. An invoice has no use
 * for a script, so granting it one would be surface bought for nothing.
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, Info, Download, Pause, Play, RotateCcw, Code2, Eye, Copy, Check } from 'lucide-react';
import { useLayoutStore } from '@/stores/layoutStore';
import { recordBrowsed } from '@/services/egressClient';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useViewport } from '@/hooks/useViewport';
import {
  APP_SANDBOX,
  filenameFor,
  savePreviewable,
  wrapForPreview,
  type PreviewableBlock,
} from '@/lib/previewableCode';

/** The host a policy refusal names, or `null` when there is nothing to name.
 *
 *  `blockedURI` is a full URL for a remote sub-resource, and one of a handful
 *  of bare words — `inline`, `eval`, `data` — for a refusal with no host in
 *  it. Only the first kind is worth telling anyone about: a page asking
 *  cdn.tailwindcss.com for itself is exactly why it renders unstyled, whereas
 *  "inline" explains nothing to a person who did not write the page. */
function hostOf(uri: string | undefined): string | null {
  if (!uri || !/^https?:/i.test(uri)) return null;
  try {
    return new URL(uri).host || null;
  } catch {
    return null;
  }
}

/** Three hosts read as a list; six read as noise. Named in full up to
 *  three, because \"and 1 more\" is longer than the host it is hiding. */
function nameThem(hosts: string[]): string {
  if (hosts.length <= 2) return hosts.join(" and ");
  if (hosts.length === 3) return `${hosts[0]}, ${hosts[1]} and ${hosts[2]}`;
  return `${hosts[0]}, ${hosts[1]} and ${hosts.length - 2} more`;
}

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
  //
  // Two channels, because a refusal and a crash are two different facts about
  // the page, and merging them is what made the old single line useless: a
  // blocked webfont is the seal doing its job on a page that is otherwise
  // fine, a thrown exception is the page not working, and whichever arrived
  // first was the one the user read.
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [reachedFor, setReachedFor] = useState<string[]>([]);
  // Hosts the person has allowed, for **this preview only**. Not
  // persisted and not a standing list: a page that wanted three.js once
  // is not a reason to let every future page reach that CDN silently.
  const [allowedHosts, setAllowedHosts] = useState<string[]>([]);

  // Playback and review (asked for 4 October 2026). The page keeps running in a
  // sealed frame, so these are the three things a person does to watch
  // something that moves: stop it to read, start it again from the top, and look
  // at the code that is actually running.
  const [paused, setPaused] = useState(false);
  const [version, setVersion] = useState(0);
  const [view, setView] = useState<'page' | 'code'>('page');
  const [copied, setCopied] = useState(false);

  // Told to the frame rather than done to it: its origin is opaque, so the
  // parent cannot reach in. `PLAYBACK` is the listener on the other side.
  useEffect(() => {
    frameRef.current?.contentWindow?.postMessage(
      { __zaramPreviewControl: true, action: paused ? 'pause' : 'play' },
      '*',
    );
  }, [paused]);

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(block.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // No clipboard in a locked-down webview. The code is on screen and
      // selectable, which is the fallback and not an error worth a banner.
    }
  }

  function restart() {
    // A fresh frame, so the page starts from its first line. Unpaused: a restart
    // that came up frozen would look like it had not worked.
    setPaused(false);
    setVersion((v) => v + 1);
    setView('page');
  }

  useEffect(() => {
    setScriptError(null);
    setReachedFor([]);
    setAllowedHosts([]);
    const onMessage = (event: MessageEvent) => {
      if (!frameRef.current || event.source !== frameRef.current.contentWindow) return;
      const data = event.data as {
        __zaramPreview?: boolean;
        kind?: string;
        detail?: string;
        uri?: string;
      };
      if (!data || data.__zaramPreview !== true) return;
      if (data.kind === 'blocked') {
        const host = hostOf(data.uri);
        if (!host) return;
        // Deduplicated: a page pulling eight webfonts from one host is one
        // fact about that page, not eight.
        setReachedFor((current) => (current.includes(host) ? current : [...current, host]));
        return;
      }
      // First error only. A page that throws on every animation frame would
      // otherwise rewrite this line hundreds of times a second, and the first
      // one is the one that explains the rest.
      setScriptError((current) => current ?? (data.detail || 'the page stopped'));
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [block.code]);

  /** Hosts refused that the person has not yet decided about. */
  const waiting = reachedFor.filter((host) => !allowedHosts.includes(host));

  /** Let this preview load from one host, and record that it did.
   *
   *  The entry is written **before** the reload, for the reason
   *  `stream_pull` writes its own before the first byte: a record
   *  written afterwards is a record of the fetches that succeeded.
   *  Rule 3 is about what leaves, not about what came back. */
  async function allowHost(host: string) {
    try {
      await recordBrowsed(host, `/ (preview: ${block.label})`);
    } catch {
      // A log that will not write must not stop the person seeing
      // their page; the failure is visible in Activity as an absence,
      // which is the honest outcome of a backend that is not there.
    }
    setAllowedHosts((current) =>
      current.includes(host) ? current : [...current, host],
    );
  }

  // Said in the user's terms rather than the browser's. "Blocked:
  // style-src-elem blocked https://fonts.googleapis.com/css2?family=…" is a
  // true sentence that tells a non-technical user nothing and reads as Zaram
  // being broken — when it is Zaram working. The seal holding is the product's
  // whole claim here, so the line leads with that and gives the consequence
  // second.
  const status = [
    scriptError ? `The page's own script stopped: ${scriptError}` : null,
    reachedFor.length
      ? `Nothing left your device — the page asked ${nameThem(reachedFor)} for part of itself, ` +
        'and the preview has no network, so it may look unfinished.'
      : null,
  ]
    .filter(Boolean)
    .join(' ');

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
          <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
            preview
          </span>
          <div className="flex-1" />
          {/* Keeping what you are looking at, from where you are looking at
              it. The same action is under the message, and both belong: the
              panel is where someone decides the page is worth having, and
              closing it to go and find a button is the moment that decision
              gets dropped. `savePreviewable` writes the model's markup, not
              the framed page in the iframe beside it. */}
          <div
            className="flex items-center overflow-hidden rounded-lg"
            style={{ border: '1px solid var(--color-border)' }}
            role="group"
            aria-label="What to show"
          >
            {(['page', 'code'] as const).map((which) => (
              <button
                key={which}
                type="button"
                data-testid={`view-${which}`}
                aria-pressed={view === which}
                onClick={() => setView(which)}
                className="flex items-center gap-1.5 px-2 py-1 text-xs"
                style={{
                  background: view === which ? 'rgba(255,255,255,0.10)' : 'transparent',
                  color: view === which ? 'var(--color-text)' : 'var(--color-text-muted)',
                }}
              >
                {which === 'page' ? <Eye size={12} /> : <Code2 size={12} />}
                {which === 'page' ? 'Page' : 'Code'}
              </button>
            ))}
          </div>
          {view === 'page' && (
            <>
              <button
                type="button"
                data-testid="playback-toggle"
                onClick={() => setPaused((was) => !was)}
                aria-label={paused ? 'Resume the page' : 'Pause the page'}
                aria-pressed={paused}
                title={paused ? 'Resume' : 'Pause — animations and timers hold where they are'}
                className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200"
                style={{ border: '1px solid var(--color-border)' }}
              >
                {paused ? <Play size={12} /> : <Pause size={12} />}
                {paused ? 'Resume' : 'Pause'}
              </button>
              <button
                type="button"
                data-testid="playback-restart"
                onClick={restart}
                aria-label="Restart the page from the beginning"
                title="Restart from the beginning"
                className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200"
                style={{ border: '1px solid var(--color-border)' }}
              >
                <RotateCcw size={12} />
                Restart
              </button>
            </>
          )}
          <button
            onClick={() => savePreviewable(block)}
            aria-label={`Save as ${filenameFor(block)}`}
            title={`Save as ${filenameFor(block)}`}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200"
            style={{ border: '1px solid var(--color-border)' }}
          >
            <Download size={12} />
            Save
          </button>
          <button
            onClick={onClose}
            aria-label="Close preview"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-slate-200"
          >
            <X size={15} />
          </button>
        </div>

        {/* The code is the review. A person watching model-written code run is
            entitled to read it, and the sealed frame is the reason they would
            otherwise have to take the page on trust. It is the model's markup,
            exactly as `Save` writes it — not the DOM the frame ended up with. */}
        {view === 'code' && (
          <div className="relative flex-1 overflow-auto" data-testid="preview-code">
            <button
              type="button"
              data-testid="copy-code"
              onClick={() => void copyCode()}
              aria-label="Copy the code"
              className="absolute right-3 top-3 flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200"
              style={{ border: '1px solid var(--color-border)', background: 'rgba(0,0,0,0.4)' }}
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <pre
              className="m-0 whitespace-pre-wrap break-words px-4 py-3 text-xs leading-relaxed"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}
            >
              {block.code}
            </pre>
          </div>
        )}

        <div className="flex-1 overflow-hidden" hidden={view !== 'page'}>
          <iframe
            ref={frameRef}
            title={`${block.label} preview`}
            // Keyed on the allowance so the frame is rebuilt rather than
            // merely re-attributed: a CSP in a `<meta>` is read when the
            // document parses, and swapping `srcDoc` without a new element
            // leaves the old policy in force.
            key={`${allowedHosts.join(',')}:${version}`}
            srcDoc={wrapForPreview(block.code, 'app', allowedHosts)}
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
          className="flex items-start gap-2 px-4 py-2"
          style={{
            borderTop: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-faint)',
          }}
        >
          <Info size={12} className="mt-[3px] shrink-0" />
          <div className="min-w-0 flex-1">
            <span className="text-xs leading-snug">
              {status || "Runs here only — no network, and no access to your files or Zaram's data."}
            </span>
            {/* **The refusal becomes an offer — 4 October 2026.**

                A page that loads three from the jsdelivr CDN
                renders as a black rectangle, and the line above
                explained why without doing anything about it. The
                maintainer asked for Three.js previews, and the shape the
                product already has for this is rule 5: default deny, then
                an explicit per-item decision.

                Per host and per preview. Allowing jsdelivr for this page
                is not a standing permission for every future one — a list
                nobody audits is how this would quietly become the open
                policy it replaced. */}
            {waiting.length > 0 && (
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                {waiting.map((host) => (
                  <button
                    key={host}
                    type="button"
                    data-testid={`allow-host-${host}`}
                    onClick={() => void allowHost(host)}
                    className="rounded-md px-2 py-1 text-[11px]"
                    style={{
                      border: '1px solid var(--color-cyan)',
                      color: 'var(--color-cyan-light)',
                    }}
                  >
                    Load from {host}
                  </button>
                ))}
                <span className="text-[11px]">
                  This asks {waiting.length === 1 ? 'that host' : 'those hosts'} for part of
                  the page, and is recorded in Activity.
                </span>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
