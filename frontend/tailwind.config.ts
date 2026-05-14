import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './hooks/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // FinAlly palette per PLAN §2
        bg: {
          DEFAULT: '#0d1117',
          alt: '#1a1a2e',
          panel: '#161b22',
          panelAlt: '#1f2536',
          border: '#2a2f3a',
        },
        accent: {
          yellow: '#ecad0a',
          blue: '#209dd7',
          purple: '#753991',
        },
        flash: {
          up: 'rgba(34, 197, 94, 0.35)',
          down: 'rgba(239, 68, 68, 0.35)',
        },
        // Semantic
        up: '#22c55e',
        down: '#ef4444',
        muted: '#8b96a8',
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};

export default config;
