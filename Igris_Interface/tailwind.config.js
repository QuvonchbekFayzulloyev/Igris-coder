/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./web/**/*.{js,ts,jsx,tsx}",
    "./desktop/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'ui': ['IBM Plex Sans', 'sans-serif'],
        'mono': ['IBM Plex Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
