/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/*.py',
    './apps/**/*.html',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        oliva: {
          50: '#F5F7F2',
          100: '#EAEFE3',
          200: '#D5DFC9',
          300: '#B6C7A2',
          400: '#8FA872',
          500: '#6B894B',
          600: '#4E5F36',
          700: '#3D4A2A',
          800: '#2A331D',
          900: '#1B2312',
          950: '#0F140A',
        },
        harvest: {
          50: '#FEFDF8',
          100: '#FDF9EB',
          400: '#DFBA56',
          500: '#C29B38',
          600: '#9E7C28',
        }
      }
    }
  },
  plugins: [],
}
