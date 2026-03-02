/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#a3007c',
          dark: '#7a005d',
          darkest: '#4d003a',
          light: '#d4a0c3',
          lightest: '#f3e3ed',
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
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['Consolas', 'Monaco', 'monospace'],
      },
      maxWidth: {
        dashboard: '1440px',
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
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)',
        dropdown: '0 4px 16px rgba(0,0,0,0.12)',
        toast: '0 8px 24px rgba(0,0,0,0.15)',
      },
    },
  },
  plugins: [],
}
