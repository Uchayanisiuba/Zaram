import { useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { useChatStore } from '@/stores/chatStore'
import {
  Bot,
  User,
  Copy,
  Check,
  Download,
  RefreshCw,
  Edit3,
  RotateCcw,
  MoreHorizontal,
  FileText,
  Image,
  File,
  Loader2,
} from 'lucide-react'
import type { Message } from '@/types'

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function extractImageUrls(content: string): string[] {
  const urls: string[] = []
  const regex = /!\[.*?\]\((.*?)\)/g
  let match
  while ((match = regex.exec(content)) !== null) {
    urls.push(match[1])
  }
  return urls
}

function MessageActions({ message, onRegenerate, onEdit, onRetry }: {
  message: Message
  onRegenerate?: () => void
  onEdit?: (newContent: string) => void
  onRetry?: () => void
}) {
  const [showMenu, setShowMenu] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const imageUrls = extractImageUrls(message.content)
    if (imageUrls.length > 0) {
      imageUrls.forEach((url, i) => {
        const a = document.createElement('a')
        a.href = url
        a.download = `image_${i + 1}.png`
        a.click()
      })
    } else {
      downloadBlob(message.content, `message_${message.id}.txt`, 'text/plain')
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-white/70 transition-colors"
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>
      <AnimatePresence>
        {showMenu && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="absolute right-0 top-6 z-20 glass rounded-lg border border-white/10 shadow-xl py-1 min-w-[160px]"
          >
            <button
              onClick={handleCopy}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy Message'}
            </button>
            <button
              onClick={handleDownload}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
            {message.role === 'assistant' && (
              <>
                {onRegenerate && (
                  <button
                    onClick={onRegenerate}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Regenerate
                  </button>
                )}
              </>
            )}
            {message.role === 'user' && onEdit && (
              <button
                onClick={() => {
                  const newContent = prompt('Edit message:', message.content)
                  if (newContent !== null) onEdit(newContent)
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 transition-colors"
              >
                <Edit3 className="w-3.5 h-3.5" />
                Edit Prompt
              </button>
            )}
            {message.role === 'assistant' && onRetry && (
              <button
                onClick={onRetry}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Retry
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function ChatWindow() {
  const { messages, isLoading, regenerateMessage, editMessage, retryMessage } = useChatStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [streamingId, setStreamingId] = useState<string | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingId])

  const handleRegenerate = (id: string) => {
    setStreamingId(id)
    regenerateMessage(id)
    setTimeout(() => setStreamingId(null), 3000)
  }

  const handleEdit = (id: string, newContent: string) => {
    editMessage(id, newContent)
  }

  const handleRetry = (id: string) => {
    setStreamingId(id)
    retryMessage(id)
    setTimeout(() => setStreamingId(null), 3000)
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-6">
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <h2 className="text-2xl font-bold mb-2">Welcome to Zaram</h2>
            <p className="text-muted-foreground">Start a conversation with your AI assistant</p>
          </div>
        </div>
      ) : (
        messages.map((message, index) => (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-white" />
              </div>
            )}
            <div className={`max-w-[70%] glass rounded-2xl p-4 relative group ${
              message.role === 'user' ? 'bg-white/10' : 'bg-white/5'
            }`}>
              <ReactMarkdown className="prose prose-invert prose-sm">
                {message.content}
              </ReactMarkdown>
              <div className="flex items-center justify-between mt-2">
                <p className="text-xs text-muted-foreground">
                  {message.timestamp.toLocaleTimeString()}
                </p>
                {streamingId === message.id && (
                  <span className="flex items-center gap-1 text-xs text-cyan-400">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Streaming...
                  </span>
                )}
              </div>
              {message.role === 'assistant' && !isLoading && (
                <div className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <MessageActions
                    message={message}
                    onRegenerate={() => handleRegenerate(message.id)}
                    onRetry={() => handleRetry(message.id)}
                  />
                </div>
              )}
              {message.role === 'user' && (
                <div className="absolute -left-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <MessageActions
                    message={message}
                    onEdit={(newContent) => handleEdit(message.id, newContent)}
                  />
                </div>
              )}
            </div>
            {message.role === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-white" />
              </div>
            )}
          </motion.div>
        ))
      )}
      {isLoading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex gap-4 justify-start"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div className="glass rounded-2xl p-4 bg-white/5">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              <span className="text-sm text-white/60">Thinking...</span>
            </div>
          </div>
        </motion.div>
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}
