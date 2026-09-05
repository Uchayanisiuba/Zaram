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

export default function AmbientPanel() {
  const [text, setText] = useState('');
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
  const refresh = useSystemStore((s) => s.refresh);
  const cloudAnsweredAt = useSystemStore((s) => s.cloudAnsweredAt);

  // Asked once when the panel is created, which happens at boot. The window is
  // kept warm and hidden, so this is not on the summon path — polling here
  // would be a timer running all day to keep one line of text fresh.
  useEffect(() => {
    void refresh();
  }, [refresh]);

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
