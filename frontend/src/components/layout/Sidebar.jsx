import { useZaram } from '../../hooks/useZaram';

export const Sidebar = () => {
  const { sidebarCollapsed, setSidebarCollapsed, clearMessages, messages } = useZaram();

  return (
    <aside className={`${
      sidebarCollapsed ? 'w-20' : 'w-64'
    } transition-all duration-300 bg-slate-950/80 backdrop-blur-xl border-r border-cyan-950/30 flex flex-col overflow-hidden`}>
      
      {/* Header */}
      <div className="h-16 border-b border-cyan-950/30 flex items-center justify-between px-4">
        {!sidebarCollapsed && <span className="text-xs font-bold uppercase tracking-widest text-cyan-400">Navigation</span>}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="p-2 hover:bg-cyan-950/30 rounded-lg transition-colors text-cyan-400"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sidebarCollapsed ? "M9 5l7 7-7 7" : "M15 19l-7-7 7-7"} />
          </svg>
        </button>
      </div>

      {/* New Chat Button */}
      <button
        onClick={clearMessages}
        className="m-4 px-4 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-lg font-medium text-sm transition-all shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 flex items-center justify-center gap-2"
      >
        <span>➕</span>
        {!sidebarCollapsed && 'New Chat'}
      </button>

      {/* Session Info */}
      {!sidebarCollapsed && (
        <div className="px-4 py-3 text-xs text-slate-400 border-t border-cyan-950/20">
          <p className="font-medium text-slate-300 mb-1">Session</p>
          <p className="text-xs text-slate-500 break-all">{messages.length} messages</p>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Footer */}
      <div className="border-t border-cyan-950/30 p-4 space-y-2">
        {!sidebarCollapsed && (
          <>
            <p className="text-xs text-slate-500 text-center">Zaram v2.0</p>
            <p className="text-xs text-slate-600 text-center">AI Operating System</p>
          </>
        )}
      </div>
    </aside>
  );
};
