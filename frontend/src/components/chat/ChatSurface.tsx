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
import { motion, AnimatePresence, type Variants } from 'framer-motion';
import { Send } from 'lucide-react';
import ArtifactCard from '@/components/ArtifactCard';
import NoticeCard from '@/components/chat/NoticeCard';
import FirstRunPanel from '@/components/firstrun/FirstRunPanel';
import { useReadiness, setupToOffer } from '@/hooks/useReadiness';
import { useConversationStore } from '@/stores/conversationStore';
import { useChatStore } from '@/stores/chatStore';
import { useSourceStore } from '@/stores/sourceStore';
import { useOrbStore } from '@/stores';
import { useSystemStore } from '@/stores/systemStore';
import ProjectScopePicker from './ProjectScopePicker';
import MicButton from './MicButton';
import CitationSummary from './CitationChips';
import SpeakButton from './SpeakButton';
import CitationPanel from './CitationPanel';
import {
  useLayoutStore,
  CHAT_MIN,
  CHAT_MAX,
  clamp,
} from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useMicStore } from '@/stores/micStore';
import { useSpeechStore } from '@/stores/speechStore';
import ResizeHandle from '@/components/common/ResizeHandle';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useViewport } from '@/hooks/useViewport';
import type { ChatSource } from '@/services/chatClient';

/** Strip internal citation markers ([M1], [S2]) from displayed text.
 *  They ground the model's answer but mean nothing to the user. Applied to
 *  accumulated text rather than individual tokens, because a marker is often
 *  split across several tokens as it streams. */
const stripMarkers = (t: string) => t.replace(/\s*\[[MS]\d+\]/g, '');

export default function ChatSurface() {
  const reduced = useIsReducedMotion();

  const messages = useChatStore((s) => s.messages);
  const streamingText = useChatStore((s) => s.streamingText);
  const streamingSources = useChatStore((s) => s.streamingSources);
  const streamingArtifacts = useChatStore((s) => s.streamingArtifacts);
  const streamingNotices = useChatStore((s) => s.streamingNotices);
  // A notice names where to go about it; the route has to actually work, so
  // it drives the same node selection the orbit uses.
  const openWorkspace = useConversationStore((s) => s.setActiveNode);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const connectionError = useChatStore((s) => s.connectionError);
  const send = useChatStore((s) => s.send);

  const { setOrbState } = useOrbStore((s) => ({ setOrbState: s.setOrbState }));
  const setActivity = useSystemStore((s) => s.setActivity);

  // On a working surface the conversation is an assistant beside your work and
  // takes less width than on the landing, where it is the main event. Each
  // context keeps its own remembered size.
  const context = useChatModeStore((s) => s.context);
  const closeChat = useChatModeStore((s) => s.closeChat);

  // Whether there is anything to answer with. Asked when the conversation
  // opens, because that is the moment it matters and the moment the answer can
  // have changed — someone who installs a model and comes back finds the
  // composer, with nothing to dismiss and no decision remembered anywhere.
  //
  // `setupToOffer` returns null unless the backend said plainly that chat
  // cannot work, so a slow or unreachable probe leaves the composer exactly
  // where it was.
  const readiness = useReadiness();
  const setupNeeded = setupToOffer(readiness);
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

  // Why voice input is off, when it is, and what went wrong with an attempt.
  // Two different things: a missing extra is not a declined permission prompt,
  // and CLAUDE.md's rule is that a disabled capability is visible rather than
  // silent — a mic button that is simply absent explains nothing.
  const micUnavailable = useMicStore((s) => s.unavailableReason);
  const micError = useMicStore((s) => s.error);
  const micStatus = useMicStore((s) => s.status);

  // The dictated transcript contained an amount. Not an error — the text landed
  // fine — so it reads as a caution and is styled apart from the failures
  // below. Measured: *naira* came back as **$**, wrong by ~1500x in the
  // direction that looks reasonable on an invoice, and `$400,000` is a
  // well-formed amount that nothing downstream can question. The person who
  // said it is the last check there is.
  const figureNotice = useMicStore((s) => s.figureNotice);

  // Speech *out* failures were rendered nowhere. `speechStore` sets a careful
  // named reason for each one — "Speech is not installed.", "Playback was
  // blocked.", "The audio could not be played." — and no component read it, so
  // every synthesised utterance 404'd for as long as the feature has existed
  // and the only symptom was silence. Same rule as the mic: a disabled
  // capability is visible, not silent.
  const speechError = useSpeechStore((s) => s.error);

  // Transcribed speech lands in the composer as ordinary editable text and is
  // never sent on the user's behalf. A recogniser that mishears and submits has
  // spoken for them.
  const appendTranscript = useCallback((text: string) => {
    setInputText((current) => (current ? `${current} ${text}` : text));
    inputRef.current?.focus();
  }, []);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Panels live in the orb region and the orb has to react to them, so this is
  // app-level state rather than local. Forgotten sources stay listed but struck
  // through, so a deletion is visibly confirmed rather than silently vanishing.
  const openSourcePanel = useSourceStore((s) => s.openSource);
  const deletedUrls = useSourceStore((s) => s.forgotten);

  // The per-reply citation panel. Local rather than app-level: unlike a fact
  // panel it belongs to one reply in this transcript and has nothing to say
  // once you leave it, so there is no reason for the orb region to own it.
  const [panelFor, setPanel] = useState<{
    sources: ChatSource[];
    anchor: HTMLElement | null;
  } | null>(null);

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

      {/* Nothing to answer with. The offers stand where the composer stands —
          a box that accepts text and produces nothing is how a new user decides
          the product is broken, and it is the one impression there is no second
          chance at. Never render both: an input under an explanation of why
          there is no input is still an input, and it will be typed into. */}
      {setupNeeded ? (
        <FirstRunPanel report={setupNeeded} onExplore={closeChat} />
      ) : (
        <>
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
                    <CitationSummary
                      sources={msg.sources}
                      deleted={deletedUrls}
                      onOpenPanel={(el) => setPanel({ sources: msg.sources, anchor: el })}
                      onOpenSource={(s, el) => s.url && openSourcePanel(s.url, el)}
                    />
                  )}
                  {/* The "unless asked" half of "orb, silent unless asked".
                      Without it the landing default is silent with no way to
                      hear a reply and nothing saying why — which reads as a
                      broken voice extra rather than as a deliberate default. */}
                  {msg.role === 'assistant' && <SpeakButton text={stripMarkers(msg.text)} />}
                  {/* Files made by this reply. CLAUDE.md: generated files
                      appear as cards in the conversation. */}
                  {msg.artifacts?.map((artifact) => (
                    <ArtifactCard key={artifact.id} artifact={artifact} />
                  ))}
                  {msg.notices?.map((notice, i) => (
                    <NoticeCard key={i} notice={notice} onOpen={openWorkspace} />
                  ))}
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
                  {/* Chips only while streaming. The summary's empty state is a
                      claim about absence, and a reply that has not finished
                      arriving cannot yet make it — saying "nothing from your
                      files" mid-stream would be wrong a moment later. */}
                  {streamingSources.length > 0 && (
                    <CitationSummary
                      sources={streamingSources}
                      deleted={deletedUrls}
                      onOpenPanel={(el) =>
                        setPanel({ sources: streamingSources, anchor: el })
                      }
                      onOpenSource={(s, el) => s.url && openSourcePanel(s.url, el)}
                    />
                  )}
                  {streamingArtifacts.map((artifact) => (
                    <ArtifactCard key={artifact.id} artifact={artifact} />
                  ))}
                  {streamingNotices.map((notice, i) => (
                    <NoticeCard key={i} notice={notice} onOpen={openWorkspace} />
                  ))}
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
            placeholder={
              micStatus === 'recording'
                ? 'Listening on this machine…'
                : 'Ask Zaram anything…'
            }
            aria-label="Message Zaram"
            disabled={isStreaming}
            className="w-full pl-4 pr-16 py-3 text-sm bg-[var(--color-glass)] border border-white/5 rounded-xl text-slate-200 placeholder-slate-500 outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
          />
          <MicButton onTranscript={appendTranscript} disabled={isStreaming} />
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
        {/* Voice input's state, in words. A disabled button with a tooltip is
            invisible to a keyboard or touch user, and "why is this greyed out"
            is exactly the question a silent control leaves unanswered. */}
        {(micError || micUnavailable || speechError) && (
          <p
            className="mt-2 px-1 text-[11px] leading-relaxed"
            style={{
              color: micError || speechError ? '#fca5a5' : 'var(--color-text-muted)',
            }}
          >
            {micError ?? speechError ?? micUnavailable}
          </p>
        )}
        {/* Amber, not red, and on its own line: nothing failed. The transcript
            arrived; one part of it is not trustworthy. Rendered separately from
            the errors above so a caution never hides a failure or vice versa. */}
        {figureNotice && (
          <p
            className="mt-2 px-1 text-[11px] leading-relaxed"
            style={{ color: '#fcd34d' }}
          >
            {figureNotice}
          </p>
        )}
        {/* Under the input rather than over it: the scope is context for what
            you are about to write, and it must not compete with the thing you
            came here to do. */}
        <div className="mt-2 px-1">
          <ProjectScopePicker />
        </div>
      </motion.div>
        </>
      )}

      {/* The citation panel, anchored beside the conversation. */}
      <AnimatePresence>
        {panelFor && (
          <div className="absolute right-full top-1/4 mr-3 z-[75] pointer-events-none">
            <CitationPanel
              sources={panelFor.sources}
              deleted={deletedUrls}
              returnFocusTo={panelFor.anchor}
              onClose={() => setPanel(null)}
              onCorrect={(s) => {
                // Correction reuses the existing fact panel rather than a
                // second implementation of the same thing — one pattern, not
                // two, and rule 4's loop already closes there.
                if (s.url) openSourcePanel(s.url, panelFor.anchor as HTMLElement);
                setPanel(null);
              }}
              onOpenActivity={() => {
                openWorkspace('activity');
                setPanel(null);
              }}
            />
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
