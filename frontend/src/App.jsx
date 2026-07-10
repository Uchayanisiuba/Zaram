import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, Brain, Database, Settings, User, 
  Activity, Cpu, Code, Mic, Paperclip, Monitor, Terminal, 
  HardDrive, Zap, Rocket, BookOpen, Check, ChevronDown
} from 'lucide-react';
import { LivingOrb } from './components/LivingOrb/LivingOrb';
import { useOrbState } from './components/LivingOrb/useOrbState';
import { ActionButton } from './components/ActionButton';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [personalities, setPersonalities] = useState({});
  // FIX: Changed default from 'af_alexis' to the real Kokoro voice 'af_heart'
  const [activePersonality, setActivePersonality] = useState('af_heart');
  const [hasInteracted, setHasInteracted] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);
  const abortControllerRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);
  const animationFrameRef = useRef(null);
  
  const { state, setState, getColors, setAudioLevel } = useOrbState();
  const colors = getColors();

  useEffect(() => {
    fetch('http://127.0.0.1:8000/personalities')
      .then(res => res.json())
      .then(data => setPersonalities(data.personalities))
      .catch(err => console.error("Failed to load personalities", err));
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [messages, isLoading]);

  const initAudioAnalysis = () => {
    if (audioContextRef.current) return;
    
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContextClass();
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      analyserRef.current.smoothingTimeConstant = 0.8;
      
      if (audioRef.current && !sourceRef.current) {
        sourceRef.current = audioContextRef.current.createMediaElementSource(audioRef.current);
        sourceRef.current.connect(analyserRef.current);
        analyserRef.current.connect(audioContextRef.current.destination);
      }
      
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      
      const analyze = () => {
        if (analyserRef.current) {
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i] * dataArray[i];
          }
          const rms = Math.sqrt(sum / dataArray.length);
          setAudioLevel(Math.min(rms / 100, 1));
        }
        animationFrameRef.current = requestAnimationFrame(analyze);
      };
      analyze();
    } catch (e) {
      console.error("Audio analysis init failed:", e);
    }
  };

  const stopAll = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.onended = null;
    }
    setIsLoading(false);
    setState('idle');
    setAudioLevel(0);
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userText = input.trim();
    setInput('');
    
    if (!hasInteracted) {
      setHasInteracted(true);
      initAudioAnalysis();
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
        const uniqueUrl = `${data.audio_url}?t=${Date.now()}`;
        audioRef.current.src = uniqueUrl;
        audioRef.current.crossOrigin = "anonymous";
        
        audioRef.current.onended = () => { 
            setState('idle'); 
            setAudioLevel(0); 
        };
        
        audioRef.current.onerror = () => { 
            setState('idle'); 
            setAudioLevel(0); 
        };
        
        await audioRef.current.play();
      } else {
        setTimeout(() => { setState('idle'); setAudioLevel(0); }, 1000);
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        setIsLoading(false);
        setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ Error: ${error.message}. Ensure backend is running.` }]);
        setState('error');
        setAudioLevel(0);
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
      <audio ref={audioRef} className="hidden" crossOrigin="anonymous" />

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
            { icon: Settings, label: 'Settings', active: false }
          ].map((item, i) => (
            <button key={i} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-500 ${item.active ? 'bg-white/5 border' : 'text-slate-400 hover:bg-white/5 hover:text-white border border-transparent'}`} style={item.active ? { borderColor: colors.primary, color: colors.primary } : {}}>
              <item.icon size={18} />
              <span className="text-sm font-medium">{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-white transition-all duration-700" style={{ background: `linear-gradient(135deg, ${colors.primary}, ${colors.secondary})` }}>
              {currentInitial}
            </div>
            <div>
              <div className="text-sm font-semibold text-white tracking-wide">{currentName.toUpperCase()}</div>
              <div className="text-[10px] text-green-400 flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div> Online
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CENTER AREA */}
      <div className="flex-1 flex flex-col relative overflow-hidden">
        <div className="h-12 flex items-center justify-between px-6 border-b border-white/5 bg-black/20 z-30">
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-slate-500">ZARAM OS</span>
            <span className="text-slate-700">|</span>
            <span className="font-bold transition-colors duration-700" style={{ color: colors.primary }}>STATE: {state.toUpperCase()}</span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-500">VOICE: {currentName}</span>
          </div>
        </div>

        {/* Orb Background */}
        <motion.div 
          className="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
          style={{ margin: '-100px' }}
          initial={{ scale: 0.3, opacity: 0 }}
          animate={{ scale: hasInteracted ? 1 : 0.3, opacity: hasInteracted ? 1 : 0 }}
          transition={{ duration: 1.5 }}
        >
          <LivingOrb />
        </motion.div>

        {/* Chat Messages */}
        <div className="absolute inset-0 top-12 flex items-center justify-center pointer-events-none z-10">
          <div className="w-full max-w-4xl h-full flex flex-col justify-center pointer-events-auto">
            <div className="flex-1 overflow-y-auto px-4 py-8 space-y-4">
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div 
                    className={`max-w-[80%] p-4 rounded-2xl backdrop-blur-md border transition-all duration-700 ${
                      msg.role === 'user' ? 'bg-white/5 border-white/10' : 'bg-black/40'
                    }`}
                    style={msg.role === 'assistant' ? { borderColor: `${colors.primary}40`, boxShadow: `0 0 20px ${colors.glow}` } : {}}
                  >
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                  </div>
                </motion.div>
              ))}
              
              {isLoading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                  <div className="p-4 rounded-2xl bg-black/40 border border-white/10 flex gap-2" style={{ borderColor: `${colors.primary}40` }}>
                    <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.primary }}></div>
                    <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.secondary, animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: colors.primary, animationDelay: '0.2s' }}></div>
                  </div>
                </motion.div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>

        {/* Input Box */}
        <motion.div
          className="absolute left-1/2 -translate-x-1/2 w-[600px] z-20"
          initial={{ top: '50vh' }}
          animate={{ 
            top: hasInteracted ? 'auto' : '50vh',
            bottom: hasInteracted ? '2rem' : 'auto'
          }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <div className="glass-panel p-2 flex items-center gap-2 rounded-full border backdrop-blur-md mx-4 transition-colors duration-700" style={{ borderColor: `${colors.primary}30`, background: 'rgba(0,0,0,0.4)' }}>
            <button className="p-3 text-slate-400 hover:text-white transition-colors" type="button"><Paperclip size={18} /></button>
            <input
              type="text"
              value={input}
              onChange={handleInputChange}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Ask Zaram anything..."
              className="flex-1 bg-transparent outline-none text-sm text-white px-2"
            />
            <button className="p-3 text-slate-400 hover:text-white transition-colors" type="button"><Mic size={18} /></button>
            <ActionButton onSend={sendMessage} onStop={stopAll} onMic={() => setState('listening')} isInputEmpty={!input.trim()} />
          </div>
        </motion.div>
      </div>

      {/* RIGHT PANEL */}
      <div className="w-[400px] flex flex-col gap-4 p-4 border-l bg-[#0a0f1c]/50 transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
        
        {/* AI Personalities Dropdown */}
        <div className="glass-panel p-5 border transition-colors duration-700 relative z-40" style={{ borderColor: `${colors.primary}20` }}>
          <h3 className="text-xs font-bold text-white mb-4">AI PERSONALITIES</h3>
          
          <div className="relative">
            <button 
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="w-full flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${personalities[activePersonality]?.gender === 'female' ? 'bg-pink-400' : 'bg-blue-400'}`} />
                <div className="text-left">
                  <div className="text-sm text-white font-medium">{personalities[activePersonality]?.name || 'Select...'}</div>
                  <div className="text-[10px] text-slate-500 truncate max-w-[200px]">{personalities[activePersonality]?.description}</div>
                </div>
              </div>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-[#0a0f1c] border border-white/10 rounded-lg shadow-2xl z-50 max-h-[300px] overflow-y-auto">
                {Object.entries(personalities).map(([id, p]) => (
                  <button
                    key={id}
                    onClick={() => {
                      setActivePersonality(id);
                      setIsDropdownOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 p-3 text-left hover:bg-white/5 transition-colors ${activePersonality === id ? 'bg-white/10' : ''}`}
                  >
                    <div className={`w-2 h-2 rounded-full ${p.gender === 'female' ? 'bg-pink-400' : 'bg-blue-400'}`} />
                    <div className="flex-1">
                      <div className="text-sm text-white">{p.name}</div>
                      <div className="text-[10px] text-slate-500">{p.description}</div>
                    </div>
                    {activePersonality === id && <Check size={14} className="text-blue-400" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel p-5 border transition-colors duration-700" style={{ borderColor: `${colors.primary}20` }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-bold text-white">ORCHESTRATION</h3>
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