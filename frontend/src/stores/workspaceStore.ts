import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PanelId, PanelConfig, WorkspaceLayout } from '@/types/workspace'

interface WorkspaceState {
  layout: WorkspaceLayout;
  activePanelId: PanelId | null;
  openArtifacts: string[];

  addPanel: (panel: PanelConfig) => void;
  removePanel: (id: PanelId) => void;
  togglePanel: (id: PanelId) => void;
  setActivePanel: (id: PanelId) => void;
  updatePanelSize: (id: PanelId, width?: number, height?: number) => void;
  openArtifactInPanel: (artifactId: string, panelId?: PanelId) => void;
  closeArtifact: (artifactId: string) => void;
}

const defaultPanels: PanelConfig[] = [
  { id: 'conversation', title: 'Conversation', visible: true },
  { id: 'artifacts', title: 'Artifacts', visible: true },
  { id: 'orb', title: 'Living Orb', visible: true },
  { id: 'diagnostics', title: 'Diagnostics', visible: false },
];

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      layout: {
        panels: defaultPanels,
        splitDirection: 'horizontal',
      },
      activePanelId: 'conversation',
      openArtifacts: [],

      addPanel: (panel) => set((state) => {
        const exists = state.layout.panels.find((p) => p.id === panel.id);
        if (exists) return state;
        return {
          layout: {
            ...state.layout,
            panels: [...state.layout.panels, panel],
          },
        };
      }),

      removePanel: (id) => set((state) => ({
        layout: {
          ...state.layout,
          panels: state.layout.panels.filter((p) => p.id !== id),
        },
      })),

      togglePanel: (id) => set((state) => {
        const panels = state.layout.panels.map((p) =>
          p.id === id ? { ...p, visible: !p.visible } : p
        );
        return { layout: { ...state.layout, panels } };
      }),

      setActivePanel: (id) => set({ activePanelId: id }),

      updatePanelSize: (id, width, height) => set((state) => {
        const panels = state.layout.panels.map((p) => {
          if (p.id !== id) return p;
          const updated: PanelConfig = { ...p };
          if (width !== undefined) updated.width = width;
          if (height !== undefined) updated.height = height;
          return updated;
        });
        return { layout: { ...state.layout, panels } };
      }),

      openArtifactInPanel: (artifactId, panelId) => set((state) => {
        const openArtifacts = state.openArtifacts.includes(artifactId)
          ? state.openArtifacts
          : [...state.openArtifacts, artifactId];
        return {
          openArtifacts,
          activePanelId: panelId || 'artifacts',
        };
      }),

      closeArtifact: (artifactId) => set((state) => ({
        openArtifacts: state.openArtifacts.filter((id) => id !== artifactId),
      })),
    }),
    {
      name: 'zaram-workspace-layout',
      partialize: (state) => ({
        layout: state.layout,
        activePanelId: state.activePanelId,
        openArtifacts: state.openArtifacts,
      }),
    }
  )
)
