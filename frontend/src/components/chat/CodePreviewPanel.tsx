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
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, Info, Download, Pause, Play, RotateCcw, Code2, Eye, Copy, Check, MousePointerClick, Wrench } from 'lucide-react';
import { changeRequest, describe, explainRequest, fixRequest, readPick, type PickedElement } from '@/lib/askAboutPage';
import { useLayoutStore } from '@/stores/layoutStore';
import { recordBrowsed } from '@/services/egressClient';
import { loadThree, usesThree, vendorPage, type VendoredThree } from '@/lib/previewLibraries';
import { findStuckLoop } from '@/lib/previewableCode';
import { stuckLoopIn } from '@/lib/appFiles';
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
  onAsk,
}: {
  block: PreviewableBlock;
  onClose: () => void;
  /** Send a request about this page back to Zaram, as a revision of the reply
   *  that wrote it. Absent where there is no conversation to send it to, and
   *  then Select and Fix this are not offered. */
  onAsk?: (text: string) => void;
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
  // What the last Save of a multi-file app did, in words, with the folder.
  const [saveNote, setSaveNote] = useState<string | null>(null);
  // **Select**: point at part of the page and ask Zaram to change it. Off by
  // default — see `PICKER` for why the page keeps its own clicks until then.
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<PickedElement | null>(null);
  const [asking, setAsking] = useState('');
  // three.js from Zaram's own copy, read once when a page needs it. `failed`
  // falls back to the page as written, which the fault line then explains.
  const [three, setThree] = useState<VendoredThree | null>(null);
  const [threeFailed, setThreeFailed] = useState(false);
  // An app of several files is read as all of them: its modules are inside
  // `data:` URLs in the joined page, where nothing can read an import.
  const everything = useMemo(
    () => (block.files ? block.files.map((f) => f.code).join('\n') : block.code),
    [block.files, block.code],
  );
  const wantsThree = usesThree(everything);
  useEffect(() => {
    if (!wantsThree || three) return;
    let live = true;
    loadThree()
      .then((loaded) => live && setThree(loaded))
      .catch(() => live && setThreeFailed(true));
    return () => {
      live = false;
    };
  }, [wantsThree, three]);
  // Memoised: the library is two megabytes, and this panel re-renders on
  // every token while a reply is still streaming.
  const vendored = useMemo(
    () => (three && wantsThree ? vendorPage(block.code, three, block.files ? everything : '') : null),
    [block.code, block.files, everything, three, wantsThree],
  );
  // Nothing is drawn while the library is being read, rather than a first
  // render that fails on `THREE` and reports a fault that is about to fix
  // itself.
  const waitingForThree = wantsThree && !three && !threeFailed;
  // **A page with a loop that cannot end is not run until the person says so.**
  // It would freeze the frame, and a frozen frame can freeze the window around
  // it. Offered *Fix this* first, with the line named. Keyed to the code, so a
  // corrected page runs without being asked again.
  const [ranAnyway, setRanAnyway] = useState<string | null>(null);
  const stuck = useMemo(() => {
    if (!block.files) {
      const one = findStuckLoop(block.code);
      return one ? { line: one.line, text: one.text, file: '' } : null;
    }
    const hit = stuckLoopIn(block.files, findStuckLoop);
    return hit ? { line: hit.line, text: hit.text, file: hit.file } : null;
  }, [block.code, block.files]);
  const held = stuck !== null && ranAnyway !== block.code;
  const frameDoc = useMemo(
    () =>
      waitingForThree || held
        ? ''
        : wrapForPreview(
            vendored ? vendored.body : block.code,
            'app',
            allowedHosts,
            // Any non-empty string turns on `data:` in the page's policy, which
            // an app's modules need as much as a vendored library does.
            (vendored?.prefix ?? '') || (block.modules ? '<!-- the app\'s modules -->' : ''),
          ),
    [waitingForThree, held, vendored, block.code, block.modules, allowedHosts],
  );

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
      await navigator.clipboard.writeText(block.files ? block.files.map((f) => `// ${f.path}\n${f.code}`).join('\n\n') : block.code);
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
      if (data.kind === 'picked') {
        const found = readPick(data.detail);
        if (found) {
          setPicked(found);
          setAsking('');
        }
        return;
      }
      if (data.kind === 'pick-cancel') {
        setPicking(false);
        setPicked(null);
        return;
      }
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
  // Said when it happened, because a page that asked a CDN for three.js and
  // got Zaram's copy instead is a substitution the person should know about.
  const served = vendored
    ? `Runs here only — no network. ${vendored.served} stood in for the CDN; nothing was fetched.`
    : '';

  // Registered on the window because focus is inside a sandboxed iframe most of
  // the time, where a React key handler on the panel would never see the event.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      // One step back at a time: the question, then picking, then the panel.
      if (picked) setPicked(null);
      else if (picking) setPicking(false);
      else onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, picked, picking]);

  // The frame is told whenever picking changes, and again whenever it is
  // rebuilt (Restart, an allowed host), since a new document starts with it off.
  useEffect(() => {
    frameRef.current?.contentWindow?.postMessage({ __zaramPreviewControl: true, action: 'pick', on: picking }, '*');
    if (!picking) setPicked(null);
  }, [picking]);

  function ask(text: string) {
    if (!onAsk) return;
    setPicking(false);
    setPicked(null);
    onAsk(text);
  }

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
              {onAsk && (
                <button
                  type="button"
                  data-testid="pick-toggle"
                  onClick={() => setPicking((was) => !was)}
                  aria-pressed={picking}
                  title={picking ? 'Stop selecting — the page gets its clicks back' : 'Point at part of the page to ask Zaram to change it'}
                  className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs hover:bg-white/5"
                  style={{
                    border: `1px solid ${picking ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                    color: picking ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                    background: picking ? 'rgba(34,211,238,0.10)' : 'transparent',
                  }}
                >
                  <MousePointerClick size={12} />
                  Select
                </button>
              )}
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
            onClick={() => {
              setSaveNote(null);
              savePreviewable(block).then(
                (where) => where && setSaveNote(`Saved ${block.files?.length} files to ${where}`),
                (err: unknown) => setSaveNote(`Not saved: ${err instanceof Error ? err.message : 'the save failed'}`),
              );
            }}
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

        {saveNote && (
          <div
            role="status"
            data-testid="save-note"
            className="px-4 py-1.5 text-xs"
            style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}
          >
            {saveNote}
          </div>
        )}

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
            {(block.files ?? [{ path: '', code: block.code }]).map((file) => (
              <div key={file.path}>
                {file.path && (
                  <div
                    className="px-4 pt-3 text-[11px]"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
                  >
                    {file.path}
                  </div>
                )}
                <pre
                  className="m-0 whitespace-pre-wrap break-words px-4 py-3 text-xs leading-relaxed"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}
                >
                  {file.code}
                </pre>
              </div>
            ))}
          </div>
        )}

        <div className="relative flex-1 overflow-hidden" hidden={view !== 'page'}>
          {picking && !picked && (
            <div
              className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded-md px-2.5 py-1 text-[11px]"
              style={{ background: 'rgba(2,6,23,0.85)', color: 'var(--color-cyan-light)', border: '1px solid var(--color-cyan)' }}
              data-testid="pick-hint"
            >
              Click any part of the page to ask Zaram about it · Esc to stop
            </div>
          )}
          {picked && onAsk && (
            <AskPopover
              picked={picked}
              value={asking}
              onChange={setAsking}
              onChangeIt={() => asking.trim() && ask(changeRequest(picked, asking))}
              onQuick={(words) => ask(changeRequest(picked, words))}
              onExplain={() => ask(explainRequest(picked))}
              onCancel={() => setPicked(null)}
            />
          )}
          {held && stuck && (
            <div
              className="flex h-full flex-col items-start justify-center gap-3 px-8"
              style={{ color: 'var(--color-text)' }}
              data-testid="stuck-loop"
            >
              <p className="text-sm">This page has a loop that never ends, so it was not started.</p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {stuck.file ? `${stuck.file}, line` : 'Line'} {stuck.line}: <code style={{ fontFamily: 'var(--font-mono)' }}>{stuck.text}</code>
                {' '}— the counter is never increased, so the page would freeze before drawing anything.
              </p>
              <div className="flex gap-2">
                {onAsk && (
                  <button
                    type="button"
                    data-testid="stuck-fix"
                    onClick={() => onAsk(fixRequest(`${stuck.file ? `${stuck.file}, ` : ''}line ${stuck.line}: \`${stuck.text}\` never changes its counter, so the page freezes before it draws anything. Check every loop in the page for the same mistake.`))}
                    className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs"
                    style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
                  >
                    <Wrench size={11} />
                    Fix this
                  </button>
                )}
                <button
                  type="button"
                  data-testid="stuck-run"
                  onClick={() => setRanAnyway(block.code)}
                  className="rounded-md px-2.5 py-1 text-xs"
                  style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
                >
                  Run anyway
                </button>
              </div>
            </div>
          )}
          <iframe
            hidden={held}
            ref={frameRef}
            onLoad={() =>
              picking &&
              frameRef.current?.contentWindow?.postMessage({ __zaramPreviewControl: true, action: 'pick', on: true }, '*')
            }
            title={`${block.label} preview`}
            // Keyed on the allowance so the frame is rebuilt rather than
            // merely re-attributed: a CSP in a `<meta>` is read when the
            // document parses, and swapping `srcDoc` without a new element
            // leaves the old policy in force.
            key={`${allowedHosts.join(',')}:${version}:${vendored ? 'lib' : 'raw'}`}
            srcDoc={frameDoc}
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
              {status || served || "Runs here only — no network, and no access to your files or Zaram's data."}
            </span>
            {scriptError && onAsk && (
              <div className="mt-1.5">
                <button
                  type="button"
                  data-testid="fix-this"
                  onClick={() => ask(fixRequest(scriptError, waiting))}
                  className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px]"
                  style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
                >
                  <Wrench size={11} />
                  Fix this
                </button>
              </div>
            )}
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

/**
 * The question, next to the part of the page it is about.
 *
 * Placed under the element when there is room and above it when there is
 * not, inside the frame's box. The element's own words are shown as text —
 * they came from the page.
 */
function AskPopover({
  picked,
  value,
  onChange,
  onChangeIt,
  onQuick,
  onExplain,
  onCancel,
}: {
  picked: PickedElement;
  value: string;
  onChange: (text: string) => void;
  onChangeIt: () => void;
  onQuick: (words: string) => void;
  onExplain: () => void;
  onCancel: () => void;
}) {
  const WIDTH = 320;
  const below = picked.rect.y + picked.rect.h + 8;
  const top = below + 170 > (typeof window !== 'undefined' ? window.innerHeight * 0.6 : 400)
    ? Math.max(8, picked.rect.y - 178)
    : below;
  const left = Math.max(8, Math.min(picked.rect.x, (typeof window !== 'undefined' ? window.innerWidth : 1000) - WIDTH - 40));
  const chip = 'rounded-md px-2 py-0.5 text-[11px] hover:bg-white/10';
  const chipStyle = { border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' };
  return (
    <div
      className="absolute z-20 flex flex-col gap-2 rounded-xl p-3"
      style={{
        top,
        left,
        width: WIDTH,
        background: 'rgba(2,6,23,0.94)',
        border: '1px solid var(--color-cyan)',
        boxShadow: '0 12px 32px rgba(0,0,0,0.45)',
      }}
      data-testid="ask-popover"
      onClick={(event) => event.stopPropagation()}
    >
      <div className="min-w-0">
        <div className="truncate text-[11px]" style={{ color: 'var(--color-cyan-light)', fontFamily: 'var(--font-mono)' }} title={picked.selector}>
          {describe(picked)}
        </div>
        {picked.text && (
          <div className="truncate text-[11px]" style={{ color: 'var(--color-text-faint)' }} title={picked.text}>
            “{picked.text}”
          </div>
        )}
      </div>
      <textarea
        autoFocus
        rows={2}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            onChangeIt();
          }
        }}
        placeholder="What should change? e.g. make it bigger, move it to the top, use a darker blue"
        className="w-full resize-none rounded-lg px-2 py-1.5 text-xs outline-none"
        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        data-testid="ask-input"
      />
      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" className={chip} style={chipStyle} onClick={() => onQuick('Remove it.')}>
          Remove it
        </button>
        <button type="button" className={chip} style={chipStyle} onClick={() => onQuick('Make it stand out more.')}>
          Make it stand out
        </button>
        <button type="button" className={chip} style={chipStyle} onClick={onExplain} data-testid="ask-explain">
          What does this do?
        </button>
      </div>
      <div className="flex items-center justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-md px-2 py-1 text-xs" style={{ color: 'var(--color-text-faint)' }}>
          Cancel
        </button>
        <button
          type="button"
          onClick={onChangeIt}
          disabled={!value.trim()}
          className="rounded-md px-2.5 py-1 text-xs disabled:opacity-40"
          style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
          data-testid="ask-send"
        >
          Ask Zaram
        </button>
      </div>
    </div>
  );
}
