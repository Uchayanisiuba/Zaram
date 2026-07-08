import { useState, useRef } from 'react';

export const ChatInput = ({ onSend, disabled }) => {
  const [text, setText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!text.trim()) return;
    onSend(text, selectedFile);
    setText('');
    setSelectedFile(null);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Auto-expand textarea
  const handleTextChange = (e) => {
    setText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    }
  };

  return (
    <div className="space-y-3">
      {/* File Badge */}
      {selectedFile && (
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-800/50 border border-slate-700/30 rounded-lg">
          <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
            <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
          </svg>
          <span className="text-sm text-slate-300 truncate flex-1">{selectedFile.name}</span>
          <button
            onClick={handleRemoveFile}
            className="p-1 hover:bg-red-500/20 rounded text-red-400"
            title="Remove file"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Input Area */}
      <div className="flex gap-3">
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask Zaram... (Shift+Enter for new line)"
          className="flex-1 px-4 py-3 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-100 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 disabled:opacity-50 disabled:cursor-not-allowed resize-none transition-all max-h-[120px]"
          rows="1"
        />

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          {/* File Upload */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="p-3 hover:bg-slate-700/50 rounded-lg transition-colors text-slate-400 hover:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Attach file"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.414a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>

          {/* Send Button */}
          <button
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="p-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-lg transition-all text-white disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 font-medium"
            title="Send message (Enter)"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M16.6915026,12.4744748 L3.50612381,13.2599618 C3.19218622,13.2599618 3.03521743,13.4170592 3.03521743,13.5741566 L1.15159189,20.0151496 C0.8376543,20.8006365 0.99,21.89 1.77946707,22.52 C2.41,22.99 3.50612381,23.1 4.13399899,22.8429026 L21.714504,14.0454487 C22.6563168,13.5741566 23.1272231,12.6315722 22.9702544,11.6889879 L4.13399899,1.16417323 C3.50612381,-0.0343686533 2.40987804,-0.0343686533 1.77946707,0.8429026 C0.994623095,1.4766014 0.837654326,2.41200634 1.15159189,3.1974932 L3.03521743,9.6384862 C3.03521743,9.95244691 3.19218622,10.1095443 3.50612381,10.1095443 L16.6915026,10.8950312 C16.6915026,10.8950312 17.1624089,10.8950312 17.1624089,10.4237391 L17.1624089,11.3663233 C17.1624089,11.3663233 17.1624089,12.4744748 16.6915026,12.4744748 Z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileSelect}
        accept=".pdf,.docx,.txt,.pptx,.xlsx,.jpg,.png,.mp3,.wav"
        className="hidden"
      />
    </div>
  );
};
