import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import https from 'node:https'
import path from 'node:path'

// --- HTTPS (ver server/TLS_README.md) ---------------------------------
// El backend solo escucha por HTTPS (server/run_server.py). El proxy de
// Vite se conecta a él verificando el certificado contra la CA propia
// de ALFA-Sentinel (server/certs/ca.crt) -- no se desactiva la
// verificación (secure: false). Si existen los certificados, el propio
// dev server de Vite también sirve por HTTPS, así la cookie de sesión
// (Secure) nunca viaja en claro entre el navegador y Vite.
const certsDir = path.resolve(import.meta.dirname, '../server/certs')
const caFile = path.join(certsDir, 'ca.crt')
const certFile = path.join(certsDir, 'server.crt')
const keyFile = path.join(certsDir, 'server.key')
const hasCerts = [caFile, certFile, keyFile].every((f) => fs.existsSync(f))

const BACKEND_URL = process.env.ALFA_BACKEND_URL ?? 'https://localhost:8000'

const backend = {
  target: BACKEND_URL,
  changeOrigin: true,
  secure: true,
  ...(BACKEND_URL.startsWith('https:') && fs.existsSync(caFile)
    ? { agent: new https.Agent({ ca: fs.readFileSync(caFile), minVersion: 'TLSv1.2' as const }) }
    : {}),
}

// El servidor real (FastAPI) corre en https://:8000, este dev server en :5173.
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
    https: hasCerts
      ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }
      : undefined,
    proxy: {
      '/api': {
        ...backend,
      },
      // POST /login (formulario de LoginGate.tsx) -- único método real
      // que queda acá (GET /login, la página Jinja2, se eliminó). Nada
      // en la app arma un link a "/login" como URL propia -- LoginGate
      // se muestra como componente in-place, no por ruta -- así que en
      // uso normal esto no se pisa con el fallback de SPA.
      '/login': {
        ...backend,
      },
      // GET /me (sesión real, ver App.tsx/api/client.ts::fetchMe) --
      // sin esto, el pedido cae en el fallback de SPA de Vite y
      // devuelve el index.html en vez de JSON (bug real, encontrado
      // probando esto contra el servidor de verdad).
      '/me': {
        ...backend,
      },
      // POST /logout (menú de usuario).
      '/logout': {
        ...backend,
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
        ...backend,
      },
      // PATCH/POST /incidents/... (drawer de Incidentes: cambiar
      // estado, responsable, clasificación, escalar una alerta suelta,
      // aislar manualmente) -- no colisiona con la página "Incidentes"
      // (esa vive en /incidentes, en español).
      '/incidents': {
        ...backend,
      },
      // POST /host-isolations/{id}/release (liberar un aislamiento ya
      // ejecutado, botón "Liberar" en la pantalla Respuesta, 2026-08-17,
      // ver PENDIENTES.md, "Aislamiento de host -- modo development,
      // laboratorio y producción") -- sin esto el request caía en el
      // fallback de SPA de Vite (204/index.html) en vez de llegar al
      // servidor real, mismo tipo de bug que ya pasó con /alerts.
      '/host-isolations': {
        ...backend,
      },
      // PATCH /rules/{id} (pantalla Reglas Heurísticas: peso/estado).
      '/rules': {
        ...backend,
      },
      // POST /reportes/generar y GET /reportes/{id}/archivo (pantalla
      // Reports: generar y descargar). A diferencia del resto, esto NO
      // se puede proxear por prefijo ("/reportes") porque colisiona
      // con la página React del mismo nombre -- un refresh en
      // /reportes tiene que caer en la SPA, no en el servidor.
      '^/reportes/generar$': {
        ...backend,
      },
      '^/reportes/\\d+/archivo$': {
        ...backend,
      },
      // POST /users, PATCH /users/{id} (Administración > Usuarios y
      // Roles).
      '/users': {
        ...backend,
      },
      // PATCH /settings/{key} (Administración > Configuración).
      '/settings': {
        ...backend,
      },
      // POST /enrollment-tokens (Administración > Agentes: generar
      // token de enrolamiento) -- endpoint real ya existente.
      '/enrollment-tokens': {
        ...backend,
      },
      // Reusa los logos reales del servidor (server/static/) en vez de
      // duplicarlos en el proyecto React -- un solo archivo fuente.
      '/static': {
        ...backend,
      },
    },
  },
})
