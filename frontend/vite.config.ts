import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El servidor real (FastAPI) corre en :8000, este dev server en :5173.
// El proxy hace que el navegador solo hable con :5173 -- todo pedido a
// /api o /login se reenvía a :8000 del lado del servidor de Vite, así
// que la cookie de sesión queda como same-origin de verdad, sin
// depender de la configuración de SameSite/CORS del navegador.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // GET /me (sesión real, ver App.tsx/api/client.ts::fetchMe) --
      // sin esto, el pedido cae en el fallback de SPA de Vite y
      // devuelve el index.html en vez de JSON (bug real, encontrado
      // probando esto contra el servidor de verdad).
      '/me': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /logout (menú de usuario) y GET /alerts/open (dropdown
      // de la campana de notificaciones) -- mismos endpoints reales
      // que ya usa la consola Jinja2, no se creó nada nuevo.
      '/logout': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/alerts': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Reusa los logos reales del servidor (server/static/) en vez de
      // duplicarlos en el proyecto React -- un solo archivo fuente.
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
