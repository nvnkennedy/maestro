/** @type {import('tailwindcss').Config} */
const withAlpha = (variable) => `rgb(var(${variable}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: withAlpha('--color-primary'),
        secondary: withAlpha('--color-secondary'),
        success: withAlpha('--color-success'),
        warning: withAlpha('--color-warning'),
        error: withAlpha('--color-error'),
        info: withAlpha('--color-info'),
        background: withAlpha('--color-background'),
        surface: withAlpha('--color-surface'),
        'surface-2': withAlpha('--color-surface-2'),
        border: withAlpha('--color-border'),
        'text-primary': withAlpha('--color-text-primary'),
        'text-secondary': withAlpha('--color-text-secondary'),
        'text-muted': withAlpha('--color-text-muted'),
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
