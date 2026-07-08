import { useZaram } from '../../hooks/useZaram';

export const Header = () => {
  const { activeTab, setActiveTab, showSettings, setShowSettings } = useZaram();

  const tabs = [
    { id: 'chat', label: 'Chat', icon: '💬' },
    { id: 'memory', label: 'Memory', icon: '🧠' },
    { id: 'knowledge', label: 'Knowledge', icon: '📚' },
  ];

  return (
    <header className="h-16 bg-slate-900/50 backdrop-blur-xl border-b border-cyan-950/30 flex items-center justify-between px-6 sticky top-0 z-40">
      {/* Logo & Title */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center font-bold text-white text-xs shadow-lg shadow-cyan-500/30">
          ZR
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-wider">ZARAM</h1>
          <p className="text-xs text-cyan-400/70 uppercase tracking-widest">AI Operating System</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <nav className="hidden md:flex items-center gap-1 bg-slate-950/50 p-1 rounded-lg border border-cyan-950/20">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-cyan-600/30 text-cyan-100 border border-cyan-400/30 shadow-lg shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/30'
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Settings Button */}
      <button
        onClick={() => setShowSettings(!showSettings)}
        className="p-2 hover:bg-cyan-950/30 rounded-lg transition-colors text-cyan-400 hover:text-cyan-300"
        title="Settings"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    </header>
  );
};
