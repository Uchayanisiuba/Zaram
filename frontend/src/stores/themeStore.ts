import { create } from 'zustand'
import { CharacterTheme } from '@/types'

interface ThemeState {
  currentTheme: CharacterTheme
  sidebarOpen: boolean
  rightPanelOpen: boolean
  setTheme: (theme: CharacterTheme) => void
  toggleSidebar: () => void
  toggleRightPanel: () => void
  getThemeColor: () => string
}

const themeColors: Record<CharacterTheme, string> = {
  alexis: 'hsl(346 84% 60%)',
  aria: 'hsl(329 84% 60%)',
  nova: 'hsl(301 84% 60%)',
  luna: 'hsl(271 84% 60%)',
  kai: 'hsl(211 84% 60%)',
  leo: 'hsl(174 84% 60%)',
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  currentTheme: 'alexis',
  sidebarOpen: true,
  rightPanelOpen: true,
  setTheme: (theme) => set({ currentTheme: theme }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleRightPanel: () => set((state) => ({ rightPanelOpen: !state.rightPanelOpen })),
  getThemeColor: () => themeColors[get().currentTheme],
}))