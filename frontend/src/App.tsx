/**
 * Zaram App — Project A UI + Zaram Architecture
 * 
 * Wires Project A's clean UI to Zaram's runtime system:
 * - useRuntimeLoop drives the 4-stage pipeline
 * - orbStore, conversationStore manage state
 * - All core/ simulation/frame architecture preserved
 */
import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useRuntimeLoop } from '@/hooks/useRuntimeLoop';
import TopNav from './components/TopNav';
import LeftRail from './components/LeftRail';
import RuntimePanel from './components/RuntimePanel';
import BottomDock from './components/BottomDock';
import ChatSurface from './components/chat/ChatSurface';
import CommandPalette from './components/CommandPalette';
import Landing from './workspaces/Landing';
import BuildWorkspace from './workspaces/BuildWorkspace';
import MemoryWorkspace from './workspaces/MemoryWorkspace';
import KnowledgeWorkspace from './workspaces/KnowledgeWorkspace';
import CanvasWorkspace from './workspaces/CanvasWorkspace';
import PluginsWorkspace from './workspaces/PluginsWorkspace';
import SettingsWorkspace from './workspaces/SettingsWorkspace';
import { useOrbStore } from '@/stores/orbStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useShellStore } from '@/stores/shellStore';
import { useShortcuts } from '@/hooks/useShortcuts';
import { detectPlatform } from '@/runtime/shortcuts/registry';
import HelpOverlay from '@/components/shortcuts/HelpOverlay';

type WorkspaceId = 'landing' | 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings';

export default function App() {
  // Start Zaram's core runtime loop (FrameState pipeline)
  useRuntimeLoop(60);

  const [workspace, setWorkspace] = useState<WorkspaceId>('landing');
  const [commandOpen, setCommandOpen] = useState(false);
  const [runtimeOpen] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);
  const { chatView, toggleChat, closeChat } = useChatModeStore();
  const platform = detectPlatform();

  const isLanding = workspace === 'landing';

  useShortcuts(platform, {
    navigate: (id) => { setWorkspace(id); setCommandOpen(false); },
    openCommand: () => setCommandOpen(true),
    toggleChat: () => useChatModeStore.getState().toggleChat(),
    toggleDock: () => useShellStore.getState().toggleDock(),
    setOrb: (state) => useOrbStore.getState().setOrbState(state),
    toggleHelp: () => setHelpOpen((o) => !o),
  });

  const navigate = (id: WorkspaceId) => {
    closeChat();
    setWorkspace(id);
    setCommandOpen(false);
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: '#080a0e',
        overflow: 'hidden',
      }}
    >
      {/* Top navigation bar — hidden on landing */}
      {!isLanding && <TopNav workspace={workspace} onSearchOpen={() => setCommandOpen(true)} />}

      {/* Body: left rail + workspace + runtime panel */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Left context rail — hidden on landing */}
        {!isLanding && <LeftRail workspace={workspace} onNavigate={navigate} />}

        {/* Main workspace area */}
        <main
          style={{
            flex: 1,
            display: 'flex',
            overflow: 'hidden',
            position: 'relative',
            background: isLanding ? '#080a0e' : '#080a0e',
          }}
        >
          {isLanding && (
            <div key="landing" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <Landing onNavigate={(id) => navigate(id as WorkspaceId)} onOrbTap={toggleChat} />
            </div>
          )}
          {workspace === 'build' && (
            <div key="build" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <BuildWorkspace />
            </div>
          )}
          {workspace === 'memory' && (
            <div key="memory" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <MemoryWorkspace />
            </div>
          )}
          {workspace === 'knowledge' && (
            <div key="knowledge" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <KnowledgeWorkspace />
            </div>
          )}
          {workspace === 'canvas' && (
            <div key="canvas" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <CanvasWorkspace />
            </div>
          )}
          {workspace === 'plugins' && (
            <div key="plugins" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <PluginsWorkspace />
            </div>
          )}
          {workspace === 'settings' && (
            <div key="settings" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <SettingsWorkspace />
            </div>
          )}
        </main>

        {/* Runtime panel — hidden on landing */}
        {!isLanding && runtimeOpen && <RuntimePanel />}
      </div>

      {/* Bottom dock — hidden on landing */}
      {!isLanding && <BottomDock workspace={workspace} onNavigate={navigate} onSearch={() => setCommandOpen(true)} />}

      {/* Command palette overlay */}
      {commandOpen && <CommandPalette onClose={() => setCommandOpen(false)} onNavigate={(id) => navigate(id as WorkspaceId)} />}

      {/* Chat surface — slides in from the right over the landing */}
      <AnimatePresence>
        {chatView === 'chat' && <ChatSurface />}
      </AnimatePresence>

      {/* Shortcuts help overlay */}
      <HelpOverlay open={helpOpen} platform={platform} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
