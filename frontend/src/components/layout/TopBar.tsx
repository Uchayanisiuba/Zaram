import { motion } from 'framer-motion'
import { Bell, Search, Settings } from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'

export function TopBar() {
  const { currentTheme } = useThemeStore()

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="glass border-b border-white/10 px-6 py-4 flex items-center justify-between"
    >
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold">ZARAM OS</h1>
        <span className="px-3 py-1 rounded-full text-xs bg-white/5 border border-white/10">
          v1.2.1
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search..."
            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-white/20 w-64"
          />
        </div>
        <button className="p-2 rounded-lg hover:bg-white/5 transition-colors relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>
        <button className="p-2 rounded-lg hover:bg-white/5 transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </motion.header>
  )
}
