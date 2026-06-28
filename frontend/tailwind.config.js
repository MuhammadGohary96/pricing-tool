/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Page ground — calm cool-paper, biased toward the magenta accent.
        // Matches the landing page 1:1 so app and splash read as one product.
        paper: '#FAF8FC',
        'paper-2': '#F3EFF8',
        brand: {
          primary: '#a3007c',
          dark: '#7a005d',
          darkest: '#4d003a',
          light: '#d4a0c3',
          lightest: '#f3e3ed',
          tint: '#f7e9f2',
          wash: '#fbf3f8',
          50: '#fdf2f9',
        },
        grey: {
          900: '#111827',
          700: '#374151',
          500: '#6B7280',
          300: '#D1D5DB',
          200: '#E5E7EB',
          100: '#F3F4F6',
          50: '#F9FAFB',
        },
        action: {
          mapping: '#4d003a',
          ai: '#a3007c',
          update: '#d4a0c3',
          complete: '#f3e3ed',
        },
        success: '#10B981',
        warning: '#F59E0B',
        error: '#EF4444',
      },
      fontFamily: {
        sans: ['Geist', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"Geist Mono"', 'Consolas', 'Monaco', 'monospace'],
      },
      maxWidth: {
        dashboard: '1440px',
      },
      letterSpacing: {
        // Resolves the previously-undefined `tracking-tightish` used on display
        // headings across 8 files — a between-step tighter than `tracking-tight`.
        tightish: '-0.0125em',
      },
      transitionTimingFunction: {
        // Mirrors --ease-premium so `ease-premium` works as a utility class.
        premium: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      fontSize: {
        kpi: ['28px', { lineHeight: '1.1', fontWeight: '900' }],
        title: ['17px', { lineHeight: '1.3', fontWeight: '700' }],
        heading: ['18px', { lineHeight: '1.3', fontWeight: '700' }],
        subheading: ['14px', { lineHeight: '1.4', fontWeight: '700' }],
        body: ['13px', { lineHeight: '1.5' }],
        caption: ['12px', { lineHeight: '1.4' }],
        micro: ['11px', { lineHeight: '1.3' }],
      },
      borderRadius: {
        DEFAULT: '8px',
        lg: '12px',
        xl: '16px',
        '2xl': '20px',
      },
      boxShadow: {
        // Legacy aliases repointed to the tinted ink (rgba(40,16,48,…)) so every
        // un-migrated `shadow-card` usage de-blackens instantly; new panels should
        // use shadow-panel / shadow-panel-hover directly.
        card: '0 1px 2px rgba(40,16,48,0.05), 0 4px 14px -8px rgba(40,16,48,0.12)',
        'card-hover': '0 2px 4px rgba(40,16,48,0.06), 0 18px 44px -16px rgba(40,16,48,0.20)',
        dropdown: '0 4px 16px rgba(40,16,48,0.14)',
        toast: '0 8px 24px rgba(40,16,48,0.18)',
        // Premium tinted elevation — shadows carry the body's cool hue, not pure black.
        panel: '0 1px 2px rgba(40,16,48,0.05), 0 4px 14px -8px rgba(40,16,48,0.12)',
        'panel-hover': '0 2px 4px rgba(40,16,48,0.06), 0 18px 44px -16px rgba(40,16,48,0.20)',
        ring: '0 0 0 1px rgba(40,16,48,0.06)',
      },
    },
  },
  plugins: [],
}
