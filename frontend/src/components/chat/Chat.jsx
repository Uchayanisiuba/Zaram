import { useRef, useEffect, useState } from 'react';
import { useZaram } from '../../hooks/useZaram';
import { zaramAPI } from '../../services/api';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';

export const Chat = () => {
  const {
    messages,
    addMessage,
    setInputText,
    isLoading,
    setIsLoading,
    selectedCharacter,
    selectedModel,
    playAudio,
    setTotalProcessingTime,
    audioRef,
  } = useZaram();

  const chatEndRef = useRef(null);
  const [error, setError] = useState(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (text, file) => {
    if (!text.trim()) return;

    setError(null);
    addMessage({
      role: 'user',
      content: text,
      file: file?.name || null,
    });

    setInputText('');
    setIsLoading(true);

    try {
      const response = await zaramAPI.sendMessage(text, selectedCharacter, selectedModel);

      if (!response.status || response.status !== 'success') {
        throw new Error(response.message || 'Failed to get response');
      }

      addMessage({
        role: 'assistant',
        content: response.text || response.response,
        character: selectedCharacter,
        model: response.model_used,
        audioUrl: response.audio_url ? zaramAPI.getAudioUrl(response.audio_url.replace('/audio/', '')) : null,
        processingTime: response.processing_time,
      });

      // Play audio if available
      if (response.audio_url) {
        const fullUrl = response.audio_url.startsWith('http') 
          ? response.audio_url 
          : `${zaramAPI.constructor.prototype.getAudioUrl('').replace('/audio/', '')}${response.audio_url}`;
        
        setTimeout(() => {
          playAudio(fullUrl);
        }, 200);
      }

      if (response.processing_time) {
        setTotalProcessingTime(prev => prev + response.processing_time);
      }

    } catch (err) {
      console.error('Chat error:', err);
      setError(err.message || 'Connection failed. Ensure backend is running on port 8000.');
      addMessage({
        role: 'error',
        content: error || 'Failed to send message',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-20">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center mb-6">
                <span className="text-4xl">🧠</span>
              </div>
              <h2 className="text-2xl font-bold text-slate-100 mb-2">Welcome to Zaram</h2>
              <p className="text-slate-400 max-w-md">
                Your AI Operating System. Start a conversation, upload documents, or manage your knowledge.
              </p>
            </div>
          ) : (
            <>
              {messages.map(msg => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <div className="flex justify-center py-4">
                  <div className="flex gap-2">
                    <div className="w-3 h-3 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-3 h-3 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-3 h-3 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-4 py-3 mx-4 mb-4 bg-red-950/30 border border-red-500/30 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-cyan-950/30 bg-slate-950/50 backdrop-blur-xl p-4">
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </div>

      {/* Hidden Audio Element */}
      <audio ref={audioRef} crossOrigin="anonymous" />
    </div>
  );
};
