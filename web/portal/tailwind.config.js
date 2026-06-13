/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'monospace'],
      },
      colors: {
        brand: { 50: '#f0f4ff', 100: '#e0e9ff', 200: '#c2d4ff', 300: '#94b4ff', 400: '#5e8bff', 500: '#3b6ef5', 600: '#2a52d8', 700: '#2240b0', 800: '#1f368e', 900: '#1e3072' },
        ink: { 50: '#f6f7f9', 100: '#eceef2', 200: '#d5d9e2', 300: '#b0b8c8', 400: '#8591a8', 500: '#66728a', 600: '#525b70', 700: '#444b5c', 800: '#3a3f4d', 900: '#1e2128', 950: '#0f1115' },
      },
    },
  },
  plugins: [],
};
