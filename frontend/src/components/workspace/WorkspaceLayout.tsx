import React, { useState, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import { MessageSquare, FileText, Circle, Activity, Terminal, StickyNote, Globe } from 'lucide-react';
import { useWorkspaceStore, useArtifactStore } from '@/stores';
import { ArtifactSidebar } from '@/components/artifacts/ArtifactSidebar';
import { ArtifactViewer } from '@/components/artifacts/ArtifactViewer';
import { ChatWindow } from '@/components/workspace/ChatWindow';
import { InputArea } from '@/components/workspace/InputArea';
import { DiagnosticsPanel } from '@/components/DiagnosticsPanel';
import { LivingOrb } from '@/components/LivingOrb/LivingOrb';
import { TopBar } from '@/components/layout/TopBar';
import { registerDefaultViewers } from '@/components/artifacts/viewerPlugins';

registerDefaultViewers();

const panelIcons: Record<string, React.ElementType> = {
  conversation: MessageSquare,
  artifacts: FileText,
  orb: Circle,
  diagnostics: Activity,
  terminal: Terminal,
  notes: StickyNote,
  browser: Globe,
};

export function WorkspaceLayout() {
  const [leftWidth, setLeftWidth] = useState(300);
  const [rightWidth, setRightWidth] = useState(320);
  const [isDraggingLeft, setIsDraggingLeft] = useState(false);
  const [isDraggingRight, setIsDraggingRight] = useState(false);

  const layout = useWorkspaceStore((s) => s.layout);
  const togglePanel = useWorkspaceStore((s) => s.togglePanel);
  const openArtifactId = useArtifactStore((s) => s.openArtifactId);

  const handleLeftMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingLeft(true);
  }, []);

  const handleRightMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingRight(true);
  }, []);

  React.useEffect(() => {
    if (!isDraggingLeft && !isDraggingRight) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingLeft) {
        setLeftWidth(Math.max(200, Math.min(600, e.clientX)));
      }
      if (isDraggingRight) {
        const windowWidth = window.innerWidth;
        const newRightWidth = Math.max(200, Math.min(600, windowWidth - e.clientX));
        setRightWidth(newRightWidth);
      }
    };
    const handleMouseUp = () => {
      setIsDraggingLeft(false);
      setIsDraggingRight(false);
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingLeft, isDraggingRight]);

  const conversationPanel = layout.panels.find((p) => p.id === 'conversation');
  const artifactsPanel = layout.panels.find((p) => p.id === 'artifacts');
  const orbPanel = layout.panels.find((p) => p.id === 'orb');
  const diagnosticsPanel = layout.panels.find((p) => p.id === 'diagnostics');

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        {conversationPanel?.visible && (
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 flex items-center justify-center p-8">
              <LivingOrb />
            </div>
            <div className="h-[40vh] min-h-[200px]">
              <ChatWindow />
            </div>
            <InputArea />
          </div>
        )}

        {artifactsPanel?.visible && (
          <>
            <div
              onMouseDown={handleLeftMouseDown}
              className="w-1 cursor-col-resize bg-white/5 hover:bg-cyan-500/30 transition-colors"
            />
            <div
              className="flex flex-col border-l border-white/10"
              style={{ width: leftWidth }}
            >
              <ArtifactSidebar />
            </div>
          </>
        )}

        {orbPanel?.visible && !conversationPanel?.visible && (
          <div className="flex-1 flex items-center justify-center">
            <LivingOrb />
          </div>
        )}

        {diagnosticsPanel?.visible && (
          <div
            className="border-l border-white/10"
            style={{ width: rightWidth }}
          >
            <DiagnosticsPanel />
          </div>
        )}
      </div>
    </div>
  );
}
