/**
 * The app Zaram started, and what it saw when it looked.
 *
 * Two shapes on one card, because they are one story: `start_app` produced a
 * URL, `look_at_app` produced a picture of it. Both are never folded — a
 * running process on the person's machine and a screenshot of their page are
 * the two outputs of an agentic reply that must not sit behind a chevron.
 *
 * **Stop is the person's.** A dev server Zaram started is a process on the
 * machine, and the button ends it through `POST /projects/{id}/app/stop` —
 * the same shape as Revert on a change: mutative, by a person, reachable from
 * no tool. The screenshot is served from Zaram's own data directory by name;
 * nothing in the URL is the model's.
 */
import { onOpen } from '@/lib/openInBrowser';
import { useBrowserStore } from '@/stores/browserStore';
import { useEffect, useState } from 'react';
import { ExternalLink, Square } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';
import { useChatStore } from '../../stores/chatStore';
import { useProjectStore } from '../../stores/projectStore';

const API = import.meta.env.VITE_ZARAM_API ?? '';

/** The tools that report a page Zaram is *driving* rather than a server it
 *  started. Both carry a URL and the card has to tell them apart; the tool
 *  name is the fact, and the URL is not — they are the same URL. */
const DRIVING_TOOLS = new Set([
  'open_in_browser',
  'read_app_page',
  'click_in_app',
  'type_in_app',
  'read_app_console',
]);

export default function AppCard({ call }: { call: ChatToolCall }) {
  const projectId = useChatStore((s) => s.projectId);
  const stopApp = useProjectStore((s) => s.stopApp);
  const [phase, setPhase] = useState<'idle' | 'working' | 'stopped' | 'failed'>('idle');

  const image = call.image ? call.image.replace(/\\/g, '/').split('/').pop() : '';
  const src = projectId && image ? `${API}/projects/${encodeURIComponent(projectId)}/screens/${encodeURIComponent(image)}` : '';
  // **Fetched, never `<img src>` straight to the API.** Every request to the
  // backend must carry the API credential, and it is installed on `fetch` —
  // an image element cannot send a header, so the direct form answered 401
  // and the card showed its own alt text. Seen on screen, 13 September, the
  // first time a real screenshot reached the card. Read with the credential,
  // shown as an object URL, released when the card goes.
  const [blob, setBlob] = useState<string>('');
  const [failed, setFailed] = useState<string>('');
  useEffect(() => {
    if (!src) return undefined;
    let url = '';
    const controller = new AbortController();
    fetch(src, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        url = URL.createObjectURL(await response.blob());
        setBlob(url);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setFailed(error.message);
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);

  async function stop() {
    if (!projectId) return;
    setPhase('working');
    const ok = await stopApp(projectId);
    setPhase(ok ? 'stopped' : 'failed');
  }

  return (
    <div
      className="mt-2 rounded-lg surface"
      data-testid="app-card"
    >
      {call.appUrl && (
        <div className="flex items-center gap-2 px-3 py-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {/* **A driven page is not a started server, and the card says
              which.** Both carry a URL, and reading "running at" over a page
              Zaram is clicking through describes the wrong half of what is
              happening — the dev server is incidental by then, and the live
              thing is the browser. Told apart by the tool that reported it,
              never by guessing from the URL: they are the same URL. */}
          <span>
            {phase === 'stopped'
              ? 'stopped'
              : DRIVING_TOOLS.has(call.tool)
                ? 'driving'
                : 'running at'}
          </span>
          {/* **Opens in Zaram's own pane when there is one.**
              Until 3 October 2026 this went straight to the system browser,
              which was the only honest option: a page rendered in-app would
              have had script running beside the Spine and egress the gate
              could not see. Both are now answered — the pane is a separate
              session with its own partition, and `webRequest` reports every
              request it makes. Opening the thing you are building in the
              window you are building it in is the point.

              `onOpen` stays as the fallback. Without a desktop host there
              is no pane, and a dead link on a card reads as a broken
              product -- which is the failure that put `openInBrowser` here
              in the first place. */}
          <a
            href={call.appUrl}
            onClick={(event) => {
              if (window.zaram?.browser) {
                event.preventDefault();
                useBrowserStore.getState().show(call.appUrl);
                return;
              }
              onOpen(call.appUrl!)(event);
            }}
            rel="noreferrer"
            className="flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)', fontFamily: 'var(--font-mono)' }}
            data-testid="app-url"
          >
            {call.appUrl}
            <ExternalLink size={10} aria-hidden />
          </a>
          <span className="flex-1" />
          {phase !== 'stopped' && projectId && (
            <button
              type="button"
              onClick={() => void stop()}
              disabled={phase === 'working'}
              className="flex items-center gap-1 disabled:opacity-50"
              style={{ color: 'var(--color-amber, #d97706)' }}
              data-testid="app-stop"
            >
              <Square size={10} aria-hidden />
              {phase === 'working' ? 'Stopping…' : phase === 'failed' ? 'Could not stop' : 'Stop'}
            </button>
          )}
        </div>
      )}
      {src && (
        <div className="px-3 py-2">
          <p className="mb-1 text-xs" style={{ color: 'var(--color-text-faint)' }}>
            what Zaram saw{call.target ? ` at ${call.target}` : ''}
          </p>
          {blob ? (
            <img
              src={blob}
              alt="Screenshot of the running app"
              style={{ maxWidth: '100%', borderRadius: 6, border: '1px solid var(--color-border-subtle)' }}
              data-testid="app-screenshot"
            />
          ) : (
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }} data-testid="app-screenshot-state">
              {failed ? `The screenshot could not be loaded (${failed}).` : 'Loading the screenshot…'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
