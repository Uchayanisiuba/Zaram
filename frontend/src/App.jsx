import { useState } from 'react';
import { ZaramProvider } from './context/ZaramContext';
import { useZaram } from './hooks/useZaram';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { Chat } from './components/chat/Chat';
import { Memory } from './components/memory/Memory';
import { Knowledge } from './components/knowledge/Knowledge';
import { Settings } from './components/settings/Settings';

const AppContent = () => {
  const { activeTab, showSettings } = useZaram();

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Animated Background Gradient */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent pointer-events-none" />

      {/* Header */}
      <Header />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Sidebar */}
        <Sidebar />

        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden">
          {showSettings ? (
            <div className="flex-1 overflow-auto">
              <Settings />
            </div>
          ) : (
            <>
              {/* Chat */}
              {activeTab === 'chat' && <Chat />}

              {/* Memory */}
              {activeTab === 'memory' && (
                <div className="flex-1 overflow-auto">
                  <Memory />
                </div>
              )}

              {/* Knowledge */}
              {activeTab === 'knowledge' && (
                <div className="flex-1 overflow-auto">
                  <Knowledge />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <ZaramProvider>
      <AppContent />
    </ZaramProvider>
  );
}

// OLD CODE BELOW - TO BE REMOVED
function LegacyApp() {
  // State Management
  const [isFirstInteraction, setIsFirstInteraction] = useState(true);
  const [isSandboxOpen, setIsSandboxOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [selectedModel, setSelectedModel] = useState('auto');
  const [selectedCharacter, setSelectedCharacter] = useState('zaram_prime');
  const [isLoading, setIsLoading] = useState(false);
  const [sandboxContent, setSandboxContent] = useState('// Double-click any message to inspect in sandbox...');
  const [fileBadgeName, setFileBadgeName] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [orbRevealed, setOrbRevealed] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Refs
  const audioRef = useRef(null);
  const chatAreaRef = useRef(null);
  const fileInputRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll effect
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Handlers
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeQuery();
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    setFileBadgeName(file ? file.name : '');
  };

  const toggleSandbox = (content = null) => {
    if (content) {
      setSandboxContent(content);
      setIsSandboxOpen(true);
    } else {
      setIsSandboxOpen(!isSandboxOpen);
    }
  };

  const executeQuery = async () => {
    if (!inputText.trim()) return;

    const userMsg = inputText.trim();
    if (audioRef.current) audioRef.current.pause();

    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }]);
    setInputText('');
    setIsLoading(true);

    if (isFirstInteraction) {
      setIsFirstInteraction(false);
      setOrbRevealed(true);
    }

    const payload = {
      text: userMsg,
      character_id: selectedCharacter,
      brain_id: selectedModel,
      filename: fileInputRef.current?.files[0]?.name || null
    };

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.text || "Pipeline synced.",
        character: selectedCharacter,
        model: data.model_used || selectedModel,
        timestamp: new Date()
      }]);

      if (data.audio_url && audioRef.current) {
        audioRef.current.src = `http://127.0.0.1:8000${data.audio_url}`;
        await audioRef.current.play();
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: "Connection failed. Ensure backend is running on port 8000.",
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
      setFileBadgeName('');
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const clearChat = () => {
    setMessages([]);
    setIsFirstInteraction(true);
    setOrbRevealed(false);
  };

  const newSession = () => {
    if (confirm('Start a new session? Current chat will be cleared.')) {
      clearChat();
    }
  };

  return (
    <div className="h-screen flex bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100 overflow-hidden">
      {/* Animated Background Gradient */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent pointer-events-none" />
      
      {/* Left Sidebar */}
      <aside className={`${sidebarCollapsed ? 'w-20' : 'w-80'} transition-all duration-300 ease-in-out flex flex-col bg-slate-950/80 backdrop-blur-xl border-r border-cyan-950/30 z-50`}>
        {/* Logo Area */}
        <div className="p-6 border-b border-cyan-950/30 flex items-center justify-between">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-cyan-500/30">
                ZR
              </div>
              <div>
                <div className="font-bold text-sm tracking-wider">ZARAM</div>
                <div className="text-[10px] text-cyan-400/70 uppercase tracking-widest">Engine v2.0</div>
              </div>
            </div>
          )}
          <button 
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 hover:bg-cyan-950/30 rounded-lg transition-colors text-cyan-400"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sidebarCollapsed ? "M13 5l7 7-7 7M5 5l7 7-7 7" : "M11 19l-7-7 7-7m8 14l-7-7 7-7"} />
            </svg>
          </button>
        </div>

        {!sidebarCollapsed && (
          <>
            {/* New Session Button */}
            <div className="p-4">
              <button 
                onClick={newSession}
                className="w-full py-3 px-4 bg-gradient-to-r from-cyan-600/20 to-blue-600/20 hover:from-cyan-600/40 hover:to-blue-600/40 border border-cyan-500/30 rounded-xl text-sm font-semibold text-cyan-300 transition-all flex items-center justify-center gap-2 group"
              >
                <span className="text-lg group-hover:rotate-90 transition-transform">+</span>
                New Session
              </button>
            </div>

            {/* Recent Sessions */}
            <div className="flex-1 overflow-y-auto px-4 py-2">
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 px-2">Recent Sessions</div>
              <div className="space-y-1">
                {['MetaHuman ARKit Optimization', 'Zaram AI Roadmap', 'Neural Network Design'].map((session, i) => (
                  <div key={i} className="p-3 hover:bg-cyan-950/20 rounded-lg cursor-pointer transition-all text-sm text-slate-400 hover:text-cyan-300 truncate group">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/50 group-hover:bg-cyan-400" />
                      {session}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Controls */}
            <div className="p-4 border-t border-cyan-950/30 space-y-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block">AI Model</label>
                <select 
                  value={selectedModel} 
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full bg-slate-900/80 text-xs text-slate-300 p-3 rounded-xl border border-cyan-900/40 outline-none focus:border-cyan-500/50 transition-colors"
                >
                  <option value="auto">Auto-Route (Smart)</option>
                  <option value="qwen3:latest">Qwen3 (Coding)</option>
                  <option value="gemma3:latest">Gemma3 (Logic)</option>
                  <option value="moondream:latest">Moondream (Vision)</option>
                  <option value="llama3.2:latest">Llama3.2 (Chat)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block">Voice Persona</label>
                <select 
                  value={selectedCharacter} 
                  onChange={(e) => setSelectedCharacter(e.target.value)}
                  className="w-full bg-slate-900/80 text-xs text-slate-300 p-3 rounded-xl border border-cyan-900/40 outline-none focus:border-cyan-500/50 transition-colors"
                >
                  <optgroup label="Female">
                    <option value="zaram_prime">Zaram Prime</option>
                    <option value="nova_hacker">Nova Core</option>
                  </optgroup>
                  <optgroup label="Male">
                    <option value="baba_elder">Elder Baba</option>
                    <option value="michael_tech">Michael Tech</option>
                  </optgroup>
                </select>
              </div>

              {/* User Profile */}
              <div className="flex items-center gap-3 pt-3 border-t border-cyan-950/30">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-600/30 to-blue-700/30 flex items-center justify-center font-bold text-cyan-400 text-xs border border-cyan-500/30">
                  AU
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-xs text-slate-200 truncate">Anisiuba Uche</div>
                  <div className="text-[9px] text-cyan-500/60 font-mono">● Online</div>
                </div>
              </div>
            </div>
          </>
        )}
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative z-10">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-cyan-950/20 bg-slate-950/30 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="text-xs font-mono text-cyan-600/70">// CONSOLE_ACTIVE</div>
            <div className="h-4 w-px bg-cyan-950/40" />
            <div className="text-xs text-slate-500">{messages.length} messages</div>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={clearChat}
              className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-950/20 rounded-lg transition-all"
              title="Clear Chat"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
            <button 
              onClick={toggleSandbox}
              className={`p-2 rounded-lg transition-all ${isSandboxOpen ? 'text-cyan-400 bg-cyan-950/30' : 'text-slate-500 hover:text-cyan-400'}`}
              title="Toggle Sandbox"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <div 
          ref={chatAreaRef}
          className={`flex-1 overflow-y-auto px-6 py-8 transition-all duration-700 ${isFirstInteraction ? 'flex items-center justify-center' : ''}`}
        >
          {isFirstInteraction ? (
            <div className="text-center space-y-6 max-w-2xl">
              <div className="space-y-2">
                <h1 className="text-5xl font-bold bg-gradient-to-r from-cyan-400 via-blue-500 to-cyan-400 bg-clip-text text-transparent">
                  Welcome to Zaram
                </h1>
                <p className="text-slate-400 text-lg">Your intelligent AI workspace console</p>
              </div>
              <div className="flex gap-3 justify-center flex-wrap">
                {['Explain quantum computing', 'Write a Python script', 'Analyze this data'].map((suggestion, i) => (
                  <button 
                    key={i}
                    onClick={() => { setInputText(suggestion); inputRef.current?.focus(); }}
                    className="px-4 py-2 bg-slate-800/50 hover:bg-slate-800 border border-cyan-900/30 hover:border-cyan-500/50 rounded-lg text-sm text-slate-300 transition-all"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                >
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-2' : 'order-1'}`}>
                    <div className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      {/* Avatar */}
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                        msg.role === 'user' 
                          ? 'bg-gradient-to-br from-blue-500 to-cyan-600 text-white' 
                          : msg.role === 'error'
                          ? 'bg-red-900/50 text-red-300 border border-red-700/50'
                          : 'bg-gradient-to-br from-cyan-600/30 to-blue-700/30 text-cyan-400 border border-cyan-500/30'
                      }`}>
                        {msg.role === 'user' ? 'You' : msg.role === 'error' ? '!' : 'ZR'}
                      </div>
                      
                      {/* Message Bubble */}
                      <div className={`group relative px-5 py-3.5 rounded-2xl ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-br from-blue-600 to-cyan-600 text-white shadow-lg shadow-cyan-900/20'
                          : msg.role === 'error'
                          ? 'bg-red-950/30 border border-red-900/50 text-red-200'
                          : 'bg-slate-800/50 border border-cyan-900/30 text-slate-200 backdrop-blur-sm'
                      }`}>
                        {msg.role === 'assistant' && (
                          <div className="text-[10px] text-cyan-400/70 font-mono mb-1.5 uppercase tracking-wider">
                            {msg.character.replace('_', ' ')} • {msg.model}
                          </div>
                        )}
                        <div className="text-sm leading-relaxed cursor-pointer" onDoubleClick={() => toggleSandbox(msg.content)}>
                          {msg.content}
                        </div>
                        <div className={`text-[10px] mt-2 opacity-50 ${msg.role === 'user' ? 'text-blue-100' : 'text-slate-400'}`}>
                          {msg.timestamp?.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-600/30 to-blue-700/30 flex items-center justify-center text-xs font-bold text-cyan-400 border border-cyan-500/30">
                      ZR
                    </div>
                    <div className="bg-slate-800/50 border border-cyan-900/30 px-5 py-3.5 rounded-2xl">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Cosmic Orb Overlay */}
        <div className={`fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-all duration-1000 z-0 ${orbRevealed ? 'opacity-40 scale-100' : 'opacity-0 scale-0'}`}>
          <div className={`w-64 h-64 rounded-full relative ${isSpeaking ? 'animate-pulse-slow' : ''}`}>
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-500/20 via-blue-600/20 to-cyan-400/20 blur-3xl" />
            <div className="absolute inset-4 rounded-full bg-gradient-to-br from-cyan-400/30 via-blue-500/30 to-cyan-300/30 blur-2xl" />
            <div className="absolute inset-0 rounded-full border-2 border-cyan-400/20 animate-spin-slow" />
            <div className="absolute inset-8 rounded-full border border-cyan-300/30 animate-spin-reverse" />
          </div>
        </div>

        {/* Input Area */}
        <div className="p-6 bg-gradient-to-t from-slate-950 to-transparent">
          <div className="max-w-4xl mx-auto">
            {fileBadgeName && (
              <div className="mb-3 flex items-center gap-2 text-xs text-cyan-400 bg-cyan-950/30 border border-cyan-900/50 px-3 py-1.5 rounded-lg w-fit">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
                {fileBadgeName}
                <button onClick={() => { setFileBadgeName(''); fileInputRef.current.value = ''; }} className="ml-2 hover:text-red-400">×</button>
              </div>
            )}
            
            <div className="relative bg-slate-800/50 backdrop-blur-xl border border-cyan-900/40 rounded-2xl p-2 focus-within:border-cyan-500/50 focus-within:shadow-lg focus-within:shadow-cyan-900/20 transition-all">
              <textarea
                ref={inputRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Ask Zaram anything..."
                rows="2"
                className="w-full bg-transparent border-none outline-none resize-none text-sm text-slate-200 placeholder-slate-500 px-4 py-3 min-h-[80px]"
              />
              
              <div className="flex justify-between items-center px-2 pb-2">
                <div className="flex items-center gap-2">
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={handleFileSelect}
                    className="hidden" 
                  />
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="p-2 text-slate-400 hover:text-cyan-400 hover:bg-cyan-950/30 rounded-lg transition-all"
                    title="Attach file"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94a3 3 0 114.243 4.243L8.567 17.825a1.5 1.5 0 01-2.122-2.122l8.84-8.84m-8.84 8.84l4.243-4.243" />
                    </svg>
                  </button>
                </div>
                
                <button
                  onClick={executeQuery}
                  disabled={isLoading || !inputText.trim()}
                  className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl text-sm transition-all flex items-center gap-2 shadow-lg shadow-cyan-900/30"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      Send
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                    </>
                  )}
                </button>
              </div>
            </div>
            
            <div className="text-center mt-3 text-[11px] text-slate-600">
              Zaram may produce inaccurate information. Verify important data.
            </div>
          </div>
        </div>
      </main>

      {/* Sandbox Drawer */}
      <div className={`fixed right-0 top-0 h-full bg-slate-950/95 backdrop-blur-xl border-l border-cyan-950/30 z-50 transition-all duration-500 ease-in-out ${isSandboxOpen ? 'w-[600px]' : 'w-0'} overflow-hidden`}>
        <div className="p-6 h-full flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-sm font-bold text-cyan-400 uppercase tracking-widest">Inspection Sandbox</h2>
              <p className="text-xs text-slate-500 mt-1">Analyze and copy content</p>
            </div>
            <button 
              onClick={() => setIsSandboxOpen(false)}
              className="p-2 text-slate-500 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div className="flex-1 bg-slate-900/50 border border-cyan-900/30 rounded-xl p-4 font-mono text-xs text-slate-300 overflow-y-auto">
            <pre className="whitespace-pre-wrap">{sandboxContent}</pre>
          </div>
          
          <div className="mt-4 flex gap-2">
            <button 
              onClick={() => navigator.clipboard.writeText(sandboxContent)}
              className="flex-1 py-2 bg-cyan-950/30 hover:bg-cyan-950/50 border border-cyan-900/50 text-cyan-400 rounded-lg text-xs font-semibold transition-all"
            >
              Copy to Clipboard
            </button>
          </div>
        </div>
      </div>

      {/* Audio Element */}
      <audio 
        ref={audioRef}
        onPlay={() => setIsSpeaking(true)}
        onEnded={() => setIsSpeaking(false)}
        onPause={() => setIsSpeaking(false)}
      />

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        .animate-pulse-slow {
          animation: pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        .animate-spin-slow {
          animation: spin 20s linear infinite;
        }
        .animate-spin-reverse {
          animation: spin 15s linear infinite reverse;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default App;