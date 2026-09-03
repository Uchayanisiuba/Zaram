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
import { Eye, Paperclip, Send, Square } from 'lucide-react';
import ArtifactCard from '@/components/ArtifactCard';
import AttachmentChips from '@/components/chat/AttachmentChips';
import RoutingControl from '@/components/chat/RoutingControl';
import { filesFromClipboard, withPasteName } from '@/lib/pastedFiles';
import {
  attachFiles,
  detachAttachment,
  keepAttachment,
  listAttachments,
  type ChatAttachment,
  type RefusedAttachment,
} from '@/services/attachmentsClient';
import NoticeCard from '@/components/chat/NoticeCard';
import FirstRunPanel from '@/components/firstrun/FirstRunPanel';
import { useReadiness, setupToOffer } from '@/hooks/useReadiness';
import { useTypedText } from '@/hooks/useTypedText';
import { stripCitationMarkers } from '@/lib/markers';
import { useChatStore } from '@/stores/chatStore';
import { useSourceStore } from '@/stores/sourceStore';
import { useOrbStore } from '@/stores';
import { useSystemStore } from '@/stores/systemStore';
import ProjectScopePicker from './ProjectScopePicker';
import DomainScopePicker from './DomainScopePicker';
import MicButton from './MicButton';
import CitationSummary from './CitationChips';
import MessageActions from './MessageActions';
import { AnsweredBy } from './AnsweredBy';
import SpeakButton from './SpeakButton';
import ReasoningPanel from './ReasoningPanel';
import CitationPanel from './CitationPanel';
import CodePreviewPanel from './CodePreviewPanel';
import { extractPreviewable, type PreviewableBlock } from '@/lib/previewableCode';
import {
  useLayoutStore,
  CHAT_MIN,
  CHAT_MAX,
  clamp,
} from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useMicStore } from '@/stores/micStore';
import { useSpeechStore } from '@/stores/speechStore';
import { preserveSpeaking, chatActivity } from '@/lib/orbActivity';
import ResizeHandle from '@/components/common/ResizeHandle';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useViewport } from '@/hooks/useViewport';
import type { ChatSource } from '@/services/chatClient';
import type { WorkspaceId } from '@/runtime/shortcuts/registry';

/** Strip internal citation markers ([M1], [S2]) from displayed text.
 *
 *  Moved to `@/lib/markers` because a third caller needed it and had been
 *  missed: the path that speaks a reply automatically was handing Kokoro the
 *  raw text, markers and all. One copy, so the next caller cannot miss it. */
const stripMarkers = stripCitationMarkers;

interface Props {
  /** Go to a workspace. The shell's own `navigate`, passed in rather than
   *  reimplemented.
   *
   *  **This was wired to a store nothing read.** `openWorkspace` was
   *  `useConversationStore.setActiveNode`, and `activeNode` has no reader
   *  outside `src/legacy/`, which is not mounted. So every notice's
   *  "Open Settings →" set a field and returned, and the panel's "open
   *  Activity" did the same — two dead routes that looked live. Reported by
   *  the maintainer, 28 August 2026.
   *
   *  Required rather than optional, and passed rather than pulled from a
   *  store, for one reason each. Required: a surface that renders notices
   *  offering to take you somewhere must have somewhere to take you, and
   *  TypeScript should say so at the call site rather than the button failing
   *  silently. Passed: `App`'s `navigate` also closes the chat, closes the
   *  command palette and sets the conversation's context — a second
   *  implementation in a store would drift from it, and drifting navigation is
   *  how this broke in the first place.
   *
   *  `npm run check:reachability` cannot catch the original defect: the export
   *  *was* used. It just led nowhere. */
  navigate: (id: WorkspaceId) => void;
}

export default function ChatSurface({ navigate }: Props) {
  const reduced = useIsReducedMotion();

  // Markup from a reply, brought forward over the orb. Held here rather than
  // per-message so only one preview is open at a time — two of these would
  // stack in the same fixed region and the lower one would be unreachable.
  const [codePreview, setCodePreview] = useState<PreviewableBlock | null>(null);

  const messages = useChatStore((s) => s.messages);
  const streamingText = useChatStore((s) => s.streamingText);
  const streamingReasoning = useChatStore((s) => s.streamingReasoning);
  const streamingSources = useChatStore((s) => s.streamingSources);
  const streamingArtifacts = useChatStore((s) => s.streamingArtifacts);
  const streamingNotices = useChatStore((s) => s.streamingNotices);
  const streamingAnsweredBy = useChatStore((s) => s.streamingAnsweredBy);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const connectionError = useChatStore((s) => s.connectionError);
  const send = useChatStore((s) => s.send);
  const cancel = useChatStore((s) => s.cancel);

  /** Turn web search on, permit the search engine, then ask again.
   *
   *  The second half is what makes it an offer rather than a setting with a
   *  shortcut. A person who has just been told the answer may be stale wants
   *  *this question* answered, not the next one — enabling the switch and
   *  leaving the stale reply on screen would be the same dead end one click
   *  further along.
   *
   *  **The host rule is the part that was missing, and its absence made the
   *  first version a refusal with no remedy.** `setWebSearch(true)` turns the
   *  planner on and grants nothing; the search then goes out to a host with no
   *  rule, default-deny refuses it, and the reply says "web search ran but
   *  returned no results". Observed by the maintainer on the first press.
   *  Nothing had gone wrong except that Zaram asked the same question twice
   *  and answered it "no" the second time.
   *
   *  Rule 7j settles it: *"Consent given deliberately for a destination is
   *  consent… Requiring a second, separate host rule afterwards asks the same
   *  question twice and reads as the product being broken."* Pressing a button
   *  that says the question goes to a search engine **is** the decision about
   *  that destination. It is still per-host, still visible in Settings, still
   *  revocable there, and the kill switch still beats it.
   *
   *  Errors are not caught here: `NoticeCard` awaits this and says so on its
   *  own button, which is where the person is looking. */
  const enableSearchAndRetry = useCallback(async () => {
    const { setWebSearch, setEgressPolicyForHost } = await import(
      '@/services/settingsClient'
    );
    const status = await setWebSearch(true);
    // Only when it is not already permitted, and only for the host the
    // backend names. Deriving the hostname here would be a second answer to
    // a question `/search/web` already answers.
    if (status.host && status.hostPolicy !== 'allow') {
      await setEgressPolicyForHost(status.host, 'allow');
    }
    const lastAsked = [...useChatStore.getState().messages]
      .reverse()
      .find((message) => message.role === 'user');
    if (lastAsked) void send(lastAsked.text);
  }, [send]);

  // Typed out at a steady cadence rather than in the clumps tokens arrive in.
  //
  // **Display only, and that is load-bearing.** `streamingText` in the store is
  // still the truth, and it is what `chatStore` hands to `pushSpeech` — so the
  // voice starts on the first sentence that will not change again no matter how
  // much of it has been drawn. Speech must never wait on an animation.
  //
  // Markers are stripped *before* the reveal, not after, so `[M1]` disappearing
  // mid-flight cannot make the line jump backwards.
  const typedText = useTypedText(stripMarkers(streamingText), !isStreaming);

  // Files attached to the message being composed. Working state in the
  // truest sense — it lives here rather than in `chatStore`, because
  // `chatStore` holds the conversation and these are not part of it until
  // they are sent (rule 7d, one layer up).
  const sessionId = useChatStore((s) => s.sessionId);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [refused, setRefused] = useState<RefusedAttachment[]>([]);
  const [kept, setKept] = useState<string[]>([]);
  const [attachBusy, setAttachBusy] = useState<string | null>(null);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Depth counter, not a boolean. `dragleave` fires when the pointer crosses
  // into a *child* element, so a boolean flickers the overlay off every time
  // the cursor passes over the composer or a message.
  const dragDepth = useRef(0);

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
  const [readiness, recheckReadiness] = useReadiness();
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
  // named reason for each one — `SPEECH_NOT_INSTALLED`, "Playback was
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
  // request is in flight, idle otherwise — but never over the top of speech.
  useEffect(() => {
    // Both orbs read the same activity, so the small one in the top bar and the
    // large one on the landing can never disagree about what is happening.
    //
    // `preserveSpeaking` is what stops this effect clobbering the one state it
    // does not own. Speech begins on the first finished sentence and outlives
    // the stream by design, so the `idle` written here when generation ends
    // used to land on top of `speaking` on every single reply — which is why
    // the avatar's mouth never moved. Read with `getState()` rather than a
    // subscription: this must react to the stream changing, not to speech
    // changing, or it re-runs itself.
    setOrbState(preserveSpeaking(useOrbStore.getState().orbState, chatActivity(isStreaming)));
    setActivity(preserveSpeaking(useSystemStore.getState().activity, chatActivity(isStreaming)));
  }, [isStreaming, setOrbState, setActivity]);

  // What the backend already holds for this conversation.
  //
  // Read on mount because the backend clears attachments when it restarts:
  // chips drawn from local state alone would outlive the documents behind
  // them, and the user would ask a question about a file that is not there.
  useEffect(() => {
    let live = true;
    void listAttachments(sessionId)
      .then((held) => {
        if (live) setAttachments(held);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [sessionId]);

  const takeFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setAttachError(null);
      setAttachBusy('*');
      try {
        const result = await attachFiles(files, sessionId);
        setAttachments((current) => [...current, ...result.attached]);
        // Refusals accumulate rather than replace: dropping a second batch
        // must not erase the explanation for the first.
        setRefused((current) => [...current, ...result.refused]);
        if (result.evicted.length > 0) {
          // Eviction is reported because the alternative is a document
          // silently leaving scope while its chip is still on screen.
          const names = result.evicted.map((e) => e.name).join(', ');
          setAttachError(`Removed ${names} to make room — a conversation holds eight files.`);
          const gone = new Set(result.evicted.map((e) => e.id));
          setAttachments((current) => current.filter((a) => !gone.has(a.id)));
        }
      } catch (err) {
        setAttachError(err instanceof Error ? err.message : 'Could not attach that.');
      } finally {
        setAttachBusy(null);
      }
    },
    [sessionId],
  );

  /**
   * A screenshot pasted into the message box.
   *
   * The last way into the attachment path that was missing. The paperclip and
   * a drag both reached `takeFiles`; Ctrl+V did nothing, so the one gesture a
   * person uses immediately after taking a screenshot was the one gesture that
   * was not wired — and there is no keyboard route to the file picker either.
   *
   * **On the input, not on the window**, which is the opposite of
   * `KnowledgeWorkspace`'s handler and deliberately so: that one skips fields
   * because a paste into its search box is a search. Here the caret is in the
   * message box by definition, so a window listener that skipped fields would
   * never fire, and one that did not would take pastes from every other
   * surface mounted beside it.
   *
   * **Text pastes are untouched.** `preventDefault` is called only once files
   * are known to be present; a paste with nothing on it falls through to the
   * browser and types, which is what it must keep doing.
   *
   * Nothing here is a new route to a model. It reaches the same `takeFiles`
   * the paperclip does, so the same parse, the same eight-file cap, the same
   * refusals and the same vision gate apply — a paste that changed any of
   * those would be a second door of exactly the kind just closed elsewhere.
   */
  const handlePaste = useCallback(
    (event: React.ClipboardEvent<HTMLInputElement>) => {
      const files = filesFromClipboard(event.clipboardData);
      if (files.length === 0) return;
      event.preventDefault();
      void takeFiles(files.map((file) => withPasteName(file)));
    },
    [takeFiles],
  );

  const handleDetach = useCallback((id: string) => {
    // Removed from the composer first. The request is the authority on the
    // server's state, but the user asked for the chip to go, and leaving it
    // there until a round trip finishes reads as the button not working.
    setAttachments((current) => current.filter((a) => a.id !== id));
    setKept((current) => current.filter((k) => k !== id));
    void detachAttachment(id).catch(() => undefined);
  }, []);

  const handleKeep = useCallback(async (id: string) => {
    setAttachBusy(id);
    setAttachError(null);
    try {
      await keepAttachment(id);
      setKept((current) => [...current, id]);
    } catch (err) {
      setAttachError(err instanceof Error ? err.message : 'Could not keep that file.');
    } finally {
      setAttachBusy(null);
    }
  }, []);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || isStreaming) return;
    setInputText('');
    const ids = attachments.map((a) => a.id);
    // **The chips stay.** An attached file belongs to the conversation, not to
    // one message: "and what about clause 4" is the second question about the
    // same document, not a reason to upload it again. The backend scopes
    // attachments by session for exactly that, so clearing them here would
    // leave the files held and unreachable — the document silently out of
    // scope while the user believes Zaram is still reading it.
    //
    // Refusals do go, because they explain a drop that has now been read.
    setRefused([]);
    void send(text, ids.length > 0 ? { attachmentIds: ids } : {});
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
      // The whole panel is the drop target, not just the composer. Aiming at a
      // 40px-tall box is a precision task, and the thing being aimed at is the
      // conversation.
      //
      // `dragDepth` is a counter rather than a boolean because `dragleave`
      // fires whenever the pointer crosses into a child element — over a
      // message, over the composer — so a boolean flickers the overlay off
      // mid-drag.
      onDragEnter={(e) => {
        if (!e.dataTransfer?.types?.includes('Files')) return;
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(e) => {
        if (e.dataTransfer?.types?.includes('Files')) e.preventDefault();
      }}
      onDragLeave={() => {
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setDragging(false);
      }}
      onDrop={(e) => {
        if (!e.dataTransfer?.types?.includes('Files')) return;
        // Prevented, always. Without this the browser navigates away to the
        // dropped file and the conversation is simply gone.
        e.preventDefault();
        dragDepth.current = 0;
        setDragging(false);
        void takeFiles(Array.from(e.dataTransfer.files ?? []));
      }}
    >
      {dragging && (
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{
            zIndex: 70,
            background: 'rgba(15, 23, 42, 0.72)',
            border: '1px dashed var(--color-cyan-light)',
            borderRadius: 12,
          }}
        >
          <div className="flex flex-col items-center gap-2 text-center px-6">
            <Paperclip size={22} style={{ color: 'var(--color-cyan-light)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text)' }}>
              Drop to read it in this conversation
            </p>
            {/* Said at the moment of the drop, because this is the moment the
                user would otherwise assume the opposite. Rule 7d is invisible
                unless it is stated where the decision looks like it is made. */}
            <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              It is not added to Knowledge unless you keep it
            </p>
          </div>
        </div>
      )}
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
        <FirstRunPanel
          report={setupNeeded}
          onExplore={closeChat}
          onConnected={recheckReadiness}
        />
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
              {messages.map((msg, msgIndex) => (
                <div
                  key={msg.id}
                  // Who said it is now carried by *side* as well as by label and
                  // colour. Both speakers used to stack down the left edge,
                  // which made a long exchange read as one continuous document
                  // rather than as a conversation — the turn boundaries were
                  // there but you had to read the labels to find them.
                  //
                  // Capped short of the full width on purpose: a bubble that
                  // spans the panel has no visible right edge to be aligned to,
                  // so the alignment stops meaning anything on exactly the long
                  // messages where the cue is most useful.
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'stretch',
                    maxWidth: msg.role === 'user' ? '85%' : undefined,
                  }}
                >
                  {/* Speaker is named, not just coloured. Colour alone fails
                      colourblind users and is invisible to a screen reader,
                      which would otherwise read one unbroken wall of text.
                      Side is a third cue and, like colour, it is the one a
                      screen reader cannot use — so the label stays. */}
                  <p
                    className="text-[10px] uppercase tracking-wider mb-1"
                    style={{
                      color:
                        msg.role === 'user'
                          ? 'var(--color-text-muted)'
                          : 'var(--color-cyan)',
                      fontFamily: 'var(--font-display)',
                      textAlign: msg.role === 'user' ? 'right' : undefined,
                    }}
                  >
                    {msg.role === 'user' ? 'You' : 'Zaram'}
                  </p>
                  {/* Above the answer, because that is the order it happened in
                      and because a reader scanning back for *why* should not
                      have to pass the conclusion to reach the working. */}
                  {msg.role === 'assistant' && msg.reasoning && (
                    <ReasoningPanel text={msg.reasoning} streaming={false} />
                  )}
                  <p
                    className="text-sm leading-relaxed whitespace-pre-wrap"
                    style={{
                      color:
                        msg.role === 'user'
                          ? 'var(--color-text)'
                          : 'var(--color-cyan)',
                      // A second, non-colour cue: the assistant's replies are
                      // indented behind a rule. The user's get a quiet surface
                      // instead, so the right edge the text is aligned to is
                      // actually drawn — right-aligned text against nothing
                      // reads as a layout accident.
                      borderLeft:
                        msg.role === 'assistant'
                          ? '2px solid var(--color-cyan-light)'
                          : undefined,
                      paddingLeft: msg.role === 'assistant' ? 10 : undefined,
                      background:
                        msg.role === 'user' ? 'var(--color-glass)' : undefined,
                      border:
                        msg.role === 'user'
                          ? '1px solid rgba(255,255,255,0.06)'
                          : undefined,
                      borderRadius: msg.role === 'user' ? 12 : undefined,
                      padding: msg.role === 'user' ? '8px 12px' : undefined,
                    }}
                  >
                    {stripMarkers(msg.text)}
                  </p>
                  {/* Copy, and re-ask. Rendered for both speakers because both
                      are worth copying, and because "ask again" belongs on the
                      user's own message — that is the text being re-sent, and
                      putting the control on the reply would imply the reply is
                      what gets regenerated.
                      **Only the retry is withheld while a reply streams**, and
                      only because it would race the request in flight. Hiding
                      the whole row was the first attempt and it took copy off
                      every message in the history for as long as Zaram was
                      talking — a control disappearing from messages that
                      finished minutes ago, for a reason the user cannot see. */}
                  <MessageActions
                    text={msg.text}
                    align={msg.role === 'user' ? 'right' : 'left'}
                    onRetry={
                      msg.role === 'user' && !isStreaming
                        ? () => void send(msg.text)
                        : undefined
                    }
                    onEdit={
                      msg.role === 'user' && !isStreaming
                        ? () => {
                            setInputText(msg.text);
                            inputRef.current?.focus();
                          }
                        : undefined
                    }
                    retryLabel="Ask again"
                  />
                  {/* Who answered. Above the citations because it is a claim
                      about this reply rather than about a source, and because
                      a reply with no sources must still say where it came
                      from. */}
                  {msg.role === 'assistant' && (
                    <AnsweredBy
                      attribution={msg.answeredBy}
                      /* The question this reply answered, not the last thing
                         said. Re-asking from the middle of a history must
                         re-send *that* question — taking the most recent one
                         would silently answer something else and attribute it
                         to this point in the conversation. */
                      onAskAnother={
                        isStreaming
                          ? undefined
                          : (model) => {
                              const question = [...messages]
                                .slice(0, msgIndex)
                                .reverse()
                                .find((m) => m.role === 'user');
                              if (question) void send(question.text, { model });
                            }
                      }
                    />
                  )}
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
                  {/* A page written in this reply can be looked at, not only
                      read. Offered only when the reply actually contains one:
                      an always-present button that usually does nothing is the
                      standing tax rule 7h refuses — the offer belongs at the
                      moment of doubt, which is the moment markup arrives. */}
                  {msg.role === 'assistant' &&
                    (() => {
                      const block = extractPreviewable(msg.text);
                      if (!block) return null;
                      return (
                        <button
                          onClick={() => setCodePreview(block)}
                          className="mt-1.5 flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] hover:bg-white/5"
                          style={{
                            border: '1px solid var(--color-border)',
                            color: 'var(--color-text-muted)',
                          }}
                        >
                          <Eye size={12} />
                          Preview {block.label}
                        </button>
                      );
                    })()}
                  {/* Files made by this reply. CLAUDE.md: generated files
                      appear as cards in the conversation. */}
                  {msg.artifacts?.map((artifact) => (
                    <ArtifactCard key={artifact.id} artifact={artifact} />
                  ))}
                  {msg.notices?.map((notice, i) => (
                    <NoticeCard
                      key={i}
                      notice={notice}
                      onOpen={navigate}
                      onEnableSearch={enableSearchAndRetry}
                    />
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
                  {/* Arrives before the answer does, and on a reasoning model it
                      is the only thing on screen for the first several seconds.
                      Same argument as the `model_load` event: a wait that shows
                      its cause is explicable, and one that shows nothing reads
                      as a hang. */}
                  <ReasoningPanel text={streamingReasoning} streaming />
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
                        {typedText}
                      </p>
                    </>
                  )}
                  {/* The attribution arrives before the first token, which is
                      the point of sending it early: it is on screen while the
                      answer is being read, not appended once reading is done. */}
                  <AnsweredBy attribution={streamingAnsweredBy} />
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
                    <NoticeCard
                      key={i}
                      notice={notice}
                      onOpen={navigate}
                      onEnableSearch={enableSearchAndRetry}
                    />
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
        {/* What is in scope for the next message, above the box you type it
            in. Below the composer would put the evidence after the question. */}
        <AttachmentChips
          attachments={attachments}
          refused={refused}
          kept={kept}
          busy={attachBusy}
          onDetach={handleDetach}
          onKeep={(id) => void handleKeep(id)}
          onDismissRefusal={(name) => setRefused((c) => c.filter((r) => r.name !== name))}
        />
        {/* Not styled as an error: nothing failed in the conversation. Eviction
            and a refused file are both housekeeping the user has to be able to
            read, and red would train them to dread the whole row. */}
        {attachError && (
          <p
            className="mb-2 px-1 text-[11px] leading-relaxed"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {attachError}
          </p>
        )}
        <div className="relative">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            onChange={(e) => {
              void takeFiles(Array.from(e.target.files ?? []));
              // Reset, so choosing the same file twice in a row fires `change`
              // the second time. Without this, removing a file and picking it
              // again does nothing and looks like a broken button.
              e.target.value = '';
            }}
          />
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => {
              // Barge-in by typing. Talking over someone to stop them is how
              // interruption works everywhere else, and waiting for Zaram to
              // finish a paragraph you have already decided against is the
              // single most irritating thing a talking assistant does.
              //
              // On change rather than on focus: clicking into the composer to
              // read it back is not an interruption, and stopping there would
              // make the speech feel fragile instead of responsive.
              useSpeechStore.getState().bargeIn();
              setInputText(e.target.value);
            }}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={
              micStatus === 'recording'
                ? 'Listening on this machine…'
                : 'Ask Zaram anything…'
            }
            aria-label="Message Zaram"
            disabled={isStreaming}
            // pr-28 rather than pr-20: a third control joined the cluster, and
            // the padding is what keeps the caret from running underneath it.
            // The original note is worth keeping — the two controls plus their
            // gap occupied 68px, and 64px of padding put the caret under the
            // mic. One more button is 26px more.
            className="w-full pl-4 pr-28 py-3 text-sm bg-[var(--color-glass)] border border-white/5 rounded-xl text-slate-200 placeholder-slate-500 outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
          />
          {/* One positioned container, three ordinary buttons inside it.
              Each control used to place itself with its own `right-*` offset,
              which meant the spacing between them was a coincidence of two
              numbers in two files — and `whileHover` scaling either one closed
              the gap. See the note in `MicButton`. */}
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {/* Leftmost of the three, because it acts on the message before it
                is written while the mic and send act on sending it. */}
            <motion.button
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || attachBusy === '*'}
              aria-label="Attach a file"
              title="Attach a document to this message"
              className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <Paperclip size={16} className="text-slate-300" />
            </motion.button>
            <MicButton onTranscript={appendTranscript} disabled={isStreaming} />
            {/* Send, or stop — the same control, because they are the same
                decision at two moments and a second button would be dead for
                most of the product's life.

                **`cancel` existed and nothing called it.** The store has
                aborted the in-flight request on clear, on resume and on the
                next send since it was written; the one case it was never wired
                to was a person deciding, mid-answer, that this one is going
                wrong. On a machine where an oversized model takes minutes per
                reply that is not a convenience — it is the difference between
                watching three minutes of a wrong answer and asking a better
                question. */}
            {isStreaming ? (
              <motion.button
                onClick={() => cancel()}
                aria-label="Stop answering"
                title="Stop answering"
                className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Square size={16} fill="currentColor" className="text-slate-300" />
              </motion.button>
            ) : (
              <motion.button
                onClick={handleSend}
                disabled={!inputText.trim()}
                aria-label="Send message"
                className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Send size={16} className="text-slate-300" />
              </motion.button>
            )}
          </div>
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
            came here to do.

            Two scopes side by side because they are two different questions —
            which work this belongs to, and which library it may read from —
            and a question sits inside both at once. The domain picker removes
            itself when no domains exist, so this is one control until the user
            has made a reason for the second. */}
        <div className="mt-2 px-1 flex items-center gap-3 flex-wrap">
          <ProjectScopePicker />
          <DomainScopePicker />
          {/* The third axis, and the only one of the three that is about the
              user rather than about the work: where this may go. It sits here
              rather than in Settings because the alternative was six actions
              and a context switch for a decision that costs one. */}
          <RoutingControl />
        </div>
      </motion.div>
        </>
      )}

      {/* Markup written in a reply, brought forward over the orb — the same
          treatment a citation and a generated document already get. */}
      <AnimatePresence>
        {codePreview && (
          <CodePreviewPanel block={codePreview} onClose={() => setCodePreview(null)} />
        )}
      </AnimatePresence>

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
                navigate('activity');
                setPanel(null);
              }}
            />
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
