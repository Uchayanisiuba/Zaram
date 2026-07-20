// frontend/src/components/conversation/ConversationInput.tsx
//
// Bottom conversation input with attachment menu.

import { useState, useRef, useEffect } from 'react'
import { Paperclip, ImagePlus, Camera, Monitor, Mic, Play, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { Message } from '@/pages/ConversationPanel'

interface ConversationInputProps {
  input: string
  isLoading: boolean
  isListening: boolean
  attachedImages: string[]
  showAttachmentMenu: boolean
  onInputChange: (value: string) => void
  onSend: () => void
  onVoice: () => void
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void
  onCameraCapture: () => void
  onScreenCapture: () => void
  onClipboardPaste: () => void
  onRemoveImage: (index: number) => void
  onToggleAttachmentMenu: () => void
}

export function ConversationInput({
  input,
  isLoading,
  isListening,
  attachedImages,
  showAttachmentMenu,
  onInputChange,
  onSend,
  onVoice,
  onFileSelect,
  onCameraCapture,
  onScreenCapture,
  onClipboardPaste,
  onRemoveImage,
  onToggleAttachmentMenu,
}: ConversationInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    textInputRef.current?.focus()
  }, [])

  return (
    <div className="px-6 py-4 border-t border-white/5 flex-shrink-0">
      {attachedImages.length > 0 && (
        <div className="flex gap-2 mb-3 overflow-x-auto pb-2">
          {attachedImages.map((img, i) => (
            <div key={i} className="relative flex-shrink-0">
              <img src={img} alt="Attached" className="h-14 w-14 object-cover rounded-lg border border-white/10" />
              <button
                onClick={() => onRemoveImage(i)}
                className="absolute -top-1 -right-1 p-0.5 bg-red-500 rounded-full text-white"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      
      <div className="glass rounded-2xl p-2 flex items-center gap-2 border border-white/10">
        {/* Universal Attachment Menu */}
        <div className="relative">
          <button
            onClick={onToggleAttachmentMenu}
            className="p-2 rounded-lg text-slate-400 hover:text-white transition-colors"
            title="Attach..."
          >
            <Paperclip className="w-4 h-4" />
          </button>
          
          {showAttachmentMenu && (
            <div className="absolute bottom-full left-0 mb-2 w-64 glass rounded-xl border border-white/10 shadow-xl overflow-hidden z-50">
              <div className="p-2 space-y-1">
                <button onClick={() => { fileInputRef.current?.click(); onToggleAttachmentMenu() }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <ImagePlus className="w-4 h-4" /> Images
                </button>
                <button onClick={() => { onToggleAttachmentMenu(); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <span className="text-sm">📄</span> Documents
                </button>
                <button onClick={() => { onToggleAttachmentMenu(); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <span className="text-sm">📁</span> Entire Folder
                </button>
                <button onClick={() => { onCameraCapture(); onToggleAttachmentMenu(); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <Camera className="w-4 h-4" /> Camera
                </button>
                <button onClick={() => { onScreenCapture(); onToggleAttachmentMenu(); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <Monitor className="w-4 h-4" /> Screen Share
                </button>
                <button onClick={() => { onClipboardPaste(); onToggleAttachmentMenu(); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-slate-300 text-sm transition-colors">
                  <span className="text-sm">📋</span> Clipboard
                </button>
              </div>
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={onFileSelect}
          className="hidden"
        />
        
        <input
          ref={textInputRef}
          type="text"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
          placeholder="Message Zaram..."
          className="flex-1 bg-transparent outline-none text-sm text-white px-4"
        />
        
        <button
          onClick={onVoice}
          className={`p-2 rounded-lg transition-colors ${isListening ? 'bg-red-500/20 text-red-400' : 'text-slate-400 hover:text-white'}`}
        >
          <Mic className="w-4 h-4" />
        </button>
        
        <Button onClick={onSend} disabled={!input.trim() || isLoading}>
          <Play className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
