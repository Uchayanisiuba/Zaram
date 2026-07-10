import { motion } from 'framer-motion'
import { 
  LayoutDashboard, MessageSquare, Cpu, Database, 
  HardDrive, Settings, Bot, Mic, Workflow, 
  ShoppingCart, BarChart3, Code, ChevronLeft, ChevronRight
} from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import { cn } from '@/lib/utils'

const menuItems = [
  { icon: LayoutDashboard, label: 'Workspace', path: '/' },
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: Cpu, label: 'Models', path: '/models' },
  { icon: Database, label: 'Knowledge', path: '/knowledge-vault' },
  { icon: HardDrive, label: 'Memory', path: '/memory' },
  { icon: Bot, label: 'Agents', path: '/agents' },
  { icon: Mic, label: 'Voice Studio', path: '/voice-studio' },
  { icon: Workflow, label: 'Automation', path: '/automation' },
  { icon: ShoppingCart, label: 'Marketplace', path: '/marketplace' },
  { icon: BarChart3, label: 'Analytics', path: '/analytics' },
  { icon: Settings, label: 'Settings', path: '/settings' },
  { icon: Code, label: 'Developer', path: '/developer' },
]

export function Sidebar() {
  const { sidebarOpen, toggleSidebar, currentTheme } = useThemeStore()

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarOpen ? 280 : 80 }}
      className={cn(
        'glass border-r border-white/10 flex flex-col h-screen relative',
        'transition-all duration-300'
      )}
    >
      <div className="p-6 flex items-center justify-between">
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center">
              <span className="text-white font-bold text-sm">Z</span>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-orange-400 bg-clip-text text-transparent">
              ZARAM
            </span>
          </motion.div>
        )}
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-lg hover:bg-white/5 transition-colors"
        >
          {sidebarOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
        </button>
      </div>

      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {menuItems.map((item) => (
          <motion.a
            key={item.path}
            href={item.path}
            className={cn(
              'flex items-center gap-3 px-3 py-3 rounded-lg transition-all duration-200 group',
              'hover:bg-white/5 glass-hover'
            )}
            whileHover={{ x: 4 }}
          >
            <item.icon className={cn("w-5 h-5 flex-shrink-0")} />
            {sidebarOpen && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                className="text-sm font-medium truncate"
              >
                {item.label}
              </motion.span>
            )}
          </motion.a>
        ))}
      </nav>

      <div className="p-4 border-t border-white/10">
        <div className={cn(
          "flex items-center gap-3 p-3 rounded-lg",
          sidebarOpen ? '' : 'justify-center'
        )}>
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <span className="text-white font-bold">A</span>
          </div>
          {sidebarOpen && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">Alexis</p>
              <p className="text-xs text-muted-foreground truncate">Online</p>
            </div>
          )}
        </div>
      </div>
    </motion.aside>
  )
}