/**
 * =================================================================================================
 * ZARAM DESIGN TOKENS — Project A Visual Language
 *
 * Deep-space dark theme: #080a0e base, indigo/cyan/purple accent palette.
 * Source of truth for fonts, colors, radii, shadows, and motion.
 * =================================================================================================
 */

// =================================================================================================
// COLORS
// =================================================================================================
export const colors = {
  // Brand / Presence
  presence: {
    primary:   '#6366f1',  // indigo-500
    secondary: '#c084fc',  // purple-400
    glow:      'rgba(99, 102, 241, 0.45)',
    accent:    '#22d3ee',  // cyan-400
    core:      '#f1f5f9',  // slate-100
  },

  // Neutral — slate scale
  neutral: {
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
  },

  // Semantic
  semantic: {
    success: '#34d399',  // emerald-400
    warning: '#fbbf24',  // amber-400
    error:   '#ef4444',  // red-500
    info:    '#22d3ee',  // cyan-400
  },

  // Glass surfaces
  glass: {
    background: 'rgba(6, 7, 9, 0.80)',
    backgroundLight: 'rgba(255, 255, 255, 0.04)',
    border:     'rgba(255, 255, 255, 0.08)',
    borderHover:'rgba(255, 255, 255, 0.14)',
  },

  // Orb state
  orb: {
    idle:      'rgba(99,  102, 241, 0.45)',
    listening: 'rgba(34,  211, 238, 0.65)',
    thinking:  'rgba(168,  85, 247, 0.65)',
    speaking:  'rgba(16,  185, 129, 0.55)',
  },

  transparent: 'transparent',
  background: '#08080f',
};

// =================================================================================================
// TYPOGRAPHY
// =================================================================================================
export const typography = {
  fontFamily: {
    // "… Variable" first — that is the family @fontsource-variable registers.
    // The bare names stay behind it for machines with the static family
    // installed. See the note in index.css about why these ship in the bundle.
    display: ["'Space Grotesk Variable'", "'Space Grotesk'", "'Inter Variable'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
    sans: ["'Inter Variable'", "'Inter'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
    mono: ["'JetBrains Mono Variable'", "'JetBrains Mono'", 'ui-monospace', 'monospace'],
  },
  fontSize: {
    xs:   '0.75rem',
    sm:   '0.875rem',
    base: '1rem',
    lg:   '1.125rem',
    xl:   '1.25rem',
    '2xl':'1.5rem',
    '3xl':'1.875rem',
    '4xl':'2.25rem',
    '5xl':'3rem',
  },
  fontWeight: {
    light:    '300',
    normal:   '400',
    medium:   '500',
    semibold: '600',
    bold:     '700',
  },
  letterSpacing: {
    tight:  '-0.025em',
    normal: '0em',
    wide:   '0.025em',
    wider:  '0.05em',
    widest: '0.1em',
  },
};

// =================================================================================================
// SPACING — 4px grid
// =================================================================================================
export const spacing = {
  '0':    '0',
  'px':   '1px',
  '0.5':  '0.125rem',
  '1':    '0.25rem',
  '1.5':  '0.375rem',
  '2':    '0.5rem',
  '2.5':  '0.625rem',
  '3':    '0.75rem',
  '3.5':  '0.875rem',
  '4':    '1rem',
  '5':    '1.25rem',
  '6':    '1.5rem',
  '8':    '2rem',
  '10':   '2.5rem',
  '12':   '3rem',
  '16':   '4rem',
  '20':   '5rem',
  '24':   '6rem',
  '32':   '8rem',
};

// =================================================================================================
// RADII
// =================================================================================================
export const radius = {
  none: '0',
  sm:   '0.375rem',
  DEFAULT: '0.75rem',
  lg:   '0.75rem',
  xl:   '1rem',
  '2xl':'1.5rem',
  full: '9999px',
};

// =================================================================================================
// EFFECTS
// =================================================================================================
export const effects = {
  shadow: {
    sm:      '0 1px 2px 0 rgba(0,0,0,0.3)',
    DEFAULT: '0 2px 8px 0 rgba(0,0,0,0.4)',
    md:      '0 4px 16px rgba(0,0,0,0.4)',
    lg:      '0 8px 32px rgba(0,0,0,0.5)',
    xl:      '0 16px 48px rgba(0,0,0,0.6)',
    '2xl':   '0 24px 64px rgba(0,0,0,0.7)',
    inner:   'inset 0 2px 4px 0 rgba(0,0,0,0.3)',
    glow:    '0 0 32px rgba(99,102,241,0.4)',
    glowCyan:'0 0 32px rgba(34,211,238,0.4)',
  },
  blur: {
    sm:    '4px',
    DEFAULT:'8px',
    md:    '12px',
    lg:    '16px',
    xl:    '24px',
    '2xl': '40px',
  },
};

// =================================================================================================
// MOTION
// =================================================================================================
export const motion = {
  duration: {
    '75':   '75ms',
    '100':  '100ms',
    '150':  '150ms',
    '200':  '200ms',
    '300':  '300ms',
    '500':  '500ms',
    '700':  '700ms',
    '1000': '1000ms',
    fast:   '150ms',
    normal: '300ms',
    slow:   '500ms',
  },
  easing: {
    linear:     'linear',
    easeIn:     'cubic-bezier(0.4, 0, 1, 1)',
    easeOut:    'cubic-bezier(0, 0, 0.2, 1)',
    easeInOut:  'cubic-bezier(0.4, 0, 0.2, 1)',
    spring:     'cubic-bezier(0.34, 1.56, 0.64, 1)',
    in:         'cubic-bezier(0.4, 0, 1, 1)',
    out:        'cubic-bezier(0, 0, 0.2, 1)',
    inOut:      'cubic-bezier(0.4, 0, 0.2, 1)',
  },
};

// =================================================================================================
// SHELL LAYOUT
// =================================================================================================
export const shell = {
  navHeight:         40,
  railWidth:         56,
  railExpandedWidth: 224,
  rightPanelWidth:   280,
  dockHeight:        60,
};
