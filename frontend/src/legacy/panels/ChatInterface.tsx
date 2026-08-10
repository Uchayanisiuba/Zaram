/**
 * ChatInterface
 *
 * The conversational workspace that appears when a user sends a message
 * or clicks an orbital node. Lives inside CenterWorkspace alongside
 * WorkspaceSurface — AnimatePresence in WorkspaceSurface handles the
 * landing ↔ chat transition.
 *
 * Architecture: reads/writes conversationStore. Drives orbStore state
 * (thinking → idle) during AI response simulation.
 */
import React, { useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Volume2, Mic, MicOff, Send } from 'lucide-react';
import { useOrbStore, useConversationStore } from '@/stores';
import type { Message } from '@/stores';

// ── Simple AI stub — replace with real backend call ─────────────────────────
function generateAIResponse(userMessage: string): string {
  const lower = userMessage.toLowerCase();
  if (lower.includes('hello') || lower.includes('hi'))
    return "Hello. I'm Zaram — your local-first living AI system. I exist at the intersection of memory, knowledge, and action. How may I assist you?";
  if (lower.includes('weather'))
    return "I'd need access to a live weather service for real-time conditions. In a full deployment, I'd query that locally and synthesize the forecast for you.";
  if (lower.includes('time'))
    return `Current system time is ${new Date().toLocaleTimeString()}.`;
  if (lower.includes('help'))
    return "You can speak or type to interact with me. I can build, recall memory, search knowledge, run agents, and operate across your entire workspace.";
  if (lower.includes('memory'))
    return "Memory Runtime is active. I currently hold context from this session and have access to your pinned memory nodes in the knowledge graph.";
  if (lower.includes('build') || lower.includes('code'))
    return "Build workspace is ready. I can scaffold components, review code, run diagnostics, and integrate with your local dev toolchain.";
  return "Understood. I'm operating as a demo instance with simulated responses. In production, I'd reason over your local context, memory, and knowledge graph to answer precisely.";
}

// ── Small orb avatar used beside AI messages ────────────────────────────────
function OrbAvatar() {
  const { orbState } = useOrbStore();
  const color = orbState === 'thinking' ? '#c084fc'
    : orbState === 'speaking' ? '#34d399'
    : '#6366f1';

  return (
    <div
      className="shrink-0 rounded-full flex items-center justify-center mt-1"
      style={{
        width: 28,
        height: 28,
        background: `radial-gradient(circle, ${color}44 0%, ${color}11 70%)`,
        border: `1px solid ${color}44`,
        boxShadow: `0 0 10px ${color}33`,
      }}
    >
      <motion.div
        className="rounded-full bg-white"
        style={{ width: 6, height: 6, boxShadow: '0 0 6px rgba(255,255,255,0.8)' }}
        animate={{ opacity: [0.4, 0.9, 0.4], scale: [0.8, 1.2, 0.8] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}

// ── Waveform feedback bar (listening / speaking) ─────────────────────────────
const WAVE_BARS = [0, 1, 2, 3, 4, 5, 6];

function WaveformFeedback({ label }: { label: string }) {
  return (
    <div className="px-4 pb-3 flex items-center gap-2">
      {WAVE_BARS.map((i) => (
        <motion.div
          key={i}
          className="w-0.5 rounded-full"
          style={{ background: 'linear-gradient(to top, #6366f1, #22d3ee)' }}
          animate={{ height: [`4px`, `${6 + (i % 3) * 8}px`, `4px`] }}
          transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.07, ease: 'easeInOut' }}
        />
      ))}
      <span className="text-xs text-indigo-400 ml-1">{label}</span>
    </div>
  );
}

// ── Main ChatInterface ───────────────────────────────────────────────────────
export function ChatInterface() {
  const {
    messages,
    isThinking,
    activeNode,
    inputText,
    addMessage,
    clearMessages,
    setIsThinking,
    setShowChat,
    setActiveNode,
    setInputText,
  } = useConversationStore();

  const { orbState, setOrbState } = useOrbStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Speech APIs
  const recRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);

  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const rec: any = new SR();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      rec.onresult = (e: SpeechRecognitionEvent) => {
        setInputText(e.results[0][0].transcript);
        setOrbState('idle');
      };
      rec.onerror = () => setOrbState('idle');
      rec.onend   = () => {
        if (orbState === 'listening') setOrbState('idle');
      };
      recRef.current = rec;
    }
    if ('speechSynthesis' in window) synthRef.current = window.speechSynthesis;
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date(),
    };
    addMessage(userMsg);
    setIsThinking(true);
    setOrbState('thinking');

    const captured = inputText;
    setInputText('');

    setTimeout(() => {
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        text: generateAIResponse(captured),
        sender: 'ai',
        timestamp: new Date(),
      };
      addMessage(aiMsg);
      setIsThinking(false);
      setOrbState('idle');
    }, 1200);
  }, [inputText, addMessage, setIsThinking, setInputText, setOrbState]);

  const handleVoice = useCallback(() => {
    if (!recRef.current) return;
    if (orbState === 'listening') {
      recRef.current.stop();
      setOrbState('idle');
    } else {
      recRef.current.start();
      setOrbState('listening');
    }
  }, [orbState, setOrbState]);

  const handleSpeak = useCallback((text: string) => {
    if (!synthRef.current) return;
    if (orbState === 'speaking') {
      synthRef.current.cancel();
      setOrbState('idle');
      return;
    }
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.85;
    utt.onstart = () => setOrbState('speaking');
    utt.onend   = () => setOrbState('idle');
    utt.onerror = () => setOrbState('idle');
    synthRef.current.speak(utt);
  }, [orbState, setOrbState]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleBack = () => {
    setShowChat(false);
    setActiveNode(null);
    clearMessages();
    setOrbState('idle');
  };

  const isListening = orbState === 'listening';
  const isSpeaking  = orbState === 'speaking';

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* ── Workspace header ── */}
      <div
        className="flex items-center justify-between px-5 py-2.5 border-b shrink-0"
        style={{
          background: 'rgba(6,7,9,0.50)',
          backdropFilter: 'blur(8px)',
          borderColor: 'var(--glass-border)',
        }}
      >
        <div className="flex items-center gap-2">
          <button
            onClick={handleBack}
            className="text-slate-600 hover:text-slate-300 transition-colors p-1 rounded-lg hover:bg-white/5"
            aria-label="Back to home"
          >
            <ChevronRight className="w-3.5 h-3.5 rotate-180" />
          </button>
          <span className="text-xs text-slate-400" style={{ letterSpacing: '0.02em' }}>
            {activeNode
              ? `${activeNode.charAt(0).toUpperCase() + activeNode.slice(1)} Workspace`
              : 'Chat'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Thinking indicator */}
          <AnimatePresence>
            {isThinking && (
              <motion.div
                className="flex items-center gap-1.5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-indigo-400"
                    animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
                <span className="text-xs text-indigo-400/70 ml-0.5">Thinking</span>
              </motion.div>
            )}
          </AnimatePresence>
          <span className="text-xs text-slate-700">{messages.length} msg</span>
        </div>
      </div>

      {/* ── Messages ── */}
      <div
        className="flex-1 overflow-y-auto px-5 py-5 space-y-4 scroll-thin"
        style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
      >
        {messages.length === 0 && !isThinking && (
          <div className="flex items-center justify-center h-full">
            <p className="text-slate-700 text-sm">Start the conversation…</p>
          </div>
        )}

        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
          >
            {msg.sender === 'ai' && (
              <div className="mr-2.5">
                <OrbAvatar />
              </div>
            )}

            <div
              className="max-w-[78%] lg:max-w-[65%] rounded-2xl px-4 py-3.5"
              style={
                msg.sender === 'user'
                  ? {
                      background:     'rgba(99,102,241,0.22)',
                      border:         '1px solid rgba(99,102,241,0.32)',
                      backdropFilter: 'blur(10px)',
                      borderTopRightRadius: 4,
                    }
                  : {
                      background:     'rgba(255,255,255,0.04)',
                      border:         '1px solid rgba(255,255,255,0.07)',
                      backdropFilter: 'blur(10px)',
                      borderTopLeftRadius: 4,
                    }
              }
            >
              <p className="text-sm text-slate-200 leading-relaxed">{msg.text}</p>
              <div className="flex items-center justify-between mt-2 gap-3">
                <span className="text-slate-700" style={{ fontSize: '11px' }}>
                  {msg.timestamp.toLocaleTimeString()}
                </span>
                {msg.sender === 'ai' && (
                  <button
                    onClick={() => handleSpeak(msg.text)}
                    className={`transition-colors ${
                      isSpeaking ? 'text-emerald-400' : 'text-slate-700 hover:text-cyan-400'
                    }`}
                    aria-label="Speak this message"
                  >
                    <Volume2 className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        ))}

        {/* AI typing indicator */}
        <AnimatePresence>
          {isThinking && (
            <motion.div
              className="flex justify-start"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="mr-2.5">
                <OrbAvatar />
              </div>
              <div
                className="rounded-2xl px-4 py-3.5 flex items-center gap-1.5"
                style={{
                  background:          'rgba(255,255,255,0.04)',
                  border:              '1px solid rgba(255,255,255,0.07)',
                  borderTopLeftRadius: 4,
                }}
              >
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-slate-500"
                    animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.18 }}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input bar ── */}
      <div className="shrink-0 px-5 pb-20 pt-3">
        <div
          className="rounded-2xl overflow-hidden transition-all duration-200"
          style={{
            background:     'rgba(255,255,255,0.04)',
            border:         '1px solid rgba(255,255,255,0.08)',
            backdropFilter: 'blur(20px)',
            boxShadow:      '0 8px 32px rgba(0,0,0,0.36)',
          }}
        >
          <div className="flex items-center gap-3 px-4 py-3">
            <input
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Zaram…"
              className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-700 outline-none"
              autoFocus
            />

            {/* Voice toggle */}
            <button
              onClick={handleVoice}
              className={`p-2 rounded-xl transition-all ${
                isListening
                  ? 'text-red-400 bg-red-500/12 border border-red-400/25'
                  : 'text-slate-600 hover:text-indigo-400 hover:bg-indigo-500/10'
              }`}
              aria-label={isListening ? 'Stop listening' : 'Start voice input'}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={!inputText.trim()}
              className="p-2 rounded-xl transition-all disabled:opacity-30 disabled:pointer-events-none"
              style={{
                background: 'rgba(34,211,238,0.12)',
                border:     '1px solid rgba(34,211,238,0.28)',
                color:      '#22d3ee',
              }}
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* Waveform feedback row */}
          <AnimatePresence>
            {(isListening || isSpeaking) && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                style={{ overflow: 'hidden' }}
              >
                <WaveformFeedback label={isListening ? 'Listening…' : 'Speaking…'} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;
