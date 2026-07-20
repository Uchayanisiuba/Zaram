// frontend/src/components/conversation/ResponseActions.tsx
//
// Response action bar for assistant messages.
// Alpha: Copy, Helpful, Not Helpful, Regenerate.
// Future: More menu (Save to Memory, Pin, Export, Share, Report, Save to Notes).

import { useState } from 'react'
import { Copy, ThumbsUp, ThumbsDown, RefreshCw, MoreHorizontal, Check } from 'lucide-react'
import type { Message } from '@/pages/ConversationPanel'

interface ResponseActionsProps {
  message: Message
  onRegenerate?: (message: Message) => void
}

export function ResponseActions({ message, onRegenerate }: ResponseActionsProps) {
  const [copied, setCopied] = useState(false)
  const [showMore, setShowMore] = useState(false)
  const [feedback, setFeedback] = useState<'helpful' | 'not-helpful' | null>(null)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  const handleFeedback = (type: 'helpful' | 'not-helpful') => {
    setFeedback(type)
    // Future: send feedback to backend
  }

  const handleRegenerate = () => {
    onRegenerate?.(message)
  }

  return (
    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        onClick={handleCopy}
        className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
        title="Copy"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      
      <button
        onClick={() => handleFeedback('helpful')}
        className={`p-1.5 rounded-md transition-colors ${
          feedback === 'helpful'
            ? 'text-green-400 bg-green-400/10'
            : 'text-slate-400 hover:text-white hover:bg-white/5'
        }`}
        title="Helpful"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      
      <button
        onClick={() => handleFeedback('not-helpful')}
        className={`p-1.5 rounded-md transition-colors ${
          feedback === 'not-helpful'
            ? 'text-red-400 bg-red-400/10'
            : 'text-slate-400 hover:text-white hover:bg-white/5'
        }`}
        title="Not Helpful"
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
      
      <button
        onClick={handleRegenerate}
        className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
        title="Regenerate"
      >
        <RefreshCw className="w-3.5 h-3.5" />
      </button>

      <div className="relative">
        <button
          onClick={() => setShowMore(!showMore)}
          className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          title="More"
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
        {showMore && (
          <div className="absolute bottom-full left-0 mb-1 w-40 glass rounded-lg border border-white/10 shadow-xl overflow-hidden z-50">
            <div className="p-1 space-y-0.5">
              <button className="w-full text-left px-2 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 transition-colors">
                Save to Memory
              </button>
              <button className="w-full text-left px-2 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 transition-colors">
                Pin
              </button>
              <button className="w-full text-left px-2 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 transition-colors">
                Export
              </button>
              <button className="w-full text-left px-2 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 transition-colors">
                Share
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
