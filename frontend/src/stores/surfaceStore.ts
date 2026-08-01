import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';

export type WorkspaceType = 'knowledge' | 'build' | 'create' | 'memory';

interface Surface {
  id: string;
  type: WorkspaceType;
  title: string;
  position: { x: number; y: number };
  zIndex: number;
}

interface SurfaceStore {
  surfaces: Surface[];
  focusedSurfaceId: string | null;
  openSurface: (type: WorkspaceType, title: string) => void;
  closeSurface: (id: string) => void;
  focusSurface: (id: string) => void;
  updatePosition: (id: string, position: { x: number; y: number }) => void;
}

const getHighestZIndex = (surfaces: Surface[]) => {
  return surfaces.reduce((max, s) => Math.max(max, s.zIndex), 10);
};

export const useSurfaceStore = create<SurfaceStore>((set) => ({
  surfaces: [],
  focusedSurfaceId: null,
  openSurface: (type, title) =>
    set((state) => {
      const newZIndex = getHighestZIndex(state.surfaces) + 1;
      const newSurface: Surface = {
        id: uuidv4(),
        type,
        title,
        position: { x: 0, y: 0 },
        zIndex: newZIndex,
      };
      return {
        surfaces: [...state.surfaces, newSurface],
        focusedSurfaceId: newSurface.id,
      };
    }),
  closeSurface: (id) =>
    set((state) => ({
      surfaces: state.surfaces.filter((s) => s.id !== id),
      focusedSurfaceId:
        state.focusedSurfaceId === id ? null : state.focusedSurfaceId,
    })),
  focusSurface: (id) =>
    set((state) => {
      const highestZIndex = getHighestZIndex(state.surfaces);
      return {
        surfaces: state.surfaces.map((s) =>
          s.id === id ? { ...s, zIndex: highestZIndex + 1 } : s
        ),
        focusedSurfaceId: id,
      };
    }),
  updatePosition: (id, position) =>
    set((state) => ({
      surfaces: state.surfaces.map((s) =>
        s.id === id ? { ...s, position } : s
      ),
    })),
}));