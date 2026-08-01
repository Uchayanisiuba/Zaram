// frontend/src/theme/presenceTheme.ts
//
// Shared color tokens for Presence Runtime states.
// All UI components read from this single source of truth.

export type PresenceState = 
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'SearchingMemory'
  | 'SearchingWeb'
  | 'Planning'
  | 'Speaking'
  | 'Learning'
  | 'Error'
  | 'Success'

export interface PresenceColorTokens {
  // Primary accent color for the state
  primary: string
  // Secondary accent color
  secondary: string
  // Glow/emission color
  glow: string
  // Subtle background accent
  backgroundAccent: string
  // Orb core color
  orbCore: string
  // Orb ring color
  ringColor: string
  // Particle color
  particleColor: string
}

// HSL-based color tokens for each presence state
// Using HSL for smooth interpolation during transitions
export const PRESENCE_COLORS: Record<PresenceState, PresenceColorTokens> = {
  Idle: {
    primary: 'hsl(220, 60%, 45%)',
    secondary: 'hsl(220, 50%, 35%)',
    glow: 'hsl(220, 70%, 50%)',
    backgroundAccent: 'hsl(220, 30%, 12%)',
    orbCore: 'hsl(220, 20%, 95%)',
    ringColor: 'hsl(220, 70%, 50%)',
    particleColor: 'hsl(220, 60%, 60%)',
  },
  Listening: {
    primary: 'hsl(180, 60%, 45%)',
    secondary: 'hsl(180, 50%, 35%)',
    glow: 'hsl(180, 70%, 55%)',
    backgroundAccent: 'hsl(180, 30%, 12%)',
    orbCore: 'hsl(180, 20%, 95%)',
    ringColor: 'hsl(180, 70%, 55%)',
    particleColor: 'hsl(180, 60%, 65%)',
  },
  Thinking: {
    primary: 'hsl(260, 60%, 50%)',
    secondary: 'hsl(260, 50%, 40%)',
    glow: 'hsl(260, 70%, 60%)',
    backgroundAccent: 'hsl(260, 30%, 12%)',
    orbCore: 'hsl(260, 20%, 95%)',
    ringColor: 'hsl(260, 70%, 60%)',
    particleColor: 'hsl(260, 60%, 70%)',
  },
  SearchingMemory: {
    primary: 'hsl(280, 60%, 50%)',
    secondary: 'hsl(280, 50%, 40%)',
    glow: 'hsl(280, 70%, 60%)',
    backgroundAccent: 'hsl(280, 30%, 12%)',
    orbCore: 'hsl(280, 20%, 95%)',
    ringColor: 'hsl(280, 70%, 60%)',
    particleColor: 'hsl(280, 60%, 70%)',
  },
  SearchingWeb: {
    primary: 'hsl(45, 90%, 55%)',
    secondary: 'hsl(45, 80%, 45%)',
    glow: 'hsl(45, 90%, 65%)',
    backgroundAccent: 'hsl(45, 40%, 12%)',
    orbCore: 'hsl(45, 20%, 95%)',
    ringColor: 'hsl(45, 90%, 65%)',
    particleColor: 'hsl(45, 80%, 75%)',
  },
  Planning: {
    primary: 'hsl(270, 60%, 45%)',
    secondary: 'hsl(270, 50%, 35%)',
    glow: 'hsl(270, 70%, 55%)',
    backgroundAccent: 'hsl(270, 30%, 12%)',
    orbCore: 'hsl(270, 20%, 95%)',
    ringColor: 'hsl(270, 70%, 55%)',
    particleColor: 'hsl(270, 60%, 65%)',
  },
  Speaking: {
    primary: 'hsl(150, 60%, 45%)',
    secondary: 'hsl(150, 50%, 35%)',
    glow: 'hsl(150, 70%, 55%)',
    backgroundAccent: 'hsl(150, 30%, 12%)',
    orbCore: 'hsl(150, 20%, 95%)',
    ringColor: 'hsl(150, 70%, 55%)',
    particleColor: 'hsl(150, 60%, 65%)',
  },
  Learning: {
    primary: 'hsl(60, 60%, 60%)',
    secondary: 'hsl(60, 50%, 50%)',
    glow: 'hsl(60, 70%, 70%)',
    backgroundAccent: 'hsl(60, 30%, 15%)',
    orbCore: 'hsl(60, 20%, 98%)',
    ringColor: 'hsl(60, 70%, 70%)',
    particleColor: 'hsl(60, 60%, 80%)',
  },
  Error: {
    primary: 'hsl(0, 60%, 50%)',
    secondary: 'hsl(0, 50%, 40%)',
    glow: 'hsl(0, 70%, 60%)',
    backgroundAccent: 'hsl(0, 30%, 12%)',
    orbCore: 'hsl(0, 20%, 95%)',
    ringColor: 'hsl(0, 70%, 60%)',
    particleColor: 'hsl(0, 60%, 70%)',
  },
  Success: {
    primary: 'hsl(120, 60%, 45%)',
    secondary: 'hsl(120, 50%, 35%)',
    glow: 'hsl(120, 70%, 55%)',
    backgroundAccent: 'hsl(120, 30%, 12%)',
    orbCore: 'hsl(120, 20%, 95%)',
    ringColor: 'hsl(120, 70%, 55%)',
    particleColor: 'hsl(120, 60%, 65%)',
  },
}

// CSS variable names for each token
export const PRESENCE_CSS_VARS = {
  primary: '--presence-primary',
  secondary: '--presence-secondary',
  glow: '--presence-glow',
  backgroundAccent: '--presence-bg-accent',
  orbCore: '--presence-orb-core',
  ringColor: '--presence-ring-color',
  particleColor: '--presence-particle-color',
} as const

// Transition duration for theme changes (300-600ms as specified)
export const THEME_TRANSITION_DURATION = '400ms'

// Helper to apply presence colors to CSS custom properties
export function applyPresenceTheme(root: HTMLElement, state: PresenceState): void {
  const colors = PRESENCE_COLORS[state]
  if (!colors) return

  Object.entries(colors).forEach(([key, value]) => {
    const cssVar = PRESENCE_CSS_VARS[key as keyof typeof PRESENCE_CSS_VARS]
    if (cssVar) {
      root.style.setProperty(cssVar, value)
    }
  })

  // Also set a data attribute for CSS selectors
  root.dataset.presenceState = state
}

// Helper to get color value for a state (for non-CSS usage like canvas)
export function getPresenceColor(state: PresenceState, token: keyof PresenceColorTokens): string {
  return PRESENCE_COLORS[state]?.[token] || PRESENCE_COLORS.Idle[token]
}

// Interpolate between two HSL colors for smooth transitions
export function interpolateHSL(
  colorA: string,
  colorB: string,
  t: number
): string {
  const parseHSL = (color: string) => {
    const match = color.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/)
    if (!match) return { h: 0, s: 0, l: 0 }
    return {
      h: parseInt(match[1], 10),
      s: parseInt(match[2], 10),
      l: parseInt(match[3], 10),
    }
  }

  const a = parseHSL(colorA)
  const b = parseHSL(colorB)

  // Shortest path for hue interpolation
  let hDiff = b.h - a.h
  if (hDiff > 180) hDiff -= 360
  if (hDiff < -180) hDiff += 360

  const h = Math.round((a.h + hDiff * t + 360) % 360)
  const s = Math.round(a.s + (b.s - a.s) * t)
  const l = Math.round(a.l + (b.l - a.l) * t)

  return `hsl(${h}, ${s}%, ${l}%)`
}