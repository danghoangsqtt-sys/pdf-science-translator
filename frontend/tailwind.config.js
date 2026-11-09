/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        // Short windows (projectors at 1024x768 and below): trim chrome so
        // the PDF keeps most of the height.
        short: { raw: '(max-height: 760px)' },
      },
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
