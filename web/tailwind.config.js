/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        chimera: {
          50: '#f0f4ff',
          100: '#dbe4ff',
          200: '#bac8ff',
          300: '#91a7ff',
          400: '#748ffc',
          500: '#5c7cfa',
          600: '#4c6ef5',
          700: '#4263eb',
          800: '#3b5bdb',
          900: '#364fc7',
        },
        platform: {
          instagram: '#E4405F',
          telegram: '#0088CC',
          facebook: '#1877F2',
          tiktok: '#FE2C55',
          twitter: '#000000',
          linkedin: '#0A66C2',
          vk: '#4C75A3',
          youtube: '#FF0000',
          reddit: '#FF4500',
          threads: '#101010',
        },
      },
    },
  },
  plugins: [],
}
