import React, { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Mic, MicOff, Send, Chrome, Music, Settings, User, MessageSquare } from 'lucide-react';
import exampleImage from 'figma:asset/ef6432358e70cd07cef418bda499a8b4438f8bd9.png';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

export function HolographicAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [recognition, setRecognition] = useState<SpeechRecognition | null>(null);
  const [speechSynthesis, setSpeechSynthesis] = useState<SpeechSynthesis | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize speech recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();
      recognitionInstance.continuous = false;
      recognitionInstance.interimResults = false;
      recognitionInstance.lang = 'en-US';

      recognitionInstance.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        setIsListening(false);
      };

      recognitionInstance.onerror = () => {
        setIsListening(false);
      };

      recognitionInstance.onend = () => {
        setIsListening(false);
      };

      setRecognition(recognitionInstance);
    }

    // Initialize speech synthesis
    if ('speechSynthesis' in window) {
      setSpeechSynthesis(window.speechSynthesis);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const generateAIResponse = (userMessage: string): string => {
    const lowerMessage = userMessage.toLowerCase();
    
    if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
      return "Hello! I'm Aarav AI, your personal assistant. How can I help you today?";
    } else if (lowerMessage.includes('weather')) {
      return "I'd love to help with weather information! Let me get that for you.";
    } else if (lowerMessage.includes('time')) {
      return `The current time is ${new Date().toLocaleTimeString()}.`;
    } else if (lowerMessage.includes('music') || lowerMessage.includes('play')) {
      return "I can help you play music! What would you like to listen to?";
    } else if (lowerMessage.includes('chrome') || lowerMessage.includes('browser')) {
      return "I can help you open Chrome or navigate to websites. What would you like to browse?";
    } else {
      return "I'm here to assist you with various tasks. Feel free to ask me anything or use the action buttons!";
    }
  };

  const handleSendMessage = () => {
    if (!inputText.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setShowChat(true);

    // Generate AI response
    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        text: generateAIResponse(inputText),
        sender: 'ai',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiResponse]);
    }, 1000);

    setInputText('');
  };

  const handleVoiceInput = () => {
    if (!recognition) {
      alert('Speech recognition is not supported in your browser.');
      return;
    }

    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      recognition.start();
      setIsListening(true);
    }
  };

  const handleSpeak = (text: string) => {
    if (!speechSynthesis) {
      alert('Speech synthesis is not supported in your browser.');
      return;
    }

    if (isSpeaking) {
      speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.8;
    utterance.pitch = 1;
    
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    speechSynthesis.speak(utterance);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleActionClick = (action: string) => {
    const actionMessage: Message = {
      id: Date.now().toString(),
      text: `${action} activated`,
      sender: 'ai',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, actionMessage]);
    setShowChat(true);
  };

  return (
    <div className="flex h-screen bg-slate-900 text-white">
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Central Content */}
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-8">
          {!showChat ? (
            <>
              {/* Holographic Bubble */}
              <div className="relative">
                <img 
                  src={exampleImage} 
                  alt="Holographic AI"
                  className="w-48 h-48 object-contain"
                />
                {(isListening || isSpeaking) && (
                  <div className="absolute inset-0 rounded-full border-4 border-blue-400 animate-pulse"></div>
                )}
              </div>

              {/* Welcome Text */}
              <div className="text-center space-y-2">
                <h1 className="text-4xl text-white">Welcome, Papa</h1>
                <p className="text-xl text-gray-300">Hi, I'm Aarav AI</p>
                <p className="text-lg text-gray-400">Your Personal Assistant</p>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-3 gap-4 max-w-md">
                <Button
                  onClick={() => handleActionClick("Opening Chrome")}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-full"
                >
                  <Chrome className="w-4 h-4 mr-2" />
                  Open Chrome
                </Button>
                <Button
                  onClick={() => handleActionClick("Playing Music")}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-full"
                >
                  <Music className="w-4 h-4 mr-2" />
                  Play Music
                </Button>
                <Button
                  onClick={() => handleActionClick("Example activated")}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-full"
                >
                  Example
                </Button>
                <Button
                  onClick={() => handleActionClick("Feature activated")}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-3 rounded-full col-span-3"
                >
                  Additional Feature
                </Button>
                <Button
                  onClick={() => setShowChat(true)}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-full col-span-3"
                >
                  <MessageSquare className="w-4 h-4 mr-2" />
                  Start Chat
                </Button>
              </div>
            </>
          ) : (
            /* Chat Interface */
            <div className="w-full max-w-4xl h-full flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <Button
                  onClick={() => setShowChat(false)}
                  variant="ghost"
                  className="text-white hover:bg-gray-700"
                >
                  ← Back to Main
                </Button>
                <div className="flex items-center gap-2">
                  <img 
                    src={exampleImage} 
                    alt="AI"
                    className="w-8 h-8 object-contain"
                  />
                  <span>Aarav AI</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto mb-4 space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[70%] p-4 rounded-2xl ${
                      message.sender === 'user' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-700 text-white'
                    }`}>
                      <p>{message.text}</p>
                      <p className="text-xs opacity-70 mt-1">
                        {message.timestamp.toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </div>

        {/* Chat Input - Always at bottom */}
        <div className="p-6 border-t border-gray-700">
          <div className="flex gap-3 max-w-4xl mx-auto">
            <div className="flex-1 relative">
              <Input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Chat input"
                className="bg-gray-800 border-gray-600 text-white placeholder:text-gray-400 pr-12 rounded-full"
              />
              <Button
                variant="ghost"
                size="sm"
                className={`absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 p-0 ${
                  isListening ? 'text-red-400' : 'text-gray-400'
                }`}
                onClick={handleVoiceInput}
              >
                {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
            </div>
            <Button 
              onClick={handleSendMessage} 
              disabled={!inputText.trim()}
              className="bg-blue-600 hover:bg-blue-500 rounded-full"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          
          {isListening && (
            <div className="mt-3 text-center">
              <p className="text-sm text-blue-400 animate-pulse">
                Listening... Speak now
              </p>
            </div>
          )}
          
          {isSpeaking && (
            <div className="mt-3 text-center">
              <p className="text-sm text-blue-400 animate-pulse">
                Speaking...
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-64 bg-gray-800 border-l border-gray-700 p-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-gray-400 text-sm">Quick Actions</p>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              Example
            </Button>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              Example
            </Button>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              Example
            </Button>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              Example
            </Button>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              Example
            </Button>
          </div>

          <div className="pt-8 space-y-2">
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              <Settings className="w-4 h-4 mr-2" />
              setting
            </Button>
            <Button variant="ghost" className="w-full justify-start text-white hover:bg-gray-700">
              <User className="w-4 h-4 mr-2" />
              profile
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}