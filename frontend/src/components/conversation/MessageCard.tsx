// frontend/src/components/conversation/MessageCard.tsx
//
// Premium assistant message card with response actions.

import { motion } from 'framer-motion'
import { Bot, User } from 'lucide-react'
import { Markdown } from '@/components/common/Markdown'
import { ResponseActions } from './ResponseActions'
import type { Message } from '@/pages/ConversationPanel'

interface MessageCardProps {
  message: Message
  noWorkspace: boolean
  onFilePreview: (filePath: string) => void
}

export function MessageCard({ message, noWorkspace, onFilePreview }: MessageCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      {message.role === 'assistant' && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0 mt-1">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}
      
      <div className={`flex flex-col gap-2 ${message.role === 'user' ? 'items-end' : 'items-start'} max-w-[90%]`}>
        {/* Workspace Context Pill */}
        {message.role === 'assistant' && message.workspaceContext && !noWorkspace && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] border border-white/10 bg-white/5 text-slate-400">
            <span>📁</span>
            <span>{message.workspaceContext.workspace}</span>
          </div>
        )}

        {/* Message Content */}
        <div className={`rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
          message.role === 'user'
            ? 'bg-white/10 text-white'
            : 'bg-black/40 border border-white/10 text-slate-200'
        } ${message.error ? 'border-red-500/30 bg-red-500/5' : ''}`}>
          {message.role === 'assistant' ? (
            <Markdown content={message.content} />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}

          {/* Referenced Files */}
                          {message.referencedFiles && message.referencedFiles.length > 0 && (
                            <div className="mt-3 space-y-1">
                              {message.referencedFiles.map((file: { path: string; name: string }, i: number) => (
                                <button
                                  key={i}
                                  onClick={() => onFilePreview(file.path)}
                                  className="flex items-center gap-2 px-2 py-1 rounded-lg text-xs bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 transition-colors"
                                >
                                  <span className="font-mono truncate max-w-[180px]">{file.name}</span>
                                </button>
                              ))}
                            </div>
                          )}
        </div>

        {/* Timestamp + Actions */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {message.role === 'assistant' && !message.error && (
            <ResponseActions message={message} />
          )}
        </div>

        {/* User Avatar */}
        {message.role === 'user' && (
          <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0 mt-1">
            <User className="w-4 h-4 text-white" />
          </div>
        )}
      </div>
    </motion.div>
  )
}
