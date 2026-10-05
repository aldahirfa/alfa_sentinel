/** @type {import('tailwindcss').Config} */
// Antes Tailwind se cargaba desde cdn.tailwindcss.com y, sin internet,
// la consola quedaba sin estilos. Ahora se compila localmente con Vite.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        base: {
          950: '#0b0f19',
          900: '#0f1420',
          850: '#131926',
          800: '#171f2e',
          700: '#232c3d',
          600: '#333f54',
        },
      },
    },
  },
  plugins: [],
}
