/**
 * WorkspaceSurface
 *
 * Stage 4 consumer: bridges frameStore (engine output) into the visual layer.
 * Switches between landing (Orb + orbital nodes) and chat workspace via
 * AnimatePresence. All conversation state lives in conversationStore.
 *
 * Architecture compliance:
 * - Reads frameStore (Stage 3 output) for orb visual state.
 * - Reads orbStore for high-level state label.
 * - Does NOT import simulation or semantic types.
 */
import React, { useCallback } from 'react';
import { motion, AnimatePresence, useMotionValue, useTransform, useAnimationFrame } from 'framer-motion';
import {
  Code2, Brain, BookOpen, Package, Layers, Settings,
  Mic, MicOff, Send,
} from 'lucide-react';
import { useOrbStore, useConversationStore } from '@/stores';
import LivingOrb from '@/components/orb/LivingOrb';
import ChatInterface from '@/components/panels/ChatInterface';

// ── Orbital node configuration ───────────────────────────────────────────────
const ORBITAL_NODES = [
  { id: 'build',     label: 'Build',     icon: Code2,     color: '#818cf8', angle: 270, speed: 34 },
  { id: 'memory',    label: 'Memory',    icon: Brain,     color: '#c084fc', angle: 210, speed: 44 },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen,  color: '#22d3ee', angle: 330, speed: 38 },
  { id: 'plugins',   label: 'Plugins',   icon: Package,   color: '#fbbf24', angle: 150, speed: 50 },
  { id: 'canvas',    label: 'Canvas',    icon: Layers,    color: '#34d399', angle:  30, speed: 42 },
  { id: 'settings',  label: 'Settings',  icon: Settings,  color: '#94a3b8', angle:  90, speed: 56 },
];

const ORBIT_RADIUS = 280;
const ORBIT_CONTAINER = 720;

// ── Single orbiting node ─────────────────────────────────────────────────────
interface OrbitalNodeProps {
  node: typeof ORBITAL_NODES[0];
  radius: number;
  onClick: (id: string) => void;
}

function OrbitalNodeItem({ node, radius, onClick }: OrbitalNodeProps) {
  const angle = useMotionValue(node.angle);

  useAnimationFrame((_, delta) => {
    const degsPerMs = 360 / (node.speed * 1000);
    angle.set(angle.get() + degsPerMs * delta);
  });

  const x = useTransform(angle, (a) => Math.cos((a * Math.PI) / 180) * radius);
  const y = useTransform(angle, (a) => Math.sin((a * Math.PI) / 180) * radius);

  return (
    <motion.div
      className="absolute cursor-pointer z-20"
      style={{ left: '50%', top: '50%', x, y }}
      whileHover={{ scale: 1.18 }}
      whileTap={{ scale: 0.94 }}
      onClick={() => onClick(node.id)}
    >
      <div style={{ transform: 'translate(-50%, -50%)' }}>
        <div className="flex flex-col items-center gap-2">
          <motion.div
            className="w-14 h-14 rounded-2xl flex items-center justify-center"
            style={{
              background:     'rgba(255,255,255,0.05)',
              border:         `1px solid ${node.color}35`,
              backdropFilter: 'blur(10px)',
              boxShadow:      '0 4px 24px rgba(0,0,0,0.3)',
            }}
            whileHover={{
              background:  `${node.color}18`,
              borderColor: `${node.color}70`,
              boxShadow:   `0 0 24px ${node.color}50, 0 4px 24px rgba(0,0,0,0.3)`,
            }}
            transition={{ duration: 0.2 }}
          >
            <node.icon className="w-6 h-6" style={{ color: node.color }} />
          </motion.div>
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

// ── Landing input bar (shown on the home screen before any chat) ─────────────
function LandingInputBar() {
  const { inputText, setInputText, setShowChat, addMessage, setIsThinking } =
    useConversationStore();
  const { orbState, setOrbState } = useOrbStore();
  const isListening = orbState === 'listening';

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    addMessage({
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date(),
    });
    setInputText('');
    setShowChat(true);
    setIsThinking(true);
    setOrbState('thinking');

    const captured = inputText;
    setTimeout(() => {
      addMessage({
        id: (Date.now() + 1).toString(),
        text: `You said: "${captured}". I'm Zaram — your local-first AI. In production I'd reason over your context, memory, and knowledge graph to answer precisely.`,
        sender: 'ai',
        timestamp: new Date(),
      });
      setIsThinking(false);
      setOrbState('idle');
    }, 1200);
  }, [inputText, addMessage, setInputText, setShowChat, setIsThinking, setOrbState]);

  const handleVoice = () => {
    setOrbState(isListening ? 'idle' : 'listening');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="shrink-0 w-full max-w-2xl mx-auto px-4 pb-24 pt-4">
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          background:     'rgba(255,255,255,0.04)',
          border:         '1px solid rgba(255,255,255,0.08)',
          backdropFilter: 'blur(20px)',
          boxShadow:      '0 8px 32px rgba(0,0,0,0.36)',
        }}
      >
        <div className="flex items-center gap-3 px-4 py-3">
          <input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
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
            aria-label={isListening ? 'Stop listening' : 'Start voice input'}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
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
      </div>
    </div>
  );
}

// ── WorkspaceSurface ──────────────────────────────────────────────────────────
const WorkspaceSurface = () => {
  const { showChat, setShowChat, addMessage, setIsThinking, setActiveNode } =
    useConversationStore();
  const { setOrbState } = useOrbStore();

  const handleNodeClick = useCallback(
    (id: string) => {
      setActiveNode(id);
      setShowChat(true);
      setIsThinking(true);
      setOrbState('thinking');
      setTimeout(() => {
        addMessage({
          id: Date.now().toString(),
          text: `Opening ${id.charAt(0).toUpperCase() + id.slice(1)} workspace. This module is ready — how would you like to begin?`,
          sender: 'ai',
          timestamp: new Date(),
        });
        setIsThinking(false);
        setOrbState('idle');
      }, 800);
    },
    [setActiveNode, setShowChat, setIsThinking, setOrbState, addMessage],
  );

  return (
    <div className="relative flex-1 flex flex-col min-h-0 overflow-hidden">
      <AnimatePresence mode="wait">
        {!showChat ? (
          /* ── Landing: Orb + Orbital Nodes ── */
          <motion.div
            key="landing"
            className="flex-1 flex flex-col items-center justify-center relative overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.35 }}
            style={{ minHeight: 0 }}
          >
            {/* Subtle grid overlay */}
            <div className="absolute inset-0 zaram-grid-bg" />

            {/* Orbital system */}
            <div
              className="relative flex items-center justify-center"
              style={{
                width:  `min(${ORBIT_CONTAINER}px, min(88vw, 78vh))`,
                height: `min(${ORBIT_CONTAINER}px, min(88vw, 78vh))`,
              }}
            >
              {/* Orbit track rings */}
              <div
                className="absolute rounded-full pointer-events-none"
                style={{
                  width:  ORBIT_RADIUS * 2 + 60,
                  height: ORBIT_RADIUS * 2 + 60,
                  border: '1px solid rgba(255,255,255,0.04)',
                }}
              />
              <div
                className="absolute rounded-full pointer-events-none"
                style={{
                  width:  ORBIT_RADIUS * 2 + 110,
                  height: ORBIT_RADIUS * 2 + 110,
                  border: '1px solid rgba(255,255,255,0.025)',
                }}
              />

              {/* Orbiting nodes */}
              {ORBITAL_NODES.map((node) => (
                <OrbitalNodeItem
                  key={node.id}
                  node={node}
                  radius={ORBIT_RADIUS}
                  onClick={handleNodeClick}
                />
              ))}

              {/* Central Living Orb — reads orbStore internally */}
              <div className="relative z-10">
                <LivingOrb />
              </div>
            </div>

            {/* Tagline */}
            <motion.p
              className="text-center text-slate-500 text-xs tracking-widest uppercase mt-3 mb-2"
              style={{ letterSpacing: '0.12em' }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              Living Intelligence · Local First
            </motion.p>

            {/* Input bar on landing page */}
            <LandingInputBar />
          </motion.div>
        ) : (
          /* ── Chat workspace ── */
          <motion.div
            key="chat"
            className="flex-1 flex flex-col min-h-0"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ChatInterface />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default WorkspaceSurface;
