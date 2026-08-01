import { create } from 'zustand';

interface ShellState {
  isDockOpen: boolean;
  toggleDock: () => void;
}

export const useShellStore = create<ShellState>((set) => ({
  isDockOpen: true,
  toggleDock: () => set((state) => ({ isDockOpen: !state.isDockOpen })),
}));