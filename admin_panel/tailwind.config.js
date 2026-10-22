/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,jsx}',
    './src/components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#FFF6ED',
          100: '#FFEBD4',
          200: '#FFD4A8',
          300: '#FFB56B',
          400: '#FF9A3C',
          500: '#FF861F',
          600: '#E86E00',
          700: '#C45C00',
          800: '#9A4800',
          900: '#7A3900',
        },
        sidebar: {
          bg: '#202D70',
          hover: '#34338A',
          active: '#141B4D',
        },
      },
    },
  },
  plugins: [],
};
