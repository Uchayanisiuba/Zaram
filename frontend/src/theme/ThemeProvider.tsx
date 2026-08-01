// frontend/src/theme/ThemeProvider.tsx
//
// Theme provider that connects Presence Runtime state to CSS custom properties.
// Subscribes to PresenceRuntime events (not frame state) and applies theme transitions.

import { createContext, useContext, useEffect, ReactNode } from 'react'
import { usePresenceRuntime } from '@/context/PresenceContext'
import { applyPresenceTheme, type PresenceState } from './presenceTheme'

interface ThemeContextValue {
  currentState: PresenceState
  setState: (state: PresenceState) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { presenceState } = usePresenceRuntime()

  useEffect(() => {
    applyTheme(presenceState)
  }, [presenceState])

  const applyTheme = (state: PresenceState) => {
    const root = document.documentElement
    applyPresenceTheme(root, state)
  }

  const setState = (state: PresenceState) => {
    applyTheme(state)
  }

  return (
    <ThemeContext.Provider value={{ currentState: presenceState, setState }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function usePresenceTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('usePresenceTheme must be used within a ThemeProvider')
  }
  return context
}