import { create } from 'zustand';

export type Theme = 'light' | 'dark' | 'system';

interface SettingsStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  theme: 'system',
  setTheme: (theme) => set({ theme }),
}));