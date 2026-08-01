// tailwind.config.ts
export default {
  content: ['./apps/desktop/renderer/**/*.{tsx,ts}'],
  theme: {
    extend: {
      colors: {
        bg: {
          deep: '#09090B',
          canvas: '#0F1115'
        },
        surface: {
          1: 'rgba(24, 26, 31, 0.7)',
          2: 'rgba(39, 42, 49, 0.8)'
        },
        orb: {
          idle: '#6366F1',
          listening: '#10B981',
          thinking: '#3B82F6',
          executing: '#F59E0B',
          error: '#EF4444'
        }
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      },
      backdropBlur: {
        '20': '20px'
      },
      animation: {
        'orb-breathe': 'breathe 4s ease-in-out infinite',
        'orb-ripple': 'ripple 1.5s ease-out infinite',
        'panel-open': 'panelOpen 200ms ease-out',
        'panel-close': 'panelClose 150ms ease-in'
      }
    }
  },
  plugins: []
}