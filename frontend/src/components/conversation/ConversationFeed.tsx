// frontend/src/components/conversation/ConversationFeed.tsx
//
// Scrollable conversation feed with modern message cards.

import { useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, Loader2, Bot } from 'lucide-react'
import { MessageCard } from './MessageCard'
import type { Message, ExecutiveState } from '@/pages/ConversationPanel'

interface ConversationFeedProps {
  messages: Message[]
  isLoading: boolean
  mappedState: ExecutiveState
  noWorkspace: boolean
  onFilePreview: (filePath: string) => void
  onRegenerate?: (message: Message) => void
  children?: React.ReactNode
}

export function ConversationFeed({
  messages,
  isLoading,
  mappedState,
  noWorkspace,
  onFilePreview,
  onRegenerate,
  children,
}: ConversationFeedProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="h-full w-full flex flex-col">
      {/* Conversation Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 flex-shrink-0">
        <div>
          <h2 className="text-base font-semibold text-white tracking-wide">Conversation</h2>
          <p className="text-[11px] text-slate-400 mt-0.5">Ask anything about your workspace</p>
        </div>
        {isLoading && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono border border-blue-400/30 bg-blue-400/5 text-blue-300">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{mappedState}</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full py-8">
            <div className="text-center">
              <MessageSquare className="w-12 h-12 mx-auto mb-4 text-slate-600" />
              <p className="text-slate-400 text-base font-medium">How can I help you today?</p>
              <p className="text-slate-500 text-sm mt-2 max-w-xs mx-auto">
                I can search your workspace, read files, analyze images, and run capabilities.
              </p>
            </div>
          </div>
        )}
        
        <AnimatePresence>
          {messages.map((msg) => (
            <div key={msg.id} className="group">
              <MessageCard
                message={msg}
                noWorkspace={noWorkspace}
                onFilePreview={onFilePreview}
              />
              {msg.role === 'assistant' && !msg.error && (
                <div className="mt-1 ml-11 opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="flex items-center gap-1">
                    {/* Response actions are now integrated into MessageCard */}
                  </div>
                </div>
              )}
            </div>
          ))}
        </AnimatePresence>
        
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3 justify-start"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0 mt-1">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-black/40 border border-white/10 flex items-center gap-2">
              <motion.div
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              </motion.div>
              <span className="text-sm text-white/60">{mappedState}</span>
            </div>
          </motion.div>
        )}
        <div ref={endRef} />
      </div>
      {children && <div className="flex-shrink-0">{children}</div>}
    </div>
  )
}
