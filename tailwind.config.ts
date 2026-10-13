import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          0: 'var(--bg-0)',
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
        },
        line: {
          1: 'var(--line-1)',
          2: 'var(--line-2)',
          3: 'var(--line-3)',
        },
        txt: {
          1: 'var(--txt-1)',
          2: 'var(--txt-2)',
          3: 'var(--txt-3)',
        },
        blue: 'var(--blue)',
        'blue-hover': 'var(--blue-hover)',
        'blue-glow': 'var(--blue-glow)',
        green: 'var(--green)',
        amber: 'var(--amber)',
        red: 'var(--red)',
        purple: 'var(--purple)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
        display: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        modal: 'var(--shadow-modal)',
      },
      animation: {
        float: 'float 20s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
        breathe: 'breathe 4s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 8s ease-in-out infinite',
        'spin-slow': 'spin-slow 120s linear infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
