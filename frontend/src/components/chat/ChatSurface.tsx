/**
 * ChatSurface — glass conversation panel.
 *
 * Temporary. This is a harness proving the transport works, not a designed
 * surface; it will be replaced when the UI spec lands. Everything meaningful
 * lives in `stores/chatStore` and `services/chatClient`, both of which survive
 * that replacement.
 *
 * Sources are rendered as a plain list under each assistant reply. Deliberately
 * unstyled — the point is that provenance arrives and can be shown, not how it
 * looks.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, type Variants } from 'framer-motion';
import { Send } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';
import { useSourceStore } from '@/stores/sourceStore';
import { useOrbStore } from '@/stores';
import { useSystemStore } from '@/stores/systemStore';
import {
  useLayoutStore,
  CHAT_MIN,
  CHAT_MAX,
  clamp,
} from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import ResizeHandle from '@/components/common/ResizeHandle';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useViewport } from '@/hooks/useViewport';
import type { ChatSource } from '@/services/chatClient';

/** Strip internal citation markers ([M1], [S2]) from displayed text.
 *  They ground the model's answer but mean nothing to the user. Applied to
 *  accumulated text rather than individual tokens, because a marker is often
 *  split across several tokens as it streams. */
const stripMarkers = (t: string) => t.replace(/\s*\[[MS]\d+\]/g, '');

/** Provenance for one reply. Each citation opens its source. */
function SourceList({
  sources,
  deleted,
  onOpen,
}: {
  sources: ChatSource[];
  deleted: Set<string>;
  onOpen: (url: string, el: HTMLElement) => void;
}) {
  if (sources.length === 0) return null;
  return (
    <div className="mt-2 pl-3 border-l border-white/10">
      <p
        className="text-[10px] uppercase text-slate-500 mb-1"
        style={{ letterSpacing: '0.06em', fontFamily: 'var(--font-display)' }}
      >
        {sources.length} source{sources.length === 1 ? '' : 's'}
      </p>
      <ul className="flex flex-col gap-1">
        {sources.map((s, i) => {
          const gone = s.url != null && deleted.has(s.url);
          return (
            <li key={s.url ?? i}>
              <button
                type="button"
                disabled={gone || !s.url}
                onClick={(e) => s.url && onOpen(s.url, e.currentTarget)}
                className="text-left text-[11px] leading-snug transition-colors disabled:cursor-default rounded px-1 -mx-1 py-0.5 enabled:hover:bg-white/5 enabled:hover:text-slate-200"
                style={{
                  color: gone ? 'var(--color-text-faint)' : 'var(--color-text-muted)',
                  textDecoration: gone ? 'line-through' : 'none',
                }}
                title={gone ? 'Forgotten' : 'Open this source'}
              >
                <span className="text-slate-500">[{s.kind}]</span>{' '}
                {s.title ?? s.url}
                {gone && <span className="ml-1 text-slate-600">— forgotten</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function ChatSurface() {
  const reduced = useIsReducedMotion();

  const messages = useChatStore((s) => s.messages);
  const streamingText = useChatStore((s) => s.streamingText);
  const streamingSources = useChatStore((s) => s.streamingSources);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const connectionError = useChatStore((s) => s.connectionError);
  const send = useChatStore((s) => s.send);

  const { setOrbState } = useOrbStore((s) => ({ setOrbState: s.setOrbState }));
  const setActivity = useSystemStore((s) => s.setActivity);

  // On a working surface the conversation is an assistant beside your work and
  // takes less width than on the landing, where it is the main event. Each
  // context keeps its own remembered size.
  const context = useChatModeStore((s) => s.context);
  const landingFraction = useLayoutStore((s) => s.chatFraction);
  const workspaceFraction = useLayoutStore((s) => s.chatFractionWorkspace);
  const chatFraction = context === 'workspace' ? workspaceFraction : landingFraction;
  const setFraction = useLayoutStore((s) => s.setChatFraction);
  const setChatFraction = useCallback(
    (f: number) => setFraction(f, context),
    [setFraction, context],
  );
  const setResizing = useLayoutStore((s) => s.setResizing);
  const resetChatFor = useLayoutStore((s) => s.resetChat);
  const resetChat = useCallback(() => resetChatFor(context), [resetChatFor, context]);
  const isResizing = useLayoutStore((s) => s.isResizing);
  const { width: viewportWidth } = useViewport();

  const panelWidth = viewportWidth * chatFraction;

  // The panel is anchored right, so the distance from the pointer to the right
  // edge of the window is the width the user is asking for.
  const handleResize = useCallback(
    (clientX: number) => {
      setChatFraction((viewportWidth - clientX) / viewportWidth);
    },
    [setChatFraction, viewportWidth],
  );

  const handleNudge = useCallback(
    (deltaPx: number) => {
      setChatFraction(
        clamp(chatFraction + deltaPx / viewportWidth, CHAT_MIN, CHAT_MAX),
      );
    },
    [chatFraction, setChatFraction, viewportWidth],
  );

  const [inputText, setInputText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Panels live in the orb region and the orb has to react to them, so this is
  // app-level state rather than local. Forgotten sources stay listed but struck
  // through, so a deletion is visibly confirmed rather than silently vanishing.
  const openSourcePanel = useSourceStore((s) => s.openSource);
  const deletedUrls = useSourceStore((s) => s.forgotten);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages, streamingText]);

  // The Orb reports system state; it does not perform. Thinking while the
  // request is in flight, idle otherwise.
  useEffect(() => {
    // Both orbs read the same activity, so the small one in the top bar and the
    // large one on the landing can never disagree about what is happening.
    setOrbState(isStreaming ? 'thinking' : 'idle');
    setActivity(isStreaming ? 'thinking' : 'idle');
  }, [isStreaming, setOrbState, setActivity]);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || isStreaming) return;
    setInputText('');
    void send(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const container: Variants = {
    hidden: reduced ? { opacity: 0 } : { x: '100%', opacity: 0 },
    visible: {
      x: 0,
      opacity: 1,
      transition: reduced
        ? { duration: 0.2 }
        : { type: 'spring', stiffness: 200, damping: 26, staggerChildren: 0.05 },
    },
    exit: reduced
      ? { opacity: 0, transition: { duration: 0.18 } }
      : { x: '100%', opacity: 0, transition: { duration: 0.28 } },
  };

  const item: Variants = {
    hidden: { opacity: 0, y: reduced ? 0 : 8 },
    visible: { opacity: 1, y: 0 },
  };

  const isEmpty = messages.length === 0 && !streamingText;

  return (
    <motion.div
      key="chat-surface"
      className="fixed top-0 right-0 h-screen flex flex-col glass-border-indigo"
      style={{
        width: panelWidth,
        zIndex: 60,
        backgroundColor: 'var(--color-glass)',
      }}
      variants={container}
      initial="hidden"
      animate="visible"
      exit="exit"
      // Width follows the cursor exactly while dragging; springing it would make
      // the edge lag behind the pointer.
      transition={isResizing ? { duration: 0 } : undefined}
    >
      <ResizeHandle
        panelSide="right"
        label="Resize conversation panel"
        value={Math.round(chatFraction * 100)}
        min={Math.round(CHAT_MIN * 100)}
        max={Math.round(CHAT_MAX * 100)}
        onResize={handleResize}
        onNudge={handleNudge}
        onReset={resetChat}
        onResizingChange={setResizing}
      />

      {/* Header */}
      <motion.div
        className="flex items-center gap-3 px-6 py-4 border-b border-white/5"
        variants={item}
        style={{ backdropFilter: 'blur(20px) saturate(1.4)' }}
      >
        <motion.div
          className="w-2 h-2 rounded-full"
          style={{
            background: isStreaming ? 'var(--color-cyan)' : 'var(--color-violet)',
          }}
          animate={{ opacity: isStreaming ? [1, 0.4, 1] : 0.6 }}
          transition={{
            duration: isStreaming ? 1.5 : 0,
            repeat: isStreaming ? Infinity : 0,
            ease: 'easeInOut',
          }}
        />
        <h2 className="text-sm font-medium text-slate-200">Conversation</h2>
      </motion.div>

      {/* Connection failure sits above the transcript: it is about the backend,
          not about any one reply. */}
      {connectionError && (
        <div
          role="alert"
          className="px-6 py-3 text-xs leading-relaxed border-b border-white/5"
          style={{ background: 'rgba(248,113,113,0.08)', color: '#fca5a5' }}
        >
          {connectionError}
        </div>
      )}

      {/* Transcript */}
      <motion.div ref={scrollRef} className="flex-1 overflow-y-auto" variants={item}>
        <div className="flex flex-col gap-4 p-6">
          {isEmpty ? (
            <p
              className="text-xs uppercase text-slate-500"
              style={{ letterSpacing: '0.05em' }}
            >
              Ask Zaram something
            </p>
          ) : (
            <>
              {messages.map((msg) => (
                <div key={msg.id}>
                  {/* Speaker is named, not just coloured. Colour alone fails
                      colourblind users and is invisible to a screen reader,
                      which would otherwise read one unbroken wall of text. */}
                  <p
                    className="text-[10px] uppercase tracking-wider mb-1"
                    style={{
                      color:
                        msg.role === 'user'
                          ? 'var(--color-text-muted)'
                          : 'var(--color-cyan)',
                      fontFamily: 'var(--font-display)',
                    }}
                  >
                    {msg.role === 'user' ? 'You' : 'Zaram'}
                  </p>
                  <p
                    className="text-sm leading-relaxed whitespace-pre-wrap"
                    style={{
                      color:
                        msg.role === 'user'
                          ? 'var(--color-text)'
                          : 'var(--color-cyan)',
                      // A second, non-colour cue: the assistant's replies are
                      // indented behind a rule.
                      borderLeft:
                        msg.role === 'assistant'
                          ? '2px solid var(--color-cyan-light)'
                          : undefined,
                      paddingLeft: msg.role === 'assistant' ? 10 : undefined,
                    }}
                  >
                    {stripMarkers(msg.text)}
                  </p>
                  {msg.role === 'assistant' && (
                    <SourceList
                      sources={msg.sources}
                      deleted={deletedUrls}
                      onOpen={openSourcePanel}
                    />
                  )}
                  {msg.error && (
                    <p className="mt-1 text-[11px]" style={{ color: '#fca5a5' }}>
                      {msg.text ? `Interrupted: ${msg.error}` : msg.error}
                    </p>
                  )}
                </div>
              ))}

              {/* In-flight reply. Sources arrive before the tokens, so they are
                  shown as soon as they land. */}
              {isStreaming && (
                <div>
                  {streamingText && (
                    <>
                      <p
                        className="text-[10px] uppercase tracking-wider mb-1"
                        style={{
                          color: 'var(--color-cyan)',
                          fontFamily: 'var(--font-display)',
                        }}
                      >
                        Zaram
                      </p>
                      <p
                        className="text-sm leading-relaxed whitespace-pre-wrap"
                        style={{
                          color: 'var(--color-cyan)',
                          borderLeft: '2px solid var(--color-cyan-light)',
                          paddingLeft: 10,
                        }}
                      >
                        {stripMarkers(streamingText)}
                      </p>
                    </>
                  )}
                  <SourceList
                    sources={streamingSources}
                    deleted={deletedUrls}
                    onOpen={openSourcePanel}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </motion.div>

      {/* Input */}
      <motion.div
        className="p-4 border-t border-white/5"
        variants={item}
        style={{ backdropFilter: 'blur(20px) saturate(1.4)' }}
      >
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Zaram anything…"
            aria-label="Message Zaram"
            disabled={isStreaming}
            className="w-full px-4 py-3 text-sm bg-[var(--color-glass)] border border-white/5 rounded-xl text-slate-200 placeholder-slate-500 outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
          />
          <motion.button
            onClick={handleSend}
            disabled={isStreaming || !inputText.trim()}
            aria-label="Send message"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Send size={16} className="text-slate-300" />
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  );
}
