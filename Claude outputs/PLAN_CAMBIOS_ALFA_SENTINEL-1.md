# Plan de cambios: ALFA-Sentinel

**Plataformas:** el sistema se desarrolla para **Windows y Linux**. Cada cambio en el agente (rutas, firewall, servicio, permisos) debe cubrir los dos sistemas.

**Rama de trabajo:** `funcionalidades`. No se hace push sin pedirlo.
**Autor de los commits:** `aldahirfernandez <aldahirfernandez27@gmail.com>`.
**Git desde la VM de Cowork:** usar siempre `git -c core.autocrlf=true`. El repositorio usa CRLF; sin esa opción, todos los archivos aparecen como modificados.

---

## ✅ 1. Protocolo HTTPS (HECHO)

Commits `6c2771a` y `937edb6` en `funcionalidades`.

- `server/generar_certificados.py`: crea la CA propia y el certificado del servidor, y copia `ca.crt` a `agent/certs/`.
- `server/run_server.py`: levanta uvicorn solo con TLS ≥ 1.2. `--insecure-dev` escucha solo en 127.0.0.1. Filtra el falso error `WinError 10054` de asyncio en Windows.
- `server/main.py`: cookie de sesión `Secure` + `SameSite=Strict` y cabeceras de seguridad (HSTS, nosniff, X-Frame-Options, no-store).
- `agent/transport.py`: HTTPS obligatorio (http solo hacia loopback), confía solo en la CA propia, verifica nombre/IP y exige TLS ≥ 1.2.
- `agent/main.py`: opción `--ca`, y valida el canal antes de enviar el token o la credencial.
- `frontend/vite.config.ts`: el proxy va a `https://localhost:8000` verificando la CA, y el dev server usa HTTPS.
- Guía: `server/TLS_README.md`.
- Probado: servidor en la laptop y agente en la VM Ubuntu (`192.168.81.1`) comunicándose.

## ✅ 2. Estado ONLINE / OFFLINE (HECHO)

Parche aplicado; además se unificó `/api/respuesta/*` (asgi.py), "Endpoints en riesgo" del dashboard y las etiquetas de todos los drawers. Verificado con `tsc -b` y contra la base local.

**Problema:** el heartbeat pone `agents.status = 'ONLINE'` y nada lo vuelve a poner en `OFFLINE`, así que los equipos apagados aparecen en línea. Además, cada pantalla usaba una regla distinta (solo `status`, 30 s fijos o `agent_stale_seconds`).

**Decisión tomada:**

- Una sola columna, **Estado**, con tres valores:
  - **En línea:** último heartbeat hace menos de `agent_stale_seconds` (120 s por defecto, configurable).
  - **Sin comunicación:** heartbeat vencido o nunca recibido. No se supone la causa: puede ser un apagado, la red o un agente neutralizado.
  - **Aislado:** hay un aislamiento vigente. Tiene prioridad sobre los otros dos.
- Se elimina la columna "Agente" (Healthy/Warning/Offline): medía la misma señal y confundía.
- No se agrega "Último reporte", porque ya existe la columna "Última conexión".

**Servidor (listo y probado en PostgreSQL 16):** archivo `patch_server.py`, en la raíz del repositorio. Se aplica con `python patch_server.py server/main.py` desde la raíz. El script falla con `AssertionError` si algún fragmento no coincide exactamente una vez, así que no deja el archivo a medias.

- Helpers `agent_online_sql()`, `is_agent_online()` y `mark_stale_agents_offline()`.
- Hilo de barrido cada 10 s (evento startup) que pasa a OFFLINE los agentes vencidos.
- Sitios unificados: `_endpoint_cte`, detalle del endpoint (devuelve `conn_status` en lugar de `agent_health`), honeyfiles (antes 30 s fijos), dashboard, detalle del incidente, reporte ("Sin comunicación") y `/api/endpoints` (sin `agent_health`).
- Corrige también el dashboard: un equipo aislado contaba como online y se restaba dos veces de offline.

**Después de aplicar el parche, verificar:**

- `python -m py_compile server/main.py`.
- Que `asgi.py` no reemplace en tiempo de ejecución las rutas modificadas (`/api/endpoints`, detalle del endpoint, dashboard). Si lo hace, aplicar la misma regla allí.

**Frontend (pendiente):**

- `EndpointsTable.tsx`: quitar la columna "Agente".
- `frontend/src/lib/endpointStatus.ts`: cambiar las etiquetas Online → "En línea", Offline → "Sin comunicación" y mantener "Aislado"; quitar `AGENT_HEALTH_*`.
- Detalle (drawer) del endpoint: usar `conn_status`.
- Buscar y actualizar todo uso de `agent_health` / `AgentHealth` / `Healthy` / `Warning` / `is_agent_live` en `frontend/src` (incluidos los tipos).
- Verificar con `node node_modules/typescript/bin/tsc -b` y hacer el commit.

## ✅ 3. Proteger el servidor frente al equipo infectado (HECHO, salvo el opcional)

Implementado en `server/hardening.py` + `main.py`/`asgi.py`/`database.py`. Probado contra una copia del servidor y contra la base (sin escribir). Pendiente: alerta automática cuando un agente pasa a "Sin comunicación" (opcional, a decidir). **Recordatorio:** la contraseña vieja de la base (`220922`) sigue en el historial de git; conviene cambiarla en PostgreSQL y en `server/.env`.

Plan original:

- Límite de volumen por agente en `/agent/events`, `/agent/alerts` y heartbeat, para evitar que inunden la base.
- Validación estricta del cuerpo: tamaños máximos de campos y del body, y rechazo de valores extraños.
- Agente aislado en cuarentena: solo heartbeat y reportes, sin cambios de configuración.
- El servidor no arranca con el `SESSION_SECRET` por defecto (`"cambia-esto-en-produccion"`).
- Quitar la contraseña de la base escrita por defecto en `server/database.py` (`postgres:220922`).
- Login: límite de intentos fallidos y bloqueo temporal.
- Opcional: generar una alerta cuando un agente pasa a "Sin comunicación", como posible neutralización.

## ✅ 4. Monitoreo (se mantiene en las 6 carpetas principales; ahora se encuentran sin HOME y con su nombre real)

- Hoy solo se vigilan 6 carpetas del perfil: Documents, Desktop, Downloads, Pictures, Videos y Music.
- Falta cubrir otras unidades y carpetas compartidas, excluyendo las rutas del sistema:
  - **Windows:** otras unidades (D:, USB) y los perfiles de `C:\Users\*`; excluir `C:\Windows`, `Program Files` y `ProgramData`.
  - **Linux:** `/home/*`, `/media` y `/mnt`, y los montajes de red; excluir `/proc`, `/sys`, `/dev`, `/usr`, `/boot` y similares.
- Las rutas salen de `expanduser("~")`: si el agente corre como servicio (SYSTEM en Windows, root en Linux) o con otra cuenta, vigila el perfil equivocado.

## ✅ 5. Creación de archivos señuelo (HECHO: archivos reales, 3+ por carpeta, a nombre del usuario)

- Revisar dónde y cómo se crean y su relación con el punto 6 (propietario y permisos cuando el agente corre como administrador o root).

## ✅ 6. Aislamiento y permisos de administrador (HECHO)

- Aislamiento: solo la conexión TCP del agente al puerto de ALFA_SENTINEL; reglas previas anuladas; firewall original restaurado al liberar (Windows y Linux). Commit `f865adf`.
- Permisos: opción A -- el agente sigue privilegiado (como un EDR) y lo que crea toma el dueño de la carpeta que lo contiene; nunca sigue enlaces simbólicos. Separar privilegios (opción B) queda como recomendación a futuro.
- Falta probar un aislamiento REAL en la VM Ubuntu y en un Windows de prueba.

Plan original:

- Hoy aislar exige ejecutar el agente como administrador o root, y entonces los archivos creados por el usuario normal no se pueden modificar. Hay que separar privilegios: por ejemplo, un servicio con privilegios solo para el firewall y el resto con el usuario.
- **Windows:** al liberar se configura `allowinbound,allowoutbound`. Lo normal en Windows es bloquear las conexiones entrantes, así que el equipo queda más expuesto que antes. Hay que guardar la política original y restaurarla.
- **Linux:** revisar que el aislamiento (iptables/nftables) también guarde las reglas originales y las restaure al liberar.

## ✅ 7. Interfaz de instalación (HECHO: asistente en consola; instalador gráfico/ejecutable queda como recomendación)

- Hoy la instalación es con comandos en la terminal. Hacer un instalador o asistente que registre el agente con el código XXXX-XXXX, copie `ca.crt` y lo instale como servicio: servicio de Windows en Windows y unidad systemd en Linux.

## ⏳ 8. Eventos

- Revisar la parte de eventos (pantalla y procesamiento). El alcance está por definir con el usuario.

## ⏳ 9. Otros hallazgos

- Autoprotección del agente: `agent_credential.json` está en texto plano, y el proceso se puede matar sin que nadie se entere.
- `server/main.py` tiene unas 7.800 líneas y `asgi.py` reemplaza rutas de `main.py` en tiempo de ejecución, con riesgo de editar la versión equivocada.
- Repositorio: `server/generated_reports/`, `__pycache__` y `PENDIENTES.md` (310 KB) conviene ignorarlos o limpiarlos.
