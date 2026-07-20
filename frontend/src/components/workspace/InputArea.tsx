import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Send, Paperclip, Mic, Brain, Database, FolderOpen, Globe, Loader2 } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useThemeStore } from '@/stores/themeStore'

export function InputArea() {
  const [rows, setRows] = useState(1)
  const { inputValue, setInputValue, addMessage, setLoading, isLoading } = useChatStore()
  const { currentTheme } = useThemeStore()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = async () => {
    if (!inputValue.trim() || isLoading) return

    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    })

    setInputValue('')
    setRows(1)
    setLoading(true)

    setTimeout(() => {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'This is a mock response. Connect to backend for real responses.',
        timestamp: new Date(),
      })
      setLoading(false)
    }, 1000)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="glass border-t border-white/10 p-6"
    >
      <div className="max-w-4xl mx-auto">
        <div className="glass rounded-2xl p-4 space-y-3">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value)
              setRows(Math.min(e.target.value.split('\n').length, 5))
            }}
            onKeyDown={handleKeyDown}
            rows={rows}
            placeholder="Type your message..."
            disabled={isLoading}
            className="w-full bg-transparent border-none outline-none resize-none text-sm placeholder:text-muted-foreground disabled:opacity-50"
          />

          <div className="flex items-center justify-between pt-3 border-t border-white/10">
            <div className="flex items-center gap-2">
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Attach file">
                <Paperclip className="w-4 h-4" />
              </button>
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Memory">
                <Brain className="w-4 h-4" />
              </button>
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Knowledge">
                <Database className="w-4 h-4" />
              </button>
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Projects">
                <FolderOpen className="w-4 h-4" />
              </button>
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Web Search">
                <Globe className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center gap-2">
              {isLoading && (
                <span className="flex items-center gap-1 text-xs text-cyan-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Generating...
                </span>
              )}
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors" title="Voice input">
                <Mic className="w-4 h-4" />
              </button>
              <button
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isLoading}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-orange-500 text-white font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
