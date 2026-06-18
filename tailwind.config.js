/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        navy: '#1B2A7B',
        'navy-light': '#2D3F9E',
        'navy-dark': '#111D5E',
        orange: '#E8541A',
        'orange-light': '#F06A30',
        'light-blue': '#5DADE2',
        'light-blue-soft': '#D6EAF8',
        gold: '#F5C518',
      },
    },
  },
  plugins: [],
}
