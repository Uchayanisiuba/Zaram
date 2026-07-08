import { createContext, useState, useCallback, useRef, useEffect } from 'react';

export const ZaramContext = createContext();

export const ZaramProvider = ({ children }) => {
  // Chat State
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Persona State
  const [selectedCharacter, setSelectedCharacter] = useState('zaram_prime');
  const [selectedModel, setSelectedModel] = useState('auto');

  // UI State
  const [activeTab, setActiveTab] = useState('chat'); // chat, memory, knowledge, settings
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Memory State
  const [memories, setMemories] = useState([]);
  const [selectedMemory, setSelectedMemory] = useState(null);

  // Knowledge State
  const [knowledgeItems, setKnowledgeItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Audio State
  const audioRef = useRef(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Conversation Meta
  const [sessionId] = useState(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const [totalProcessingTime, setTotalProcessingTime] = useState(0);

  // Messages Management
  const addMessage = useCallback((message) => {
    setMessages(prev => [...prev, {
      id: `msg_${Date.now()}_${Math.random()}`,
      timestamp: new Date(),
      ...message
    }]);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const updateLastMessage = useCallback((updates) => {
    setMessages(prev => {
      const updated = [...prev];
      if (updated.length > 0) {
        updated[updated.length - 1] = { ...updated[updated.length - 1], ...updates };
      }
      return updated;
    });
  }, []);

  // Memory Management
  const addMemory = useCallback((memory) => {
    const newMemory = {
      id: `mem_${Date.now()}`,
      createdAt: new Date(),
      importance: 'medium',
      ...memory
    };
    setMemories(prev => [newMemory, ...prev]);
    return newMemory;
  }, []);

  const deleteMemory = useCallback((memoryId) => {
    setMemories(prev => prev.filter(m => m.id !== memoryId));
  }, []);

  const updateMemory = useCallback((memoryId, updates) => {
    setMemories(prev => prev.map(m => m.id === memoryId ? { ...m, ...updates } : m));
  }, []);

  const exportMemories = useCallback(() => {
    const data = JSON.stringify(memories, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zaram_memories_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [memories]);

  // Knowledge Management
  const addKnowledgeItem = useCallback((item) => {
    const newItem = {
      id: `know_${Date.now()}`,
      uploadedAt: new Date(),
      ...item
    };
    setKnowledgeItems(prev => [newItem, ...prev]);
    return newItem;
  }, []);

  const deleteKnowledgeItem = useCallback((itemId) => {
    setKnowledgeItems(prev => prev.filter(k => k.id !== itemId));
  }, []);

  const searchKnowledge = useCallback(async (query) => {
    if (!query.trim()) {
      setSearchQuery('');
      return;
    }
    
    setSearchQuery(query);
    setIsSearching(true);
    
    try {
      // This will be replaced with actual semantic search API call
      await new Promise(resolve => setTimeout(resolve, 500));
      // Results will be filtered by searchQuery in component
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Audio Management
  const playAudio = useCallback(async (audioUrl) => {
    if (!audioRef.current) return;
    
    try {
      setIsSpeaking(true);
      audioRef.current.src = audioUrl;
      await audioRef.current.play();
    } catch (error) {
      console.error('Audio playback failed:', error);
      setIsSpeaking(false);
    }
  }, []);

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsSpeaking(false);
  }, []);

  // Setup audio event listeners
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleEnded = () => setIsSpeaking(false);
    audio.addEventListener('ended', handleEnded);
    
    return () => audio.removeEventListener('ended', handleEnded);
  }, []);

  const value = {
    // Chat
    messages,
    addMessage,
    clearMessages,
    updateLastMessage,
    inputText,
    setInputText,
    isLoading,
    setIsLoading,

    // Persona
    selectedCharacter,
    setSelectedCharacter,
    selectedModel,
    setSelectedModel,

    // UI
    activeTab,
    setActiveTab,
    sidebarCollapsed,
    setSidebarCollapsed,
    showSettings,
    setShowSettings,

    // Memory
    memories,
    addMemory,
    deleteMemory,
    updateMemory,
    exportMemories,
    selectedMemory,
    setSelectedMemory,

    // Knowledge
    knowledgeItems,
    addKnowledgeItem,
    deleteKnowledgeItem,
    searchKnowledge,
    searchQuery,
    isSearching,

    // Audio
    audioRef,
    playAudio,
    stopAudio,
    isSpeaking,

    // Session
    sessionId,
    totalProcessingTime,
    setTotalProcessingTime,
  };

  return (
    <ZaramContext.Provider value={value}>
      {children}
    </ZaramContext.Provider>
  );
};
