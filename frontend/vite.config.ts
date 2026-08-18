import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El servidor real (FastAPI) corre en :8000, este dev server en :5173.
// El proxy hace que el navegador solo hable con :5173 -- todo pedido a
// /api (y a las rutas reales listadas abajo) se reenvía a :8000 del
// lado del servidor de Vite, así que la cookie de sesión queda como
// same-origin de verdad, sin depender de la configuración de
// SameSite/CORS del navegador.
//
// React es hoy la única interfaz web (el frontend Jinja2 se eliminó
// completo, ver PENDIENTES.md) y maneja su propio ruteo client-side
// para /dashboard, /endpoints, /alertas, /incidentes, /honeyfiles,
// /reglas, /respuesta, /reportes, /administracion, /perfil (ver
// App.tsx::getInitialPage). Esas rutas NO se proxean acá a propósito:
// tienen que caer en el fallback de SPA de Vite (sirve index.html) y
// no en el servidor real, que ya no tiene una página que devolver ahí.
// Los prefijos de abajo son distintos de esos nombres de página
// justamente para no pisarlos (p.ej. /incidents en inglés vs
// /incidentes en español) -- la única excepción real era /reportes,
// que colisionaba con la página del mismo nombre; se resuelve con
// rutas exactas en vez de por prefijo.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /login (formulario de LoginGate.tsx) -- único método real
      // que queda acá (GET /login, la página Jinja2, se eliminó). Nada
      // en la app arma un link a "/login" como URL propia -- LoginGate
      // se muestra como componente in-place, no por ruta -- así que en
      // uso normal esto no se pisa con el fallback de SPA.
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
      // POST /logout (menú de usuario).
      '/logout': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // GET /alerts/open (dropdown de la campana de notificaciones) --
      // ruta EXACTA a propósito (regex, no prefijo): App.tsx reconoce
      // "/alerts" (sin acento) como alias en inglés de la página
      // "Alertas" (que vive en "/alertas"), así que un "/alerts" a
      // secas tiene que caer en el fallback de SPA de Vite, igual que
      // "/reportes" más abajo. Con un prefijo simple ("/alerts": {...})
      // Vite reenviaba CUALQUIER ruta que empezara con "/alerts" al
      // servidor real -- incluida esa página, que ahí no existe (el
      // backend solo tiene GET /alerts/open y GET /api/alerts) -> 404
      // real, encontrado en producción (ver PENDIENTES.md).
      '^/alerts/open$': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // PATCH/POST /incidents/... (drawer de Incidentes: cambiar
      // estado, responsable, clasificación, escalar una alerta suelta,
      // aislar manualmente) -- no colisiona con la página "Incidentes"
      // (esa vive en /incidentes, en español).
      '/incidents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /host-isolations/{id}/release (liberar un aislamiento ya
      // ejecutado, botón "Liberar" en la pantalla Respuesta, 2026-08-17,
      // ver PENDIENTES.md, "Aislamiento de host -- modo development,
      // laboratorio y producción") -- sin esto el request caía en el
      // fallback de SPA de Vite (204/index.html) en vez de llegar al
      // servidor real, mismo tipo de bug que ya pasó con /alerts.
      '/host-isolations': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // PATCH /rules/{id} (pantalla Reglas Heurísticas: peso/estado).
      '/rules': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /reportes/generar y GET /reportes/{id}/archivo (pantalla
      // Reports: generar y descargar). A diferencia del resto, esto NO
      // se puede proxear por prefijo ("/reportes") porque colisiona
      // con la página React del mismo nombre -- un refresh en
      // /reportes tiene que caer en la SPA, no en el servidor.
      '^/reportes/generar$': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/reportes/\\d+/archivo$': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /users, PATCH /users/{id} (Administración > Usuarios y
      // Roles).
      '/users': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // PATCH /settings/{key} (Administración > Configuración).
      '/settings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // POST /enrollment-tokens (Administración > Agentes: generar
      // token de enrolamiento) -- endpoint real ya existente.
      '/enrollment-tokens': {
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
