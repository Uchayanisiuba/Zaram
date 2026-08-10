import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence, useMotionValue, useTransform, useAnimationFrame } from 'motion/react';
import {
  Mic, MicOff, Send, Settings, X, MessageSquare,
  Volume2, Brain, BookOpen, Code2, Layers, Package,
  Search, Activity, Bell, User, Clock, Database,
  ChevronRight, Wifi, Cpu, Bookmark,
} from 'lucide-react';
import { LivingOrb } from './LivingOrb';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

// ── Orbital node data ────────────────────────────────────────────
// Angles: 270=top, 330=top-right, 30=bottom-right, 90=bottom, 150=bottom-left, 210=top-left
const ORBITAL_NODES = [
  { id: 'build',     label: 'Build',     icon: Code2,     color: '#818cf8', angle: 270, speed: 34 },
  { id: 'memory',    label: 'Memory',    icon: Brain,     color: '#c084fc', angle: 210, speed: 44 },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen,  color: '#22d3ee', angle: 330, speed: 38 },
  { id: 'plugins',   label: 'Plugins',   icon: Package,   color: '#fbbf24', angle: 150, speed: 50 },
  { id: 'canvas',    label: 'Canvas',    icon: Layers,    color: '#34d399', angle: 30,  speed: 42 },
  { id: 'settings',  label: 'Settings',  icon: Settings,  color: '#94a3b8', angle: 90,  speed: 56 },
];

const LEFT_RAIL_ITEMS = [
  { id: 'context',   label: 'Recent Context',  icon: Clock },
  { id: 'memory',    label: 'Pinned Memory',   icon: Bookmark },
  { id: 'knowledge', label: 'Knowledge',       icon: Database },
  { id: 'plugins',   label: 'Plugins',         icon: Package },
  { id: 'search',    label: 'Search',          icon: Search },
  { id: 'settings',  label: 'Settings',        icon: Settings },
];

const DOCK_ITEMS = [
  { id: 'search',    label: 'Search',    icon: Search },
  { id: 'build',     label: 'Build',     icon: Code2 },
  { id: 'memory',    label: 'Memory',    icon: Brain },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'canvas',    label: 'Canvas',    icon: Layers },
  { id: 'plugins',   label: 'Plugins',   icon: Package },
  { id: 'voice',     label: 'Voice',     icon: Mic },
  { id: 'settings',  label: 'Settings',  icon: Settings },
];

const ORBIT_RADIUS = 310;
const ORBIT_CONTAINER = 780;

// ── Smooth orbiting node using useAnimationFrame ─────────────────
interface OrbitalNodeProps {
  node: typeof ORBITAL_NODES[0];
  radius: number;
  onClick: () => void;
}

function OrbitalNode({ node, radius, onClick }: OrbitalNodeProps) {
  const angle = useMotionValue(node.angle);

  useAnimationFrame((_, delta) => {
    const degreesPerMs = 360 / (node.speed * 1000);
    angle.set(angle.get() + degreesPerMs * delta);
  });

  const x = useTransform(angle, (a) => Math.cos((a * Math.PI) / 180) * radius);
  const y = useTransform(angle, (a) => Math.sin((a * Math.PI) / 180) * radius);

  return (
    <motion.div
      className="absolute cursor-pointer z-20"
      style={{ left: '50%', top: '50%', x, y }}
      whileHover={{ scale: 1.18 }}
      whileTap={{ scale: 0.94 }}
      onClick={onClick}
    >
      {/* Centering wrapper */}
      <div style={{ transform: 'translate(-50%, -50%)' }}>
        <div className="flex flex-col items-center gap-2">
          {/* Glass card */}
          <motion.div
            className="w-14 h-14 rounded-2xl flex items-center justify-center"
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: `1px solid ${node.color}35`,
              backdropFilter: 'blur(10px)',
              boxShadow: `0 4px 24px rgba(0,0,0,0.3)`,
            }}
            whileHover={{
              background: `${node.color}18`,
              borderColor: `${node.color}70`,
              boxShadow: `0 0 24px ${node.color}50, 0 4px 24px rgba(0,0,0,0.3)`,
            }}
            transition={{ duration: 0.2 }}
          >
            <node.icon className="w-6 h-6" style={{ color: node.color }} />
          </motion.div>
          {/* Label */}
          <span
            className="text-slate-400 whitespace-nowrap select-none"
            style={{ fontSize: '11px', letterSpacing: '0.03em' }}
          >
            {node.label}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

// ── AI response generator ─────────────────────────────────────────
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
  return "Understood. I'm operating as a demo instance with simulated responses. In production, I'd reason over your local context, memory, and knowledge graph to answer precisely.";
}

// ── Main component ────────────────────────────────────────────────
export function ResponsiveAIAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [recognition, setRecognition] = useState<SpeechRecognition | null>(null);
  const [synth, setSynth] = useState<SpeechSynthesis | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const rec = new SR();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      rec.onresult = (e: SpeechRecognitionEvent) => { setInputText(e.results[0][0].transcript); setIsListening(false); };
      rec.onerror = () => setIsListening(false);
      rec.onend = () => setIsListening(false);
      setRecognition(rec);
    }
    if ('speechSynthesis' in window) setSynth(window.speechSynthesis);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    const userMsg: Message = { id: Date.now().toString(), text: inputText, sender: 'user', timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setShowChat(true);
    setIsThinking(true);
    const captured = inputText;
    setInputText('');
    setTimeout(() => {
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        text: generateAIResponse(captured),
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsThinking(false);
    }, 1200);
  }, [inputText]);

  const handleVoice = () => {
    if (!recognition) return;
    if (isListening) { recognition.stop(); setIsListening(false); }
    else { recognition.start(); setIsListening(true); }
  };

  const handleSpeak = (text: string) => {
    if (!synth) return;
    if (isSpeaking) { synth.cancel(); setIsSpeaking(false); return; }
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.85;
    utt.onstart = () => setIsSpeaking(true);
    utt.onend = () => setIsSpeaking(false);
    utt.onerror = () => setIsSpeaking(false);
    synth.speak(utt);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleNodeClick = (nodeId: string) => {
    setActiveNode(nodeId);
    setShowChat(true);
    setIsThinking(true);
    setTimeout(() => {
      setMessages([{
        id: Date.now().toString(),
        text: `Opening ${nodeId.charAt(0).toUpperCase() + nodeId.slice(1)} workspace. This module is ready — how would you like to begin?`,
        sender: 'ai',
        timestamp: new Date(),
      }]);
      setIsThinking(false);
    }, 800);
  };

  return (
    <div
      className="h-screen overflow-hidden text-slate-100 flex flex-col"
      style={{
        background: 'radial-gradient(ellipse at 25% 15%, rgba(99,102,241,0.08) 0%, transparent 52%), radial-gradient(ellipse at 75% 85%, rgba(168,85,247,0.06) 0%, transparent 52%), #08080f',
        fontFamily: "'Space Grotesk', 'Inter', sans-serif",
      }}
    >
      {/* ── Top Navigation ─────────────────────────────── */}
      <div
        className="h-10 shrink-0 flex items-center justify-between px-5 border-b border-white/5 z-40"
        style={{ background: 'rgba(6,7,9,0.80)', backdropFilter: 'blur(16px)' }}
      >
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden text-slate-400 hover:text-slate-200 transition-colors p-1 mr-1"
            onClick={() => setShowMobileSidebar(true)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <span className="text-sm text-slate-100" style={{ fontWeight: 600, letterSpacing: '0.08em' }}>ZARAM</span>
          <div
            className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            <motion.div
              className="w-1.5 h-1.5 rounded-full bg-emerald-400"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-xs text-slate-400 uppercase" style={{ fontSize: '10px', letterSpacing: '0.06em' }}>
              Local Active
            </span>
          </div>
          {showChat && (
            <span className="text-slate-600 text-xs hidden sm:block">
              / {activeNode ? activeNode.charAt(0).toUpperCase() + activeNode.slice(1) : 'Chat'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden md:flex items-center gap-1 text-xs" style={{ color: '#475569', fontVariantNumeric: 'tabular-nums', fontSize: '11px' }}>
            <Cpu className="w-3 h-3" />
            <span>Neural Engine</span>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-xs" style={{ color: '#475569', fontSize: '11px' }}>
            <Wifi className="w-3 h-3" />
          </div>
          <Bell className="w-3.5 h-3.5 text-slate-600 hover:text-slate-300 cursor-pointer transition-colors" />
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(99,102,241,0.35)', border: '1px solid rgba(99,102,241,0.4)' }}
          >
            <User className="w-3 h-3 text-indigo-200" />
          </div>
        </div>
      </div>

      {/* ── Body Row ─────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left Rail (desktop) ──────────────────────── */}
        <div
          className="hidden lg:flex flex-col shrink-0 border-r border-white/5 overflow-hidden z-30 transition-all duration-300 ease-in-out"
          style={{ width: '56px', background: 'rgba(6,7,9,0.60)', backdropFilter: 'blur(16px)' }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.width = '224px'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.width = '56px'; }}
        >
          <div className="flex-1 py-3 flex flex-col gap-0.5">
            {LEFT_RAIL_ITEMS.map(item => (
              <button
                key={item.id}
                className="flex items-center gap-3 px-4 py-3 w-full text-left transition-colors hover:bg-white/5"
                style={{ minWidth: '224px' }}
              >
                <item.icon className="w-4 h-4 shrink-0 text-slate-600 group-hover:text-slate-400" style={{ minWidth: 16 }} />
                <span className="text-xs text-slate-500 whitespace-nowrap" style={{ letterSpacing: '0.01em' }}>{item.label}</span>
              </button>
            ))}
          </div>
          <div className="p-3 border-t border-white/5">
            <button
              className="flex items-center gap-3 w-full hover:bg-white/5 p-1.5 rounded-xl transition-colors"
              style={{ minWidth: '200px' }}
            >
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                style={{ background: 'rgba(99,102,241,0.30)', border: '1px solid rgba(99,102,241,0.35)' }}
              >
                <User className="w-3.5 h-3.5 text-indigo-300" />
              </div>
              <span className="text-xs text-slate-500 whitespace-nowrap">Profile</span>
            </button>
          </div>
        </div>

        {/* ── Center Workspace ─────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0 relative overflow-hidden">
          <AnimatePresence mode="wait">
            {!showChat ? (
              /* ── Landing: Orb + Orbital Nodes ──────── */
              <motion.div
                key="landing"
                className="flex-1 flex flex-col items-center justify-center relative pb-16 overflow-hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ duration: 0.4 }}
              >
                {/* Subtle grid background */}
                <div
                  className="absolute inset-0 opacity-[0.04] pointer-events-none"
                  style={{
                    backgroundImage: 'linear-gradient(rgba(99,102,241,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.6) 1px, transparent 1px)',
                    backgroundSize: '56px 56px',
                  }}
                />

                {/* Orbital system */}
                <div
                  className="relative flex items-center justify-center"
                  style={{
                    width: `min(${ORBIT_CONTAINER}px, min(90vw, 82vh))`,
                    height: `min(${ORBIT_CONTAINER}px, min(90vw, 82vh))`,
                  }}
                >
                  {/* Orbital track rings */}
                  <div
                    className="absolute rounded-full pointer-events-none"
                    style={{
                      width: ORBIT_RADIUS * 2 + 60,
                      height: ORBIT_RADIUS * 2 + 60,
                      border: '1px solid rgba(255,255,255,0.04)',
                    }}
                  />
                  <div
                    className="absolute rounded-full pointer-events-none"
                    style={{
                      width: ORBIT_RADIUS * 2 + 110,
                      height: ORBIT_RADIUS * 2 + 110,
                      border: '1px solid rgba(255,255,255,0.025)',
                    }}
                  />

                  {/* Slowly orbiting nodes */}
                  {ORBITAL_NODES.map(node => (
                    <OrbitalNode
                      key={node.id}
                      node={node}
                      radius={ORBIT_RADIUS}
                      onClick={() => handleNodeClick(node.id)}
                    />
                  ))}

                  {/* Central Living Orb */}
                  <div className="relative z-10 flex flex-col items-center">
                    <LivingOrb
                      isListening={isListening}
                      isSpeaking={isSpeaking}
                      isThinking={isThinking}
                      size="lg"
                    />
                  </div>
                </div>

                {/* Tagline */}
                <motion.div
                  className="text-center mt-4 space-y-1"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                >
                  <p className="text-slate-500 text-xs tracking-widest uppercase" style={{ letterSpacing: '0.12em' }}>
                    Living Intelligence · Local First
                  </p>
                </motion.div>
              </motion.div>
            ) : (
              /* ── Chat / Workspace ───────────────────── */
              <motion.div
                key="chat"
                className="flex-1 flex flex-col min-h-0"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {/* Workspace header */}
                <div
                  className="flex items-center justify-between px-5 py-2.5 border-b border-white/5 shrink-0"
                  style={{ background: 'rgba(6,7,9,0.50)', backdropFilter: 'blur(8px)' }}
                >
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { setShowChat(false); setActiveNode(null); setMessages([]); }}
                      className="text-slate-600 hover:text-slate-300 transition-colors p-1 rounded-lg hover:bg-white/5"
                    >
                      <ChevronRight className="w-3.5 h-3.5 rotate-180" />
                    </button>
                    <span className="text-xs text-slate-400" style={{ letterSpacing: '0.02em' }}>
                      {activeNode ? `${activeNode.charAt(0).toUpperCase() + activeNode.slice(1)} Workspace` : 'Chat'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isThinking && (
                      <motion.div
                        className="flex items-center gap-1.5"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                      >
                        {[0, 1, 2].map(i => (
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
                    <span className="text-xs text-slate-700">{messages.length} msg</span>
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}>
                  {messages.length === 0 && !isThinking && (
                    <div className="flex items-center justify-center h-full">
                      <p className="text-slate-700 text-sm">Start the conversation…</p>
                    </div>
                  )}
                  {messages.map(msg => (
                    <motion.div
                      key={msg.id}
                      className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.22 }}
                    >
                      {msg.sender === 'ai' && (
                        <div className="mr-3 mt-1 shrink-0">
                          <LivingOrb size="xs" isSpeaking={isSpeaking} isThinking={isThinking} />
                        </div>
                      )}
                      <div
                        className="max-w-[78%] lg:max-w-[65%] rounded-2xl px-4 py-3.5"
                        style={
                          msg.sender === 'user'
                            ? {
                                background: 'rgba(99,102,241,0.22)',
                                border: '1px solid rgba(99,102,241,0.32)',
                                backdropFilter: 'blur(10px)',
                                borderTopRightRadius: 4,
                              }
                            : {
                                background: 'rgba(255,255,255,0.04)',
                                border: '1px solid rgba(255,255,255,0.07)',
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
                              className="text-slate-700 hover:text-cyan-400 transition-colors"
                            >
                              <Volume2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Chat Input ───────────────────────────────── */}
          <div className="shrink-0 px-5 pb-24 pt-3 z-20">
            <div
              className="rounded-2xl overflow-hidden transition-all duration-200"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                backdropFilter: 'blur(20px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.36)',
              }}
            >
              <div className="flex items-center gap-3 px-4 py-3">
                <input
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Message Zaram…"
                  className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-700 outline-none"
                />
                <button
                  onClick={handleVoice}
                  className={`p-2 rounded-xl transition-all ${
                    isListening
                      ? 'text-red-400 bg-red-500/12 border border-red-400/25'
                      : 'text-slate-600 hover:text-indigo-400 hover:bg-indigo-500/10'
                  }`}
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
                <button
                  onClick={handleSend}
                  disabled={!inputText.trim()}
                  className="p-2 rounded-xl transition-all disabled:opacity-30 disabled:pointer-events-none"
                  style={{ background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.28)', color: '#22d3ee' }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(34,211,238,0.22)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(34,211,238,0.12)'; }}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>

              {/* Waveform feedback */}
              <AnimatePresence>
                {(isListening || isSpeaking) && (
                  <motion.div
                    className="px-5 pb-3 flex items-center gap-2"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                  >
                    {[0, 1, 2, 3, 4, 5, 6].map(i => (
                      <motion.div
                        key={i}
                        className="w-0.5 rounded-full"
                        style={{ background: 'linear-gradient(to top, #6366f1, #22d3ee)' }}
                        animate={{ height: [`4px`, `${6 + (i % 3) * 8}px`, `4px`] }}
                        transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.07, ease: 'easeInOut' }}
                      />
                    ))}
                    <span className="text-xs text-indigo-400 ml-1">
                      {isListening ? 'Listening…' : 'Speaking…'}
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* ── Runtime Panel (xl desktops) ──────────────── */}
        <div
          className="hidden xl:flex flex-col shrink-0 border-l border-white/5 overflow-y-auto"
          style={{
            width: '280px',
            background: 'rgba(6,7,9,0.60)',
            backdropFilter: 'blur(16px)',
            scrollbarWidth: 'none',
          }}
        >
          <div className="px-4 py-3 border-b border-white/5">
            <p className="text-xs text-slate-600 uppercase" style={{ letterSpacing: '0.1em' }}>AI Runtime</p>
          </div>

          {/* Mini orb */}
          <div className="flex flex-col items-center py-8 border-b border-white/5">
            <LivingOrb
              isListening={isListening}
              isSpeaking={isSpeaking}
              isThinking={isThinking}
              size="sm"
            />
            <div className="mt-4 flex items-center gap-2">
              <motion.div
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: isListening ? '#22d3ee' : isThinking ? '#c084fc' : isSpeaking ? '#34d399' : '#34d399',
                }}
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <span className="text-xs text-slate-500">
                {isListening ? 'Listening' : isThinking ? 'Thinking' : isSpeaking ? 'Speaking' : 'Ready'}
              </span>
            </div>
          </div>

          <div className="px-4 py-5 space-y-5">
            {/* Memory */}
            <div>
              <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>Memory</p>
              {[{ label: 'Context Window', value: 68, color: '#6366f1' }, { label: 'Recall Index', value: 92, color: '#22d3ee' }].map(item => (
                <div key={item.label} className="mb-3">
                  <div className="flex justify-between mb-1.5">
                    <span className="text-xs text-slate-600">{item.label}</span>
                    <span className="text-xs text-slate-600" style={{ fontVariantNumeric: 'tabular-nums' }}>{item.value}%</span>
                  </div>
                  <div className="h-0.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: `linear-gradient(to right, ${item.color}, rgba(34,211,238,0.8))` }}
                      initial={{ width: 0 }}
                      animate={{ width: `${item.value}%` }}
                      transition={{ duration: 1.4, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Context */}
            <div>
              <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>Active Context</p>
              <div className="space-y-2">
                {[
                  { label: 'Current session', icon: MessageSquare },
                  { label: 'Local neural engine', icon: Cpu },
                  { label: 'Knowledge graph', icon: Database },
                ].map(item => (
                  <div key={item.label} className="flex items-center gap-2.5 py-1.5">
                    <item.icon className="w-3 h-3 text-slate-700" />
                    <span className="text-xs text-slate-600">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Agent */}
            <div>
              <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>Agents</p>
              <div
                className="rounded-xl p-3 flex items-center gap-2.5"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}
              >
                <motion.div
                  className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                  animate={{ scale: [1, 1.4, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="text-xs text-slate-500">Core agent active</span>
              </div>
            </div>

            {/* Voice */}
            <div>
              <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>Voice</p>
              <div className="flex gap-2">
                <button
                  onClick={handleVoice}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs transition-all"
                  style={
                    isListening
                      ? { background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.30)', color: '#f87171' }
                      : { background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', color: '#64748b' }
                  }
                >
                  {isListening ? <MicOff className="w-3 h-3" /> : <Mic className="w-3 h-3" />}
                  {isListening ? 'Stop' : 'Input'}
                </button>
                <button
                  onClick={() => { const lastAi = messages.filter(m => m.sender === 'ai').slice(-1)[0]; if (lastAi) handleSpeak(lastAi.text); }}
                  disabled={!messages.some(m => m.sender === 'ai')}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs transition-all disabled:opacity-30 disabled:pointer-events-none"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', color: '#64748b' }}
                >
                  <Volume2 className="w-3 h-3" />
                  Output
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Bottom Command Dock ──────────────────────────── */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
        <div
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-2xl pointer-events-auto"
          style={{
            background: 'rgba(6,7,9,0.88)',
            border: '1px solid rgba(255,255,255,0.09)',
            backdropFilter: 'blur(24px)',
            boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
          }}
        >
          {DOCK_ITEMS.map((item, i) => (
            <React.Fragment key={item.id}>
              {i === 4 && <div className="w-px h-6 mx-0.5" style={{ background: 'rgba(255,255,255,0.08)' }} />}
              <motion.button
                className="relative flex items-center justify-center w-10 h-10 rounded-xl transition-colors group"
                style={{ color: item.id === 'voice' && isListening ? '#f87171' : '#475569' }}
                whileHover={{ y: -6, scale: 1.2 }}
                whileTap={{ scale: 0.92 }}
                transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                onClick={() => {
                  if (item.id === 'voice') handleVoice();
                  else handleNodeClick(item.id);
                }}
                title={item.label}
              >
                <item.icon className="w-4 h-4 group-hover:text-indigo-300 transition-colors" />
                {/* Tooltip */}
                <span
                  className="absolute -top-9 left-1/2 -translate-x-1/2 text-xs text-slate-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none rounded-lg px-2.5 py-1"
                  style={{ background: 'rgba(10,10,20,0.96)', border: '1px solid rgba(255,255,255,0.07)' }}
                >
                  {item.label}
                </span>
              </motion.button>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Mobile Sidebar ───────────────────────────────── */}
      <AnimatePresence>
        {showMobileSidebar && (
          <motion.div
            className="fixed inset-0 z-50 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowMobileSidebar(false)}
          >
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <motion.div
              className="absolute left-0 top-0 h-full w-64 flex flex-col"
              style={{
                background: 'rgba(8,8,16,0.97)',
                border: '1px solid rgba(255,255,255,0.07)',
                backdropFilter: 'blur(24px)',
              }}
              initial={{ x: -264 }}
              animate={{ x: 0 }}
              exit={{ x: -264 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/5">
                <span className="text-sm text-slate-200" style={{ fontWeight: 600, letterSpacing: '0.08em' }}>ZARAM</span>
                <button onClick={() => setShowMobileSidebar(false)} className="text-slate-600 hover:text-slate-300 transition-colors p-1">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 py-3">
                {LEFT_RAIL_ITEMS.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setShowMobileSidebar(false)}
                    className="flex items-center gap-3 px-5 py-3 hover:bg-white/5 w-full text-left transition-colors"
                  >
                    <item.icon className="w-4 h-4 text-slate-600" />
                    <span className="text-sm text-slate-500">{item.label}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
