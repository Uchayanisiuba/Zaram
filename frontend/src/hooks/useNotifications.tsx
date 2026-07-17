import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react'

type NotificationType = 'success' | 'error' | 'info' | 'warning'

interface Notification {
  id: string
  type: NotificationType
  title: string
  message?: string
  timestamp: number
}

const NOTIFICATION_DURATION = 4000

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const addNotification = useCallback((type: NotificationType, title: string, message?: string) => {
    const id = `notif-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    setNotifications(prev => [...prev, { id, type, title, message, timestamp: Date.now() }])
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, NOTIFICATION_DURATION)
  }, [])

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }, [])

  return { notifications, addNotification, removeNotification }
}

export function NotificationContainer({ notifications, onRemove }: { notifications: Notification[]; onRemove: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
      <AnimatePresence>
        {notifications.map((notif) => (
          <motion.div
            key={notif.id}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className={`glass rounded-lg p-3 border shadow-lg flex items-start gap-3 ${
              notif.type === 'success' ? 'border-green-400/30' :
              notif.type === 'error' ? 'border-red-400/30' :
              notif.type === 'warning' ? 'border-yellow-400/30' :
              'border-blue-400/30'
            }`}
          >
            <div className="mt-0.5">
              {notif.type === 'success' && <CheckCircle2 className="w-4 h-4 text-green-400" />}
              {notif.type === 'error' && <XCircle className="w-4 h-4 text-red-400" />}
              {notif.type === 'warning' && <AlertTriangle className="w-4 h-4 text-yellow-400" />}
              {notif.type === 'info' && <Info className="w-4 h-4 text-blue-400" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white">{notif.title}</p>
              {notif.message && (
                <p className="text-[10px] text-slate-400 mt-0.5">{notif.message}</p>
              )}
            </div>
            <button
              onClick={() => onRemove(notif.id)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
