/**
 * ChatSurface — glass conversation panel sliding in from the left.
 *
 * Reads messages from the REAL conversation store (useConversationStore).
 * Drives replies through useStreamingText and orb state via useOrbStore.
 */
import { useEffect, useRef } from 'react';
import { motion, type Variants } from 'framer-motion';
import { Send } from 'lucide-react';
import { useConversationStore, useOrbStore } from '@/stores';
import useStreamingText from '@/hooks/useStreamingText';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

export default function ChatSurface() {
  const reduced = useIsReducedMotion();

  // Select only what we need from the conversation store
  const { messages, addMessage, inputText, setInputText } = useConversationStore(
    (s) => ({
      messages: s.messages,
      addMessage: s.addMessage,
      inputText: s.inputText,
      setInputText: s.setInputText,
    })
  );

  const { setOrbState } = useOrbStore((s) => ({ setOrbState: s.setOrbState }));

  const { displayedText, isStreaming, startStreaming } = useStreamingText();

  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-scroll on new messages or streaming
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages, displayedText]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    };
  }, []);

  const handleSend = async () => {
    const trimmed = inputText.trim();
    if (!trimmed || isStreaming) return;

    const now = new Date();

    // Push user message to the REAL store
    addMessage({
      id: `user-${Date.now()}`,
      text: trimmed,
      sender: 'user',
      timestamp: now,
    });
    setInputText('');

    // Orb -> thinking
    setOrbState('thinking');

    // Brief thinking pause, then stream reply
    typingTimeoutRef.current = setTimeout(async () => {
      setOrbState('speaking');

      const reply =
        "I'm here with you. What would you like to explore together?";

      await startStreaming(reply);

      // Orb -> idle when done streaming
      setOrbState('idle');
    }, 400);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  // Motion variants
  const container: Variants = {
    hidden: reduced
      ? { opacity: 0 }
      : { x: '100%', opacity: 0 },
    visible: {
      x: 0,
      opacity: 1,
      transition: {
        type: reduced ? 'tween' : 'spring',
        duration: reduced ? 0.25 : undefined,
        stiffness: reduced ? undefined : 260,
        damping: reduced ? undefined : 30,
        staggerChildren: 0.06,
      },
    },
    exit: reduced
      ? {
          opacity: 0,
          transition: {
            type: 'tween',
            duration: 0.25,
            staggerChildren: 0.06,
          },
        }
      : {
          x: '100%',
          opacity: 0,
          transition: {
            type: 'spring',
            stiffness: 260,
            damping: 30,
            staggerChildren: 0.06,
          },
        },
  };

  const item: Variants = {
    hidden: {
      opacity: 0,
      y: reduced ? 0 : 12,
    },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.3, ease: 'easeOut' },
    },
  };

  return (
    <motion.div
      key="chat-surface"
      className="fixed top-0 right-0 h-screen flex flex-col glass-border-indigo"
      style={{
        width: 440,
        zIndex: 60,
        backgroundColor: 'var(--color-glass)',
      }}
      variants={container}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      {/* Header */}
      <motion.div
        className="flex items-center gap-3 px-6 py-4 border-b border-white/5"
        variants={item}
        style={{
          backdropFilter: 'blur(20px) saturate(1.4)',
        }}
      >
        <motion.div
          className="w-2 h-2 rounded-full"
          style={{
            background: isStreaming
              ? 'var(--color-cyan)'
              : 'var(--color-violet)',
          }}
          animate={{
            opacity: isStreaming ? [1, 0.4, 1] : 0.6,
          }}
          transition={{
            duration: isStreaming ? 1.5 : 0,
            repeat: isStreaming ? Infinity : 0,
            ease: 'easeInOut',
          }}
        />
        <h2 className="text-sm font-medium text-slate-200">Conversation</h2>
      </motion.div>

      {/* Message list */}
      <motion.div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        variants={item}
      >
        <div className="flex flex-col gap-4 p-6">
          {messages.length === 0 && !displayedText ? (
            <p
              className="text-xs uppercase text-slate-500"
              style={{ letterSpacing: '0.05em' }}
            >
              Tap the orb to begin
            </p>
          ) : (
            <>
              {messages.map((msg) => (
                <p
                  key={msg.id}
                  className="text-sm leading-relaxed"
                  style={{
                    color:
                      msg.sender === 'user'
                        ? 'var(--color-text)'
                        : 'var(--color-cyan)',
                  }}
                >
                  {msg.text}
                </p>
              ))}
              {/* Streaming reply currently being typed */}
              {isStreaming && displayedText ? (
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: 'var(--color-cyan)' }}
                >
                  {displayedText}
                </p>
              ) : null}
            </>
          )}
        </div>
      </motion.div>

      {/* Input bar */}
      <motion.div
        className="p-4 border-t border-white/5"
        variants={item}
        style={{
          backdropFilter: 'blur(20px) saturate(1.4)',
        }}
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
            onClick={() => void handleSend()}
            disabled={isStreaming || !inputText.trim()}
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
