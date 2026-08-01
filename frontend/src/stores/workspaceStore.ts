import { create } from 'zustand';

interface Camera {
  x: number;
  y: number;
  zoom: number;
}

interface WorkspaceState {
  camera: Camera;
  setCamera: (update: Partial<Camera>) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  camera: { x: 0, y: 0, zoom: 1 },
  setCamera: (update) =>
    set((state) => ({
      camera: { ...state.camera, ...update },
    })),
}));