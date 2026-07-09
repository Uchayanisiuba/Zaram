import { useState } from 'react';
import { ZaramProvider } from './context/ZaramContext';
import { useZaram } from './hooks/useZaram';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { Chat } from './components/chat/Chat';
import { Memory } from './components/memory/Memory';
import { Knowledge } from './components/knowledge/Knowledge';
import { Settings } from './components/settings/Settings';

const AppContent = () => {
  const { activeTab, showSettings } = useZaram();

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Animated Background Gradient */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent pointer-events-none" />

      {/* Header */}
      <Header />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Sidebar */}
        <Sidebar />

        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden">
          {showSettings ? (
            <div className="flex-1 overflow-auto">
              <Settings />
            </div>
          ) : (
            <>
              {/* Chat */}
              {activeTab === 'chat' && <Chat />}

              {/* Memory */}
              {activeTab === 'memory' && (
                <div className="flex-1 overflow-auto">
                  <Memory />
                </div>
              )}

              {/* Knowledge */}
              {activeTab === 'knowledge' && (
                <div className="flex-1 overflow-auto">
                  <Knowledge />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <ZaramProvider>
      <AppContent />
    </ZaramProvider>
  );
}
