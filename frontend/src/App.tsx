/**
 * Zaram App — Project A UI + Zaram Architecture
 * 
 * Wires Project A's clean UI to Zaram's runtime system:
 * - useRuntimeLoop drives the 4-stage pipeline
 * - orbStore, conversationStore manage state
 * - All core/ simulation/frame architecture preserved
 */
import { useState, useEffect } from 'react';
import { useRuntimeLoop } from '@/hooks/useRuntimeLoop';
import TopNav from './components/TopNav';
import LeftRail from './components/LeftRail';
import RuntimePanel from './components/RuntimePanel';
import BottomDock from './components/BottomDock';
import CommandPalette from './components/CommandPalette';
import Landing from './workspaces/Landing';
import BuildWorkspace from './workspaces/BuildWorkspace';
import MemoryWorkspace from './workspaces/MemoryWorkspace';
import KnowledgeWorkspace from './workspaces/KnowledgeWorkspace';
import CanvasWorkspace from './workspaces/CanvasWorkspace';
import PluginsWorkspace from './workspaces/PluginsWorkspace';
import SettingsWorkspace from './workspaces/SettingsWorkspace';

type WorkspaceId = 'landing' | 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings';

export default function App() {
  // Start Zaram's core runtime loop (FrameState pipeline)
  useRuntimeLoop(60);

  const [workspace, setWorkspace] = useState<WorkspaceId>('landing');
  const [commandOpen, setCommandOpen] = useState(false);
  const [runtimeOpen] = useState(true);

  const isLanding = workspace === 'landing';

  // ⌘K to open command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const navigate = (id: WorkspaceId) => {
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
              <Landing onNavigate={(id) => navigate(id as WorkspaceId)} />
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
    </div>
  );
}
