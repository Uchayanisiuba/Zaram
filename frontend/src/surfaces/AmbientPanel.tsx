/**
 * The ambient panel — Zaram over whatever is already on screen.
 *
 * Summoned by a global accelerator or by the screen-edge handle, never by
 * anything the user did not do on purpose. `electron/native/ambient.js` owns
 * the window; this owns what is in it.
 *
 * **It is deliberately not the shell.** A composer, a reply, and one line
 * saying where the answer comes from. Six workspaces and a VRM renderer make a
 * good application and a bad overlay, and the position the architecture gives
 * away free is *fastest*, not *fullest* — a resident local model answers with
 * no network round trip, and that advantage is squandered by a heavy bundle in
 * front of it.
 *
 * **The egress line is on the surface itself**, which `CLAUDE.md` requires:
 * being ambient makes the disclosure more important, not less, because the
 * user is looking at somebody else's document rather than at Zaram. It reuses
 * `describeSystem` — the same function the orb's label calls — so the overlay
 * and the orb cannot disagree about whether data can leave. Rewriting the
 * wording here would be a second answer to the one question this product must
 * never give two answers to.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { streamChat, ChatTransportError } from '@/services/chatClient';
import { useSystemStore, describeSystem } from '@/stores/systemStore';
import { fetchServers, callTool, type ToolServer } from '@/services/toolsClient';
import { Monitor, MousePointerClick, Keyboard, List, Maximize, Move, RotateCcw, ChevronDown, ChevronUp, X } from 'lucide-react';

export default function AmbientPanel() {
  const [text, setText] = useState('');
  // The selection read when the summon key was pressed arrives after the
  // panel is up. It goes into the composer as the thing to ask about, with
  // the cursor after it, and is never kept: working state, not memory.
  useEffect(() => {
    const api = (window as unknown as { zaram?: { ambient?: { onSelection?: (l: (t: string) => void) => () => void } } }).zaram;
    const off = api?.ambient?.onSelection?.((selected: string) => {
      if (typeof selected !== 'string' || !selected.trim()) return;
      setText((current) => (current.trim() ? `${current}\n\n${selected}` : `${selected}\n\n`));
    });
    return () => {
      if (typeof off === 'function') off();
    };
  }, []);
  const [reply, setReply] = useState('');
  // A boolean, not a phase. This was three states — ready, asking, answered —
  // and only `asking` was ever read: the other two rendered identically,
  // because "answered" is just "not asking, with text". A state nobody
  // branches on is a state that will eventually be branched on wrongly.
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const cloudAnsweredAt = useSystemStore((s) => s.cloudAnsweredAt);

  // Computer Use quick actions state
  const [cuaServers, setCuaServers] = useState<ToolServer[]>([]);
  const [cuaActionResult, setCuaActionResult] = useState<{ tool: string; result?: any; error?: string } | null>(null);
  const [cuaActionBusy, setCuaActionBusy] = useState(false);
  const [showCuaActions, setShowCuaActions] = useState(false);

  // Load cua-driver servers on mount
  useEffect(() => {
    if (backendOnline) {
      void loadCuaServers();
    }
  }, [backendOnline]);

  const loadCuaServers = useCallback(async () => {
    try {
      const servers = await fetchServers();
      const cua = servers.filter((s) => s.id.toLowerCase().includes('cua-driver') || s.id.toLowerCase().includes('cua'));
      setCuaServers(cua);
    } catch {
      // Silently fail - computer use is optional
    }
  }, []);

  const runCuaAction = useCallback(async (serverId: string, tool: string, args: Record<string, any>) => {
    if (cuaActionBusy) return;
    setCuaActionBusy(true);
    setCuaActionResult(null);
    try {
      const result = await callTool(serverId, tool, args);
      setCuaActionResult({ tool, result: result.result, error: result.error });
    } catch (err) {
      setCuaActionResult({ tool, error: (err as Error).message });
    } finally {
      setCuaActionBusy(false);
    }
  }, [cuaActionBusy]);

  const runQuickAction = useCallback(async (serverId: string, action: 'screenshot' | 'list_windows' | 'list_apps' | 'get_desktop_state') => {
    const config: Record<string, { tool: string; args: Record<string, any> }> = {
      screenshot: { tool: 'get_desktop_state', args: {} },
      list_windows: { tool: 'list_windows', args: {} },
      list_apps: { tool: 'list_apps', args: {} },
      get_desktop_state: { tool: 'get_desktop_state', args: {} },
    };
    const { tool, args } = config[action];
    await runCuaAction(serverId, tool, args);
  }, [runCuaAction]);

  // The window is shown rather than created, so focus has to be taken
  // explicitly each time. Without this the panel appears and the first
  // keystroke goes nowhere, which reads as the hotkey having missed.
  useEffect(() => {
    const focus = () => inputRef.current?.focus();
    focus();
    window.addEventListener('focus', focus);
    return () => window.removeEventListener('focus', focus);
  }, []);

  // Hide, never close. The window is warm — created hidden at boot so that a
  // summon is a `show()` — and closing it would throw that away and pay
  // renderer startup on the next hotkey.
  const dismiss = useCallback(() => {
    abortRef.current?.abort();
    void window.zaram?.ambient?.dismiss();
  }, []);

  const ask = useCallback(async () => {
    const question = text.trim();
    if (!question || asking) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAsking(true);
    setReply('');
    setError(null);

    try {
      for await (const event of streamChat({ text: question }, controller.signal)) {
        if (event.type === 'token') setReply((r) => r + event.content);
        else if (event.type === 'error') setError(event.message);
      }
    } catch (err) {
      // A deliberate dismissal aborts the stream, and an abort is not a
      // failure — showing "the request failed" for something the user chose
      // would be the interface blaming them for pressing Escape.
      if (controller.signal.aborted) return;
      setError(
        err instanceof ChatTransportError
          ? err.message
          : 'Zaram could not reach the backend.',
      );
    } finally {
      // `finally`, not a line at the end of each branch. An abort returns
      // early from the catch, and the two paths that reached `setPhase` before
      // left the caret spinning forever on the third.
      if (!controller.signal.aborted) setAsking(false);
    }
  }, [text, asking]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      dismiss();
      return;
    }
    // Enter sends; Shift+Enter is a newline. The overlay is for one question,
    // so the common case gets the unmodified key.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void ask();
    }
  };

  const status = describeSystem({
    backendOnline,
    routing,
    activity: asking ? 'thinking' : 'idle',
    // The ambient surface is the one place a selection can leave the machine
    // without the main window open, so its egress statement must be the same
    // one the orb makes rather than a quieter version of it.
    cloudAnsweredAt,
  });

  return (
    <div className="ambient" data-testid="ambient-panel" onKeyDown={onKeyDown}>
      <div className="ambient__composer">
        <textarea
          ref={inputRef}
          className="ambient__input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Zaram"
          rows={1}
          aria-label="Ask Zaram"
          spellCheck={false}
        />
      </div>

      {(reply || asking || error) && (
        <div className="ambient__reply" role="status" aria-live="polite">
          {error ? (
            <p className="ambient__error">{error}</p>
          ) : (
            <p className="ambient__text">
              {reply}
              {asking && <span className="ambient__caret" aria-hidden="true" />}
            </p>
          )}
        </div>
      )}

      {/* Computer Use Quick Actions */}
      {cuaServers.length > 0 && (
        <div className="ambient__cua-actions" style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--color-border-subtle)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Computer Use ({cuaServers[0].id})
            </span>
            <button
              type="button"
              className="text-xs p-1 rounded"
              style={{ color: 'var(--color-text-muted)', background: 'none', border: 0 }}
              onClick={() => setShowCuaActions(!showCuaActions)}
              aria-expanded={showCuaActions}
            >
              {showCuaActions ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>

          {showCuaActions && (
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runQuickAction(cuaServers[0].id, 'screenshot')}
                  disabled={cuaActionBusy}
                  title="Capture full desktop screenshot"
                >
                  <Monitor size={12} />
                  <span>Screenshot</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runQuickAction(cuaServers[0].id, 'list_windows')}
                  disabled={cuaActionBusy}
                  title="List all open windows"
                >
                  <List size={12} />
                  <span>List Windows</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runQuickAction(cuaServers[0].id, 'list_apps')}
                  disabled={cuaActionBusy}
                  title="List running applications"
                >
                  <RotateCcw size={12} />
                  <span>List Apps</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runQuickAction(cuaServers[0].id, 'get_desktop_state')}
                  disabled={cuaActionBusy}
                  title="Full desktop state with cursor position"
                >
                  <Maximize size={12} />
                  <span>Desktop State</span>
                </button>
              </div>

              {/* Advanced actions - need target */}
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runCuaAction(cuaServers[0].id, 'get_window_state', { pid: 0, include_screenshot: true })}
                  disabled={cuaActionBusy}
                  title="Inspect a window (needs PID)"
                >
                  <Maximize size={12} />
                  <span>Window State</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runCuaAction(cuaServers[0].id, 'click', { pid: 0, x: 100, y: 100 })}
                  disabled={cuaActionBusy}
                  title="Click at coordinates (needs PID, x, y)"
                >
                  <MousePointerClick size={12} />
                  <span>Click</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runCuaAction(cuaServers[0].id, 'type_text', { pid: 0, text: '' })}
                  disabled={cuaActionBusy}
                  title="Type text (needs PID, text)"
                >
                  <Keyboard size={12} />
                  <span>Type Text</span>
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: cuaActionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runCuaAction(cuaServers[0].id, 'scroll', { pid: 0, direction: 'down', pages: 1 })}
                  disabled={cuaActionBusy}
                  title="Scroll window (needs PID)"
                >
                  <Move size={12} />
                  <span>Scroll</span>
                </button>
              </div>

              {/* Action Result */}
              {cuaActionResult && (
                <div
                  className="mt-2 p-2 rounded-lg text-xs font-mono overflow-auto max-h-48"
                  style={{
                    background: cuaActionResult.error ? 'rgba(248,113,113,0.1)' : 'rgba(16,185,129,0.1)',
                    border: cuaActionResult.error
                      ? '1px solid rgba(248,113,113,0.4)'
                      : '1px solid rgba(16,185,129,0.4)',
                    color: cuaActionResult.error ? '#fca5a5' : 'var(--color-emerald)',
                  }}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span>
                      {cuaActionResult.error ? <span style={{ color: '#fca5a5' }}>✕</span> : <span style={{ color: 'var(--color-emerald)' }}>✓</span>}
                      {cuaActionResult.tool}
                    </span>
                    <button
                      type="button"
                      className="text-xs p-1"
                      style={{ color: 'var(--color-text-muted)', background: 'none', border: 0 }}
                      onClick={() => setCuaActionResult(null)}
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {cuaActionResult.error
                      ? cuaActionResult.error
                      : JSON.stringify(cuaActionResult.result, null, 2).slice(0, 2000)}
                  </pre>
                  {cuaActionResult.result &&
                    typeof cuaActionResult.result === 'object' &&
                    'screenshot' in cuaActionResult.result && (
                    <div className="mt-2">
                      <img
                        src={`data:image/png;base64,${cuaActionResult.result.screenshot}`}
                        alt="Screenshot"
                        style={{ maxWidth: '100%', maxHeight: 200, borderRadius: '4px', border: '1px solid var(--color-border-subtle)' }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Rule 5's disclosure, at the moment and place it is needed. The tone
          class is the same three-way split the orb uses, so a user who has
          learned what the orb's colours mean has already learned this. */}
      <div className={`ambient__status ambient__status--${status.tone}`}>
        <span className="ambient__label">{status.label}</span>
        <span className="ambient__detail">{status.detail}</span>
      </div>
    </div>
  );
}
