import type { Config } from 'tailwindcss';
import { colors, typography, spacing, radius, effects, motion } from './src/theme';

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: ['class'],
  theme: {
    extend: {
      colors: {
        // Neutral slate scale (used as slate-100 → slate-900)
        slate: colors.neutral,

        // Semantic
        ...colors.semantic,

        // Brand
        primary:     colors.presence.primary,
        accent:      colors.presence.accent,
        purple:      colors.presence.secondary,

        // Orb state
        orb: colors.orb,

        // Glass
        glass: {
          bg:     colors.glass.background,
          border: colors.glass.border,
        },

        // Presence
        presence: colors.presence,

        // Project B shadcn colors (CSS var references)
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',

        transparent: 'transparent',
      },
      borderRadius: {
        ...radius,
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: typography.fontFamily,
      fontSize:   typography.fontSize,
      fontWeight: typography.fontWeight,
      letterSpacing: typography.letterSpacing,
      spacing:    spacing,
      boxShadow:  effects.shadow,
      blur:       effects.blur,
      transitionDuration:       motion.duration,
      transitionTimingFunction: motion.easing,
    },
  },
  plugins: [],
} satisfies Config;
