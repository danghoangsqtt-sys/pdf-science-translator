/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#14452F',
          hover: '#0f3624',
          light: '#e8f0ec',
        }
      }
    },
  },
  plugins: [],
}
