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
import ChatSurface from './components/chat/ChatSurface';
import SourcePanelLayer from './components/chat/SourcePanelLayer';
import CommandPalette from './components/CommandPalette';
import Landing from './workspaces/Landing';
import WorkWorkspace from './workspaces/WorkWorkspace';
import MemoryWorkspace from './workspaces/MemoryWorkspace';
import KnowledgeWorkspace from './workspaces/KnowledgeWorkspace';
import ActivityWorkspace from './workspaces/ActivityWorkspace';
import SettingsWorkspace from './workspaces/SettingsWorkspace';
import { useOrbStore } from '@/stores/orbStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useShellStore } from '@/stores/shellStore';
import { useShortcuts } from '@/hooks/useShortcuts';
import { detectPlatform } from '@/runtime/shortcuts/registry';
import HelpOverlay from '@/components/shortcuts/HelpOverlay';

// Build, Canvas and Plugins are out of scope for v1. Their surfaces are preserved
// in src/legacy/ and are not reachable from the shell.
import type { WorkspaceId } from '@/runtime/shortcuts/registry';

export default function App() {
  // Start Zaram's core runtime loop (FrameState pipeline)
  useRuntimeLoop(60);

  const [workspace, setWorkspace] = useState<WorkspaceId>('landing');
  const [commandOpen, setCommandOpen] = useState(false);
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
    // The conversation takes less width beside work than it does on the
    // landing, where it is the main event.
    useChatModeStore.getState().setContext(id === 'landing' ? 'landing' : 'workspace');
  };

  /** The Orb, from anywhere, goes to the conversation.
   *
   *  It used to slide a narrow chat column in beside whatever workspace you
   *  were on, which made the same gesture produce two different things
   *  depending on where you stood — a small orb and a cramped column here, the
   *  full conversation there. The Orb is one object with one meaning, so it now
   *  does one thing: return to the conversation as it appears from the landing,
   *  full size. Workspaces are somewhere you go and come back from. */
  const openConversation = () => {
    setWorkspace('landing');
    setCommandOpen(false);
    const chat = useChatModeStore.getState();
    chat.setContext('landing');
    chat.openChat();
  };

  return (
    <div
      className="zaram-backdrop"
      style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Top navigation bar — hidden on landing */}
      {!isLanding && (
        <TopNav
          workspace={workspace}
          onSearchOpen={() => setCommandOpen(true)}
          onOpenConversation={openConversation}
        />
      )}

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
            // Transparent so the shell's shared backdrop shows through and the
            // glass surfaces have something to refract.
            background: 'transparent',
          }}
        >
          {isLanding && (
            <div key="landing" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <Landing onNavigate={(id) => navigate(id as WorkspaceId)} onOrbTap={toggleChat} />
            </div>
          )}
          {workspace === 'work' && (
            <div key="work" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <WorkWorkspace />
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
          {workspace === 'activity' && (
            <div key="activity" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <ActivityWorkspace />
            </div>
          )}
          {workspace === 'settings' && (
            <div key="settings" style={{ flex: 1, display: 'flex', animation: 'fade-in 0.25s ease' }}>
              <SettingsWorkspace />
            </div>
          )}
        </main>
      </div>

      {/* Bottom dock — hidden on landing */}
      {/* The floating dock is gone. It duplicated the left rail exactly — the
          same four destinations, twice on screen — and floated over content,
          which is how it ended up covering Activity's retention controls. One
          navigation surface. */}

      {/* Command palette overlay */}
      {commandOpen && <CommandPalette onClose={() => setCommandOpen(false)} onNavigate={(id) => navigate(id as WorkspaceId)} />}

      {/* Chat surface — slides in from the right over the landing */}
      <AnimatePresence>
        {chatView === 'chat' && <ChatSurface />}
      </AnimatePresence>

      {/* Source panels — over the orb region, beside the conversation. */}
      <SourcePanelLayer />

      {/* Shortcuts help overlay */}
      <HelpOverlay open={helpOpen} platform={platform} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
