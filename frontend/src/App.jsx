import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, Brain, Database, Settings, User, 
  Activity, Cpu, Code, Mic, Paperclip, Monitor, Terminal, 
  HardDrive, Zap, Rocket, BookOpen, Check
} from 'lucide-react';
import { LivingOrb } from './components/LivingOrb/LivingOrb';
import { useOrbState } from './components/LivingOrb/useOrbState';
import { ActionButton } from './components/ActionButton';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Zaram OS initialized. Systems online. How can I assist you?' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [personalities, setPersonalities] = useState({});
  const [activePersonality, setActivePersonality] = useState('af_alexis');
  const [hasInteracted, setHasInteracted] = useState(false);
  
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);
  const abortControllerRef = useRef(null);
  
  const { state, setState, getColors } = useOrbState();
  const colors = getColors();

  useEffect(() => {
    fetch('http://127.0.0.1:8000/personalities')
      .then(res => res.json())
      .then(data => setPersonalities(data.personalities))
      .catch(err => console.error("Failed to load personalities", err));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && (state === 'speaking' || state === 'thinking')) {
        stopAll();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state]);

  const stopAll = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.onended = null;
    }
    setIsLoading(false);
    setState('idle');
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userText = input.trim();
    setInput('');
    
    if (!hasInteracted) {
      setHasInteracted(true);
    }
    
    stopAll();
    
    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    setState('thinking');
    setIsLoading(true);

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: userText, 
          model: 'gemma3:latest',
          personality: activePersonality
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) throw new Error('Backend connection failed');
      const data = await response.json();
      
      setIsLoading(false);
      
      setMessages(prev => [...prev, { role: 'assistant', content: data.text }]);
      
      setState('speaking');

      if (data.audio_url && audioRef.current) {
        audioRef.current.src = data.audio_url;
        audioRef.current.onended = () => {
          setState('idle');
        };
        audioRef.current.onerror = () => {
          setState('idle');
        };
        await audioRef.current.play();
      } else {
        setTimeout(() => setState('idle'), 1000);
      }

    } catch (error) {
      if (error.name !== 'AbortError') {
        setIsLoading(false);
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `⚠️ Error: ${error.message}. Ensure backend is running.` 
        }]);
        setState('error');
        setTimeout(() => setState('idle'), 3000);
      }
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    if ((state === 'speaking' || state === 'thinking') && e.target.value.length > 0) {
      stopAll();
    }
  };

  const currentName = personalities[activePersonality]?.name || 'Alexis';
  const currentInitial = currentName.charAt(0).toUpperCase();

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#050810] text-slate-200 transition-colors duration-1000">
      
      <audio ref={audioRef} className="hidden" />

      {/* LEFT SIDEBAR */}
      <div className="w-64 flex flex-col bg-[#0a0f1c] border-r transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
        <div className="p-6 border-b border-white/5">
          <h1 className="text-2xl font-bold text-white tracking-wider">ZARAM</h1>
          <p className="text-[10px] mt-1 uppercase tracking-widest transition-colors duration-700" style={{ color: colors.secondary }}>Unified Voice OS</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {[
            { icon: Activity, label: 'Orchestration', active: true },
            { icon: MessageSquare, label: 'Chat', active: false },
            { icon: Brain, label: 'Models', active: false },
            { icon: Database, label: 'Knowledge', active: false },
            { icon: HardDrive, label: 'Memory', active: false },
            { icon: Code, label: 'Tools', active: false },
            { icon: Settings, label: 'Settings', active: false },
          ].map((item, i) => (
            <button 
              key={i} 
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-500 ${
                item.active 
                  ? 'bg-white/5 border' 
                  : 'text-slate-400 hover:bg-white/5 hover:text-white border border-transparent'
              }`}
              style={item.active ? { borderColor: colors.primary, color: colors.primary } : {}}
            >
              <item.icon size={18} />
              <span className="text-sm font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3">
            <div 
              className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-white transition-all duration-700" 
              style={{ background: `linear-gradient(135deg, ${colors.primary}, ${colors.secondary})` }}
            >
              {currentInitial}
            </div>
            <div>
              <div className="text-sm font-semibold text-white tracking-wide">
                {currentName.toUpperCase()}
              </div>
              <div className="text-[10px] text-green-400 flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                Online
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CENTER AREA */}
      <div className="flex-1 flex flex-col relative">
        <div className="h-12 flex items-center justify-between px-6 border-b border-white/5 bg-black/20">
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-slate-500">ZARAM OS</span>
            <span className="text-slate-700">|</span>
            <span className="font-bold transition-colors duration-700" style={{ color: colors.primary }}>STATE: {state.toUpperCase()}</span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-500">VOICE: {currentName}</span>
          </div>
        </div>

        {/* Orb Background - ANIMATED SIZE AND OPACITY */}
        <motion.div 
          className="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ 
            scale: hasInteracted ? 1 : 0.5, 
            opacity: hasInteracted ? 1 : 0.3 
          }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        >
          <LivingOrb />
        </motion.div>

        {/* Chat History Overlay */}
        <motion.div 
          className="relative z-10 flex-1 flex flex-col items-center p-8 pointer-events-none"
          initial={{ y: 0 }}
          animate={{ y: hasInteracted ? 0 : -100 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <div className="w-full max-w-3xl h-[400px] flex flex-col pointer-events-auto">
            <div className="flex-1 overflow-y-auto space-y-4 p-4">
              <AnimatePresence>
                {messages.map((msg, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div 
                      className={`max-w-[80%] p-4 rounded-2xl backdrop-blur-md border transition-all duration-700 ${
                        msg.role === 'user' 
                          ? 'bg-white/5 border-white/10 text-white' 
                          : 'bg-black/40 text-slate-200'
                      }`}
                      style={msg.role === 'assistant' ? { borderColor: `${colors.primary}40`, boxShadow: `0 0 20px ${colors.glow}` } : {}}
                    >
                      <p className="text-sm leading-relaxed">{msg.content}</p>
                    </div>
                  </motion.div>
                ))}
                
                {/* Loading Dots */}
                {isLoading && (
                  <motion.div 
                    key="loading-dots"
                    initial={{ opacity: 0, scale: 0.8 }} 
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.2 }}
                    className="flex justify-start"
                  >
                    <div className="p-4 rounded-2xl bg-black/40 border border-white/10 flex gap-2" style={{ borderColor: `${colors.primary}40` }}>
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.primary }}></div>
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.secondary, animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.primary, animationDelay: '0.2s' }}></div>
                    </div>
                  </motion.div>
                )}
                
                <div ref={messagesEndRef} />
              </AnimatePresence>
            </div>
          </div>
        </motion.div>

        {/* Input Area - STARTS CENTERED ON BOTH X AND Y AXIS */}
        <div className="absolute left-1/2 -translate-x-1/2 w-[600px] z-20">
          <motion.div
            initial={{ top: '50%', y: '-50%' }}
            animate={{ 
              top: hasInteracted ? 'auto' : '50%',
              bottom: hasInteracted ? '2.5rem' : 'auto',
              y: hasInteracted ? 0 : '-50%'
            }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <div className="glass-panel p-2 flex items-center gap-2 rounded-full border transition-colors duration-700" style={{ borderColor: `${colors.primary}30` }}>
              <button className="p-3 text-slate-400 hover:text-white transition-colors"><Paperclip size={18} /></button>
              <input
                type="text"
                value={input}
                onChange={handleInputChange}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask Zaram anything..."
                className="flex-1 bg-transparent outline-none text-sm text-white placeholder-slate-500 px-2"
              />
              <button className="p-3 text-slate-400 hover:text-white transition-colors"><Mic size={18} /></button>
              
              <ActionButton 
                onSend={sendMessage} 
                onStop={stopAll} 
                onMic={() => setState('listening')} 
                isInputEmpty={!input.trim()} 
              />
            </div>
          </motion.div>
        </div>
      </div>

      {/* RIGHT PANELS */}
      <div className="w-[400px] flex flex-col gap-4 p-4 overflow-y-auto border-l bg-[#0a0f1c]/50 transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
        
        <div className="glass-panel p-5 border transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-bold text-white tracking-widest">AI PERSONALITIES</h3>
            <User size={14} className="text-slate-500" />
          </div>
          <div className="space-y-2">
            {Object.entries(personalities).map(([id, p]) => (
              <button
                key={id}
                onClick={() => setActivePersonality(id)}
                className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all duration-300 ${
                  activePersonality === id 
                    ? 'bg-white/10 border-white/30' 
                    : 'bg-transparent border-transparent hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${p.gender === 'female' ? 'bg-pink-400' : 'bg-blue-400'}`}></div>
                  <div className="text-left">
                    <div className="text-sm font-medium text-white">{p.name}</div>
                    <div className="text-[10px] text-slate-500">{p.description}</div>
                  </div>
                </div>
                {activePersonality === id && <Check size={16} className={colors.primary} />}
              </button>
            ))}
          </div>
        </div>

        <div className="glass-panel p-5 border transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-bold text-white tracking-widest">ORCHESTRATION</h3>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: colors.primary }}></div>
              <span className="text-[10px] font-mono transition-colors duration-700" style={{ color: colors.primary }}>ACTIVE</span>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Active Model</span>
              <span className="font-mono transition-colors duration-700" style={{ color: colors.secondary }}>Gemma 3</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">AI State</span>
              <span className="font-mono transition-colors duration-700" style={{ color: colors.primary }}>{state.toUpperCase()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;