import { useState } from 'react';
import { useZaram } from '../../hooks/useZaram';

export const ChatMessage = ({ message }) => {
  const { playAudio, isSpeaking } = useZaram();
  const [copied, setCopied] = useState(false);

  const isUser = message.role === 'user';
  const isError = message.role === 'error';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePlayAudio = () => {
    if (message.audioUrl) {
      playAudio(message.audioUrl);
    }
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl ${
        isError
          ? 'bg-red-950/30 border border-red-500/30 rounded-lg px-4 py-3'
          : isUser
          ? 'bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border border-cyan-500/30 rounded-lg px-4 py-3'
          : 'bg-slate-800/50 border border-slate-700/30 rounded-lg px-4 py-3'
      }`}>
        
        {/* Header */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              {message.character === 'zaram_prime' ? '🧠 Zaram Prime' : `🤖 ${message.character}`}
            </span>
            {message.model && (
              <span className="text-xs text-slate-500">•</span>
            )}
            {message.model && (
              <span className="text-xs text-slate-500">{message.model}</span>
            )}
          </div>
        )}

        {/* Content */}
        <p className={`text-sm leading-relaxed ${isError ? 'text-red-300' : isUser ? 'text-blue-100' : 'text-slate-200'}`}>
          {message.content}
        </p>

        {/* File Indicator */}
        {message.file && (
          <div className="mt-3 text-xs text-slate-400 bg-slate-900/50 px-3 py-2 rounded border border-slate-700/50 inline-block">
            📎 {message.file}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center gap-2 mt-3">
          {!isUser && message.audioUrl && (
            <button
              onClick={handlePlayAudio}
              className="p-1.5 hover:bg-cyan-500/20 rounded-lg transition-colors text-cyan-400 hover:text-cyan-300"
              title="Play audio"
            >
              {isSpeaking ? (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>
          )}

          <button
            onClick={handleCopy}
            className="p-1.5 hover:bg-slate-700/50 rounded-lg transition-colors text-slate-500 hover:text-slate-300"
            title="Copy message"
          >
            {copied ? (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>

          {message.processingTime && (
            <span className="text-xs text-slate-500 ml-auto">
              {message.processingTime.toFixed(2)}s
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
