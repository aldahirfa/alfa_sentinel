# Pendientes técnicos

Registro de trabajo identificado pero diferido a propósito, para no perderlo. Cada entrada explica el problema real, por qué no se resolvió todavía, y el camino propuesto para cuando se retome.

## Convención de UI: no ocultar lo que falta, marcarlo (2026-08-12)

**Regla del proyecto, a partir de ahora:** cuando un mockup o diseño pide algo que todavía no existe (una columna, un campo del drawer, una categoría de filtro), no se saca de la pantalla sin dejar rastro -- se muestra deshabilitado o con un valor honesto tipo "No disponible" / "Pendiente", con tooltip explicando por qué. Sacar el elemento entero hace que el sistema se vea más incompleto de lo que es y, con el tiempo, se pierde el registro de que faltaba agregarlo. Esto es distinto de una decisión explícita de arquitectura ya conversada y aceptada (ej. la pérdida de notas/Responsable/Eventos relacionados al adoptar `alfa_sentinel` tal cual, decidida a propósito en la reestructuración de la base) -- esas sí quedan afuera del todo porque fue una elección consciente, no una omisión de apuro.

**Aplicado retroactivamente en Eventos (2026-08-12):** el filtro "Categoría" ahora también lista "⚡ Proceso" y "🛡️ Sistema" como opciones deshabilitadas (no eliminadas) con la razón en el propio texto; la tabla recuperó la columna "Riesgo" (marcada "— ver Detecciones", ya que el score vive en `alerts`, no en `events`); el drawer recuperó Proceso Padre (PPID), Línea de Comando, Hash del Ejecutable y Usuario Ejecutor como campos visibles marcados "Pendiente" (a diferencia de Proceso/PID, que si son columnas reales hoy siempre `NULL`, estos cuatro ni siquiera existen como columna en ningún lado todavía).

## Atribución de proceso en eventos de archivo

**Estado:** no implementado. `/procesos` sigue como placeholder; `events.process_id` y `events.process_name` existen en el schema pero siempre quedan `NULL`.

**Por qué:** `agent/file_monitor.py` usa `watchdog`, que se apoya en las notificaciones de sistema de archivos del SO (`ReadDirectoryChangesW` en Windows, `inotify` en Linux). Ninguna de las dos expone qué proceso originó un cambio -- es una limitación del SO, no de la librería. Por separado, `agent/process_monitor.py` (`get_running_processes()`, vía `psutil`) sí obtiene el listado de procesos en ejecución, pero `agent/main.py` solo lo imprime por consola (línea ~71) -- nunca se envía al servidor. `honeyfile_activations` (tabla con las mismas columnas de proceso) tampoco se llena nunca; nada hace `INSERT` ahí.

**Camino propuesto (dos partes independientes):**

1. **¿Qué proceso tocó este archivo?** -- requiere una fuente de datos distinta a watchdog:
   - **Windows:** Sysmon (Sysinternals) + lectura del canal `Microsoft-Windows-Sysmon/Operational` vía `pywin32` (`win32evtlog`), correlacionando `ProcessId`/`Image` con `TargetFilename`. Sysmon corre como servicio con privilegios elevados. Matiz importante: Sysmon está orientado sobre todo a `FileCreate` (Event ID 11), no tiene un evento de "escritura" tan granular como los `on_modified` actuales -- probablemente cambie la granularidad de lo que hoy reportamos, no es un reemplazo 1:1.
   - **Linux:** `auditd`, con reglas de auditoría sobre las rutas vigiladas (`auditctl -w /ruta -p wa`), parseando `/var/log/audit/audit.log` (o `ausearch`) para sacar `pid`/`comm`/`exe`.
   - El servidor ya está listo para recibir esto (`events.process_id`/`process_name` ya existen, `EventCreate` ya los acepta) -- todo el trabajo es del lado del agente.

2. **¿Qué proceso causó una detección específica?** -- depende de (1) y además requiere:
   - Cambiar `agent/heuristic_engine.py`: `FileActivityAnalyzer` hoy es una única ventana global por agente (cuenta archivos únicos sin distinguir proceso). Habría que llevar una ventana por proceso.
   - Agregar `process_id`/`process_name` a la tabla `alerts` (hoy no los tiene, a diferencia de `events`) -- cambio de schema vía `schema_updates.sql`.

**Decisión (2026-08-11):** queda documentado, se sigue con las secciones de UI que sí se pueden construir y verificar por completo ahora (Detecciones, Incidentes). Se retoma cuando haya tiempo dedicado a instrumentar el agente -- no es un fix rápido, es trabajo real de sistemas por SO que además hay que probar en máquinas reales (no se puede verificar desde este entorno).

---

## Alerta ↔ eventos que la dispararon

**Estado:** revertido (2026-08-12). Se había resuelto el 2026-08-11 con la tabla puente `alert_events`, pero esa tabla no existe en la nueva estructura `alfa_sentinel` (ver "Reestructuración de la base de datos" más abajo) y se decidió adoptar la nueva estructura tal cual, sin reintroducirla. `events` ya no tiene forma de vincularse a `alerts` -- "Eventos relacionados" en Detecciones y "Detección relacionada" en Eventos quedan sin datos reales que mostrar y hay que sacarlos de la UI (etapa 4 de la reestructuración).

**Camino propuesto si se retoma:** agregar de nuevo una tabla puente (mismo diseño que antes) o, más simple con `alerts.incident_id` ya presente, una columna `alerts.event_ids`-equivalente si algún día vuelve a hacer falta.

---

## Incidente ↔ detecciones que agrupa

**Estado:** revertido (2026-08-12). Se había resuelto el 2026-08-11 con la tabla puente `incident_alerts` (many-to-many). La nueva estructura `alfa_sentinel` usa en cambio `alerts.incident_id` como FK directa nullable -- un incidente puede tener varias alertas (`SELECT * FROM alerts WHERE incident_id = ...`), pero cada alerta pertenece como máximo a un solo incidente. Esto cubre el mismo caso de uso real que se venía usando (nunca se vinculó una detección a más de un incidente), así que no es una pérdida funcional -- es una simplificación válida. Lo que sí se pierde son `incident_notes` y `incidents.assigned_to`/`assigned_at`/`closed_by`/`updated_at` (Responsable), que no tienen equivalente en la nueva estructura y no se reintrodujeron (decisión explícita del autor).

**Lo que sigue afuera, igual que antes:** un incidente sigue ligado a un único endpoint (`incidents.agent_id`). "Respuesta asociada" sigue siendo nota honesta, no datos reales de `host_isolations`.

---

## Reestructuración de la base de datos (ransomware_detection → alfa_sentinel)

**Estado:** en curso (2026-08-12), por etapas: schema → agente → servidor → templates.

**Qué cambió el schema:** `agents` se separó en `endpoints` (host físico) + `agents` (instalación del agente en ese host); `event_types` y `severity_levels` pasaron de VARCHAR+CHECK a catálogos en tabla; `alerts.incident_id` reemplaza a la tabla puente `incident_alerts`; nueva tabla `agent_rule` para umbrales por agente (sin datos todavía, ver nota en `database/schema.sql`); nueva tabla `alert_rule` para registrar qué regla(s) dispararon cada alerta con su peso aplicado.

**Decisión explícita del autor (no fabricar, no dejar dato fantasma):** se adopta la estructura de 19 tablas tal cual se definió, sin reintroducir `alert_events`, `alert_notes`, `incident_notes`, `incident_alerts` ni `incidents.assigned_to`/`assigned_at`/`closed_by`/`updated_at`. Eso significa que, hasta que se decida lo contrario, ALFA-Sentinel no tiene: notas de analista en detecciones ni en incidentes, "Responsable" asignado a un incidente, ni "Eventos relacionados"/"Detección relacionada". La base se recreó desde cero (`alfa_sentinel`), sin migrar datos de `ransomware_detection`.

**Etapa 2 (agente) -- hecho (2026-08-12):** `agent/main.py` manda `os`/`agent_version` en vez de `operating_system`/`architecture` (nueva `config.AGENT_VERSION`); `agent/file_monitor.py` y `agent/heuristic_engine.py` ya no arman ni mandan `event_ids` ni `details` (sin destino en la nueva `alerts`). El agente sigue mandando `event_type`/`severity`/`rule_name` como strings -- la traducción a `event_type_id`/`severity_id`/`alert_rule` queda del lado del servidor (etapa 3), para no acoplar al agente a los ids internos de la base.

**Etapa 3 (servidor) -- hecho (2026-08-12):** `server/main.py` reescrito por completo: enrolamiento separa `endpoints`/`agents`; `report_event`/`report_alert` traducen `event_type`/`severity` a los catálogos nuevos (rechazan con 422 si el nombre no matchea, no inventan un id); `alert_rule` reemplaza a `alerts.rule_id`; `alerts.incident_id` reemplaza a `incident_alerts`; se sacaron los endpoints `PATCH /incidents/{id}/assign`, `POST /incidents/{id}/notes` y `POST /alerts/{id}/notes` (sin tabla destino). Se aprovechó la columna nueva `alerts.resolved_at` (no existía antes) para marcarla al cerrar/marcar falso positivo una detección, mismo criterio que `incidents.closed_at`.

**Pérdida adicional encontrada durante la etapa 3 (corolario de perder `alerts.details`):** "Honeyfile relacionado" en el detalle de una detección (cruce por `details->>'last_file'` contra `honeyfiles.file_path`) tampoco tiene de dónde salir más -- se saca junto con el resto.

**Hallazgo aparte, no de esta reestructuración:** `endpoints.html` tenía un "Host Drawer" con un botón de aislamiento que sí escribía en `host_isolations` (a diferencia del resto de la app, que lo muestra deshabilitado) y una dirección MAC inventada. Se corrigió en la etapa 3c: botón deshabilitado con el mismo tooltip honesto que Dashboard/Incidentes, MAC reemplazada por "No disponible". También se notó que `POST /api/enrollment-tokens` (usado por el modal de Endpoints) no exige rol admin, a diferencia de `POST /enrollment-tokens` -- queda sin tocar por estar fuera del alcance de esta reestructuración, pero debería unificarse.

**Falta (etapa 4):** adaptar templates para no mostrar secciones que dependían de lo eliminado -- notas (Detecciones/Incidentes), Responsable de incidente, Eventos relacionados/Detección relacionada, Honeyfile relacionado, `alerts.details` (file_count/último archivo) en Detecciones y Actividad reciente del dashboard, motor heurístico (ya no tiene severity/auto_isolate por regla). Se pausó (2026-08-12) para construir primero la funcionalidad de Honeyfiles pedida (ver más abajo); sigue pendiente.

**Corrección sobre lo registrado en la etapa 3e:** ese bloque decía que `honeyfiles_page` ya se había adaptado a `endpoints` -- no era cierto. `honeyfiles_page`, `GET /api/honeyfiles/{id}/detail` y `POST /api/honeyfiles/deploy` seguían consultando `agents.hostname`/`agents.operating_system`/`agents.ip_address`/`agents.architecture`, columnas que ya no existen en `agents` (viven en `endpoints`) -- se habrían roto contra la base nueva apenas alguien abriera `/honeyfiles`. Se corrigió recién ahora (2026-08-12), al construir la funcionalidad de plantillas. De paso se encontró que `JSONResponse` se usaba en varias rutas (`/api/honeyfiles/...`, el drawer de Endpoints) sin estar importado -- también corregido.

---

## Honeyfiles por plantilla (2026-08-12)

**Qué se construyó:** antes, el botón "Desplegar" del Wizard de Honeyfiles insertaba una fila directo en `honeyfiles` como si el archivo ya existiera en el endpoint elegido -- ningún agente recibía ninguna orden ni creaba nada, era el mismo tipo de dato ficticio que el toggle de aislamiento de red que se sacó de Endpoints en la etapa 3c. Se reemplazó por un flujo real de punta a punta:

1. `honeyfile_templates` (qué debería existir: nombre, tipo, ruta destino, plataforma, contenido, si se auto-despliega) y `agent_honeyfile_templates` (en qué agente concreto se aplica, con `status` PENDING/CREATED/FAILED) -- dos tablas nuevas en `database/schema.sql`.
2. El Wizard (`POST /api/honeyfiles/deploy`) ya no toca `honeyfiles`: crea la plantilla y, si se eligieron endpoints puntuales, filas `agent_honeyfile_templates` en PENDING. Si se marca "despliegue automático", no hace falta elegir endpoints -- se resuelve solo.
3. El agente pide su política en cada ejecución (`GET /agent/honeyfile-policy`, agente no tiene bucle en segundo plano hoy, así que "cada ejecución" es lo único posible). El servidor le devuelve lo pendiente de crear más lo que ya creó antes (para que sepa qué seguir vigilando), y de paso resuelve ahí mismo cualquier plantilla `auto_deploy=TRUE` que coincida con el SO de ese endpoint y todavía no le haya sido asignada -- perezoso a propósito, así una plantilla nueva alcanza a agentes que ya existían sin tener que sembrar filas por adelantado.
4. `agent/honeyfile_deployer.py` (nuevo) escribe en disco lo que falta y reporta el resultado (`POST /agent/honeyfile-policy/report`) con el sha256 real del contenido escrito. Recién ahí el servidor inserta la fila real en `honeyfiles`.
5. `agent/file_monitor.py` ahora también vigila (no recursivo) la carpeta de cada honeyfile que viva fuera de la carpeta desde donde corre el agente (ej. el Desktop del usuario) -- si no, watchdog nunca hubiera visto actividad ahí, porque el watch recursivo original solo cubre "." (la carpeta del agente). `agent/honeyfile_monitor.py` reconoce un honeyfile por ruta exacta conocida además del chequeo viejo por carpeta local `honeyfiles/` (se mantiene por compatibilidad).

**Decisiones de alcance, explícitas:**
- El contenido es texto plano guardado con la extensión elegida (`.xlsx`, `.docx`, etc.), no un archivo Office/PDF válido de verdad -- generar binarios reales requeriría sumar librerías nuevas al agente (`openpyxl`, `python-docx`...) y no aporta nada que la detección necesite (reacciona a que el archivo exista y se lo toque, no a que se abra bien en Word/Excel).
- La ruta de destino admite `%USERPROFILE%`, `$HOME` o `~` como marcador de "carpeta personal", que el agente resuelve con `os.path.expanduser("~")` en su propio SO. Si se elige plataforma "Todas" con una ruta con sintaxis de un solo SO (ej. `%USERPROFILE%\Desktop\` con barras invertidas), un agente Linux la va a crear igual, literal -- no hay traducción automática de separadores de ruta entre Windows y Linux. Para rutas realmente distintas por SO, hoy hay que crear dos plantillas (una por plataforma), no una sola marcada "Todas".
- No hay UI todavía para editar o desactivar una plantilla ya creada, ni para ver el estado PENDING/CREATED/FAILED por endpoint más allá del contador agregado en la cabecera de `/honeyfiles` -- si hace falta, es la siguiente extensión natural.

## Historial de cambios de estado de un incidente

**Estado:** no implementado. `incidents.status` guarda el valor actual nada más -- no hay registro de cuándo pasó de "Abierto" a "En investigación" o a "Contenido". La "Línea temporal" del incidente por eso solo muestra los hechos con fecha real disponible (detecciones generadas, apertura, asignación, cierre), no cada transición de estado intermedia.

**Camino propuesto:** una tabla `incident_status_history` (incident_id, status, changed_by, changed_at), poblada desde `PATCH /incidents/{id}/status` cada vez que cambia. Chico y mecánico, pero no se hizo ahora para no seguir agrandando el alcance de esta pasada.

---

## Unificación de Incidentes y Alertas + 2 reglas heurísticas nuevas + Responsable (2026-08-12)

**Qué se pidió:** rediseñar "Incidentes y Alertas" como centro de respuesta unificado (no una lista de eventos crudos como Eventos, sino anomalías correlacionadas), reintroducir "Responsable" de verdad (revirtiendo la decisión explícita de la reestructuración a `alfa_sentinel`), y definir reglas heurísticas nuevas además de las 2 existentes.

**Qué se construyó:**

1. **`/detecciones` (lista) redirige a `/incidentes`.** `COMBINED_CTE` unifica `incidents` (casos ya agrupados) con alertas sueltas (`alerts.incident_id IS NULL`) en una sola matriz, con un `status_bucket` calculado por `CASE` para poder filtrar/colorear parejo aunque los vocabularios de estado reales de cada tabla no coincidan -- el estado real de cada fila se sigue mostrando tal cual está guardado, no se renombra. `/detecciones/{id}` (detalle de una alerta puntual) sigue existiendo igual que antes.
2. **Drawer "Expediente"** (`GET /api/incidentes/{kind}/{id}/drawer`) sirve tanto un incidente como una alerta suelta, con una "Cadena de Evidencia" real: eventos + activaciones de honeyfile del mismo agente en una ventana de 5 min antes / 1 min después del momento en que se disparó -- no se inventa un paso de "ejecución de proceso" que el agente no reportó.
3. **`incidents.assigned_to`/`assigned_at` reintroducidos** (revierte la decisión de la reestructuración, a pedido explícito) con `PATCH /incidents/{incident_id}/assign` funcional de verdad, no como placeholder. `incident_notes` y `alert_notes` siguen sin reintroducirse -- no se pidieron, y los formularios de "Notas" que quedaban en `incidente_detail.html`/`deteccion_detail.html` apuntando a endpoints inexistentes (404 silencioso) se deshabilitaron con tooltip explicando por qué, en vez de dejarlos rotos.
4. **2 reglas heurísticas nuevas** en `agent/heuristic_engine.py` (`FileActivityAnalyzer`): `ransomware_extension_rename` (archivo renombrado a extensión conocida de ransomware -- `.locked`, `.encrypted`, `.enc`, etc. -- peso 70, 1 ocurrencia, ventana 30s) y `mass_deletion` (ráfaga de borrados, peso 40, 15 archivos, ventana 10s), sembradas en `heuristic_rules`. El motor ahora suma los pesos de todas las reglas que disparen a la vez (tope 100) y reporta la de mayor peso como `rule_name` -- el servidor (`AlertCreate`/`alert_rule`) sigue aceptando una sola regla por alerta, simplificación aceptada.
5. **Bug real encontrado de paso:** `agent/file_monitor.py` `on_moved` pasaba `event.src_path` (nombre viejo) en vez de `event.dest_path` (nombre nuevo) a `register_event` -- con eso, `ransomware_extension_rename` nunca hubiera podido dispararse, porque miraba la extensión del archivo antes del rename, no después. Corregido.

**No incluido a propósito:** correlación entre reglas y proceso que las originó (sigue dependiendo de "Atribución de proceso en eventos de archivo", más arriba, no resuelto). "Aislar Host"/"Terminar Proceso" siguen deshabilitados con el mismo motivo de siempre (el agente no tiene bucle de comandos remotos).

---

## Página de Reglas real (`/configuracion`, 2026-08-12)

**Qué se construyó:** reemplaza el placeholder anterior. Lista las 4 reglas de `heuristic_rules` con `peso`/`is_active`/`umbral`/`ventana` editables desde la consola (`PATCH /rules/{rule_id}`), más alertas vinculadas (30 días) y última vez disparada como referencia de solo lectura.

**Actualización (2026-08-13): `umbral`/`ventana` pasaron de solo lectura a editables de verdad.** Se agregó `GET /agent/rule-policy` (mismo patrón que ya existía para honeyfiles vía `GET /agent/honeyfile-policy`): el agente lo pide en cada ejecución y recibe `peso`/`umbral`/`ventana` de cada regla con `is_active = TRUE` en la base. `FileActivityAnalyzer` (`agent/heuristic_engine.py`) ganó un `classmethod` `from_policy()` que arma el analizador con esos valores en vez de los que tenía fijos en `__init__()`; si el pedido al servidor falla (sin red, servidor caído), cae en los valores por defecto de siempre con las 4 reglas activas, para que un problema de conectividad no deje al agente sin detectar nada. Una regla con `is_active = FALSE` directamente no viene en la política -- el agente deja de evaluarla por completo, no la evalúa igual con un umbral cualquiera. `agent/file_monitor.py::start_file_monitor()` y `agent/main.py` se actualizaron para pedir la política antes de levantar el monitor.

**Por qué antes no era así:** hasta este cambio, el agente arrancaba sin pedirle nada a ningún endpoint sobre umbral/ventana -- editarlos en la consola no hubiera cambiado la detección real, así que se dejaron deshabilitados con la razón explicada (ver historial de este archivo). El mecanismo de sincronización que faltaba ya está construido; sigue habiendo un límite real y explicado en la propia pestaña Agentes: el cambio se aplica recién en el próximo arranque del agente, no en caliente sobre un proceso ya corriendo, porque el agente sigue sin bucle en segundo plano.

**Verificado de punta a punta (2026-08-13):** pruebas unitarias de `FileActivityAnalyzer.from_policy()` (sin política -> valores por defecto con las 4 reglas activas; política parcial con `mass_deletion` desactivada -> esa regla no dispara aunque se fuerce el umbral por defecto; regla con parámetros nuevos del servidor -> dispara con el umbral bajado) y una corrida real con Postgres (`pgserver` + `TestClient`): `GET /agent/rule-policy` con credencial válida e inválida, `PATCH /rules/1` cambiando peso/umbral/ventana (200) y con umbral/ventana inválidos (422), desactivar `mass_deletion` y confirmar que desaparece de la política que ve el agente, y que las 2 acciones quedan en `audit_logs` con el detalle correcto.

**Lo que sigue sin construirse, a propósito:** `agent_rule` (excepciones por agente puntual) sigue vacía y sin código que la use -- esto sincroniza reglas globales, no overrides por endpoint. Tampoco hay generador de reglas nuevas genéricas (`+ Nueva Regla` sigue deshabilitado): cada regla sigue siendo código Python específico en `FileActivityAnalyzer`, no una fila de configuración arbitraria.

---

## Ventana flotante de alerta + reglas heurísticas sincronizadas (2026-08-13)

**Qué se pidió:** una notificación visible en cualquier pantalla de la consola cuando se detecta una alerta (no solo en la campanita), y que "por si acaso" las reglas heurísticas se puedan editar de verdad.

**Ventana flotante:** nueva, en `server/templates/base.html` (vive ahí, no en una vista puntual, para aparecer sin importar la pantalla). Reutiliza el mismo endpoint que ya alimentaba la campanita (`GET /alerts/open`), ahora consultado cada 5s en vez de 30s. Cada id de alerta que este navegador ya mostró como ventana flotante se guarda en `localStorage` (`alfa_seen_alert_ids`) para no repetir el aviso al navegar entre pantallas o recargar. La primera vez que se usa en un navegador, si ya había alertas `NEW` viejas en la base, se avisan todas juntas una sola vez -- después, solo las genuinamente nuevas. No es un socket ni push real, sigue siendo polling (ahora más seguido) -- suficiente para un demo o para el uso real de un analista con la consola abierta, no para miles de alertas por segundo.

**Reglas heurísticas editables:** ver la entrada de arriba ("Página de Reglas real") -- se agregó `GET /agent/rule-policy` y `FileActivityAnalyzer.from_policy()`, y ahora `umbral`/`ventana` son editables de verdad en Configuración, no solo `peso`/`is_active`.

---

## Reporte PDF de incidente (2026-08-12)

**Qué se construyó:** `GET /incidentes/{incident_id}/reporte.pdf`, generado en el momento con `reportlab` (agregado a `server/requirements.txt`). Incluye ficha del incidente, impacto, reglas heurísticas disparadas (con peso aplicado real), traza técnica/cadena de evidencia (mismo criterio de ventana que el drawer: eventos + activaciones de honeyfile del mismo endpoint) y resolución. El enlace ya existía en el drawer de `incidentes.html` (`btnPdfReport`), deshabilitado para alertas sueltas -- ahora apunta a un endpoint real para incidentes.

**Qué se muestra como "No disponible" en vez de inventarse:** proceso padre, línea de comando y usuario ejecutor (el agente no los reporta, ver "Atribución de proceso en eventos de archivo"); hash SHA-256 de un archivo cualquiera que no sea honeyfile (solo `honeyfiles.file_hash` guarda un hash real, calculado por el agente al crear el señuelo); historial de cambios de estado del incidente (no existe, ver sección de más arriba) y notas de analista (`incident_notes`/`alert_notes`, no reintroducidas).

---

## Bug real encontrado y corregido: resta de fechas naive/aware (2026-08-12)

**Qué pasaba:** `agents.last_seen_at` es `TIMESTAMPTZ` -- psycopg lo devuelve como `datetime` con timezone (aware). Ocho lugares distintos en `server/main.py` (el filtro Jinja `timeago`, usado en Dashboard/Honeyfiles y varias vistas más; el cálculo de conectividad en Dashboard, Honeyfiles ×2 y el drawer de Incidentes; y el conteo `agents_ok`/`agents_attention` en tres vistas) calculaban `datetime.now() - last_seen_at`, restando un `datetime` sin timezone (naive) de uno con timezone (aware). Python no permite esa resta -- revienta con `TypeError: can't subtract offset-naive and offset-aware datetimes` apenas hay un agente `ONLINE` real con `last_seen_at` seteado.

**Por qué no se había notado:** en todo lo probado manualmente hasta ahora no había un agente `ONLINE` con `last_seen_at` reciente al mismo tiempo que se visitaba una de esas ocho vistas. Se encontró recién al armar una base Postgres real (no solo `py_compile`/Jinja/`node --check`, que no ejecutan las consultas) y sembrar un agente `ONLINE` con `last_seen_at = CURRENT_TIMESTAMP` para probar de punta a punta la función de Reportes -- el error salió apenas se generó el primer "Informe de Actividad de Endpoints". Es la clase de bug que un demo o defensa de tesis con datos reales agarra al toque.

**Corrección:** las ocho ocurrencias en `server/main.py` (línea del filtro `time_ago`, Dashboard, Honeyfiles, Incidentes/drawer, y las tres vistas con el conteo `agents_ok`/`agents_attention`/`agent_status_bucket`) pasaron de `datetime.now()` a `datetime.now(last_seen_at.tzinfo)` -- toma el timezone del valor que ya vino de la base en vez de asumir uno. La consulta nueva de Reportes (`_gather_endpoints_report_data`) en cambio calcula "en línea" del lado de SQL (`agents.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '...'`), el mismo patrón que ya usaba `ENDPOINT_CTE` en `/endpoints` -- ese patrón no tiene el problema porque nunca resta fechas en Python.

**Verificado de punta a punta:** se armó una instancia Postgres real (`pgserver`, sin root) con `database/schema.sql` cargado tal cual, datos de prueba sembrados (usuario, 2 endpoints, 2 agentes -- uno `ONLINE` con `last_seen_at` reciente --, eventos, un honeyfile, un incidente cerrado con su alerta y regla), y se corrió la app completa con `TestClient` contra esa base: login, `/dashboard`, `/endpoints`, `/honeyfiles`, `/eventos`, `/incidentes`, `/incidentes/1`, `/incidentes/1/reporte.pdf`, el drawer de expediente, `/configuracion`, y las 12 combinaciones de `/reportes/generar` (3 tipos × 2 formatos × con/sin filtro de endpoint) más la descarga de los archivos generados -- todo devolvió 200 después de la corrección.

---

## Informes y Reportes (2026-08-12)

**Qué se pidió:** que el sistema pueda responder "quién generó tal informe, cuándo, con qué parámetros" -- trazabilidad de auditoría real, no solo el archivo. Se armó según la tabla `reports` propuesta (adaptada a las convenciones del proyecto: `BIGSERIAL`/`TIMESTAMPTZ`, FKs reales a `endpoints`/`users`).

**Qué se construyó:**

1. **Tabla `reports`** (bitácora, no el archivo pesado): título, tipo, formato, período (con fechas resueltas, no solo la etiqueta), endpoint filtrado (`NULL` = todos), quién lo generó (`generated_by`, FK a `users`, siempre la sesión activa), y `file_path` -- la ruta en disco (`server/generated_reports/`) del archivo ya generado.
2. **3 tipos de informe**, los mismos que se propusieron, con contenido 100% de datos reales:
   - **SECURITY** (Informe de Seguridad General): alertas por severidad, incidentes por estado y clasificación, reglas heurísticas más activas, cobertura de honeyfiles (activos/activados/total), tiempo promedio de resolución.
   - **ENDPOINTS** (Actividad de Endpoints): por endpoint -- conectividad (calculada en SQL, ver bug de arriba), eventos en el período, honeyfiles desplegados/pendientes.
   - **INCIDENTS** (Incidentes): lista de incidentes abiertos en el período con endpoint, regla, estado, responsable y riesgo máximo. A propósito es un resumen de auditoría, no la traza forense completa de cada uno (eso ya existe por separado: `/incidentes/{id}/reporte.pdf`) -- el propio PDF lo aclara y redirige ahí para el detalle técnico.
3. **2 formatos reales**: PDF (`reportlab`, mismo estilo que el reporte de un incidente puntual) y XLSX (`openpyxl`, nueva dependencia en `server/requirements.txt`).
4. **`POST /reportes/generar`** arma el archivo en memoria, inserta la fila de auditoría, lo escribe a disco, y recién ahí actualiza `file_path` -- si algo falla a mitad de camino no queda un registro de auditoría apuntando a un archivo que no existe. `GET /reportes/{id}/archivo` sirve exactamente esa copia guardada (no regenera con datos más nuevos), con `disposition=inline` o `attachment`.

**Decisión explícita, siguiendo la regla de no fabricar funcionalidad:** no hay generación automática/programada ("Sistema (Auto)" del mockup original) -- `generated_by` siempre es un usuario real de la sesión. Se dejó documentado como extensión futura en vez de simularlo con un usuario "Sistema" que nadie configuró. Tampoco se ofrece un selector de rango de fechas libre, solo presets (7/30/90 días, todo el histórico) -- alcanza para el caso de uso y evita la complejidad de un date-range picker que el mockup no pedía en detalle.

**No incluido a propósito:** edición o eliminación de un informe ya generado desde la UI (se pueden borrar archivos del disco a mano si hace falta liberar espacio, pero no hay endpoint para eso todavía). Filtrado del historial por tipo/fecha/usuario en la propia tabla -- hoy solo pagina, sin filtros; se agregaría si el volumen de informes lo justifica.

---

## Panel de Control en React (frontend/, 2026-08-15)

**Qué se construyó:** un segundo frontend, aparte del Flask/Jinja2 existente, solo para el Panel de Control (Dashboard) -- React + TypeScript + Tailwind + Recharts + lucide-react, con datos 100% reales de PostgreSQL (nunca mock), vía dos endpoints JSON nuevos en `server/main.py`:

- `GET /api/dashboard/overview`: snapshot completo (KPIs, distribución de riesgo, endpoints en riesgo, alertas recientes, honeyfiles, estado de endpoints, top detecciones, actividad reciente, estado del sistema). Mismas consultas y mismos criterios de negocio que ya usa `dashboard_page()`/`dashboard/live` para las plantillas Jinja2 -- son dos caminos de código separados que llegan a las mismas cifras, no una fuente de verdad paralela. Si se cambia una regla de negocio en uno, hay que replicarla en el otro.
- `GET /api/dashboard/activity-series?period=24h|7d|30d`: la serie de tiempo del gráfico grande, 4 series reales (alertas, actividad de archivos, incidentes, honeyfiles), agrupadas por hora (24h) o por día (7d/30d).

**Decisiones de "no fabricar" aplicadas acá:**
- `endpoints_isolated` sale de `host_isolations` -- hoy siempre 0, porque nada escribe ahí todavía (el módulo de aislamiento automático es el próximo a construir, a pedido explícito del autor). La tarjeta "Endpoints Aislados" del Panel de Control está lista para mostrar un número real en cuanto ese módulo exista, sin tocar el frontend.
- `recent_alerts[].process` siempre es `null` -- `alerts` no tiene columna de proceso (ver "Atribución de proceso en eventos de archivo", más arriba). La tabla del dashboard muestra "—" en vez de inventar un nombre de proceso.
- `honeyfile_activity.recent[].file_name` siempre es `null` -- la alerta de `honeyfile_access` no incluye qué archivo fue (el agente no manda el `file_path` en el payload de la alerta, solo en el evento crudo). El panel muestra "archivo no identificado" en vez de inventar un nombre. Camino para resolverlo: agregar `file_path` al payload de `send_alert()` cuando la regla es `honeyfile_access` (agent/file_monitor.py) y resolverlo del lado del servidor contra `honeyfiles.file_path` del mismo agente -- no se hizo todavía, queda pendiente.
- "Actividad de seguridad" (gráfico grande) usa `events.detected_at` como proxy real de "actividad sospechosa" -- es el volumen crudo de archivos, no una clasificación de "sospechoso" separada que no existe.

**Bug real encontrado y corregido:** el parámetro de rango del segundo endpoint se llamaba `range`, igual que la función builtin de Python `range()` -- la sombreaba dentro de la misma función, y el armado de los buckets de tiempo (`for i in range(...)`) rompía con `TypeError: 'str' object is not callable`. Se renombró a `period` (parámetro interno y de la URL).

**Arquitectura del proyecto nuevo:** `frontend/` (Vite + React + TypeScript), corre en `:5173` en desarrollo. `vite.config.ts` tiene un proxy de `/api` y `/login` hacia `:8000` (el servidor real), para que la cookie de sesión viaje same-origin sin depender de configuración de `SameSite` en el navegador. Del lado del servidor se agregó `CORSMiddleware` (`allow_credentials=True`, orígenes explícitos vía `CORS_ORIGINS`) como respaldo, por si se sirve el frontend sin el proxy de Vite en algún momento.

**Limitación del entorno de este sandbox (no del código):** un directorio corrupto en `node_modules` bloquea cualquier instalación nueva de paquete npm (`ENOTEMPTY` al renombrar `node_modules/clsx`). Esto impidió instalar `@tailwindcss/vite` (la integración recomendada de Tailwind v4 con Vite) -- se usa en su lugar el CDN de Tailwind Play (`index.html`), que da las mismas clases utilitarias sin necesitar el paquete. En una máquina sin este problema, migrar a la integración real de Vite es directo (`npm install -D @tailwindcss/vite`, agregarlo a `plugins` en `vite.config.ts`) sin tocar ningún componente.

**Fuera del alcance pedido, pero necesario para que la app funcione sola:** una pantalla de login (`LoginGate.tsx`) -- sin ella no hay forma de autenticar la sesión que exigen los endpoints `/api/dashboard/*`. Ver entrada siguiente: se rehizo para que sea una réplica fiel de `login.html`, no queda como placeholder básico.

**Verificado de punta a punta (2026-08-15):** `npm run build` sin errores de TypeScript; prueba real con `pgserver` + `uvicorn` + el dev server de Vite corriendo juntos: login a través del proxy, `GET /api/dashboard/overview` y `/api/dashboard/activity-series` con cookie real (200, datos reales), sin cookie (401), contraseña incorrecta (401).

---

## Login del Panel de Control como réplica fiel del real (2026-08-15)

**Qué se hizo:** `LoginGate.tsx` (la pantalla de login del `frontend/` en React, ver entrada anterior) dejó de ser un formulario mínimo genérico y pasó a ser una réplica fiel de `server/templates/login.html` -- mismos dos paneles (panel izquierdo con gradiente navy/índigo, diagrama de red SVG con las mismas coordenadas, animación de radar/pulso, logo real; panel derecho con la tarjeta de login blanca, mismo texto, mismos campos con íconos, mismo toggle de "¿Olvidaste tu contraseña?"), mismo logo real (`/static/logo-icon.png`, servido por el backend, no duplicado como archivo en `frontend/`) y mismo flujo de `POST /login`. No es una reinterpretación -- se leyó `login.html` completo y se tradujo su estructura/CSS a componentes React + clases Tailwind.

**Cambios de soporte:**
- `vite.config.ts`: se agregó `/static` al proxy hacia `:8000`, para que el logo real se sirva a través del dev server de React igual que `/api` y `/login`.
- `index.html`: se agregaron las animaciones `travel` y `pulse-ring` al `tailwind.config` inline (vía CDN), portadas literalmente de los `@keyframes` de `login.html`.

**Limitación real del entorno encontrada y resuelta (no es un problema del código):** la carpeta del proyecto (`detection_ransomware/`) vive en una carpeta de Windows montada dentro del sandbox de Linux. Ese tipo de montaje entre sistemas operativos no tolera bien el patrón de Vite para invalidar su caché de dependencias (borra y reescribe `node_modules/.vite/deps/_metadata.json` cada vez que cambia `vite.config.ts`) -- cualquier archivo dentro de esa caché queda bloqueado con `EPERM: operation not permitted` al intentar reescribirlo, sin importar el nombre de la carpeta de caché. Esto solo bloqueaba **levantar el servidor de desarrollo de Vite dentro de este sandbox** para poder probar en vivo -- no afecta el código entregado ni debería reproducirse en una máquina real (Windows puro, sin este montaje cruzado).

**Cómo se verificó igual, de punta a punta (2026-08-15):** se copió `frontend/` a una carpeta nativa de Linux dentro del sandbox (fuera del montaje de Windows, solo para esta prueba), se reinstalaron los paquetes ahí (`npm install`, sin errores, algo que tampoco es posible de forma confiable directamente en la carpeta montada) y se corrió el flujo real completo: `pgserver` + `uvicorn` + el dev server de Vite juntos. Resultado: el logo real se sirve a través del proxy (`GET /static/logo-icon.png` → 200, PNG real de 100744 bytes, idéntico al archivo real en `server/static/`), el login funciona con un usuario real de la base (`POST /login` → 200, cookie de sesión), y con esa cookie `GET /api/dashboard/overview` responde 200 con datos reales. Los archivos entregados en `frontend/` (en la carpeta real del proyecto) no se tocaron para esta prueba -- la copia era solo para evitar la restricción del montaje al probar.

---

## Reskin del Panel de Control al diseño "Nocturne" + identidad AGETIC (2026-08-15)

**Qué pasó:** el autor recibió un mockup completo del mismo Panel de Control (`Panel de control AGETIC/ALFA_SENTINEL Panel de Control.dc.html`), hecho con un sistema de diseño llamado "Nocturne": tema oscuro con toggle a claro, iconos Phosphor, franja con los colores de la bandera boliviana en el sidebar, pie "AGETIC · Estado Plurinacional de Bolivia", gráficos SVG a mano (curvas suaves y anillo de dona) en vez de una librería de gráficos. A pedido explícito ("quiero que lo copies tal cual"), se reconstruyeron todos los componentes del Panel de Control de React con ese diseño exacto -- mismos datos reales de antes, look nuevo.

**Cambios de fondo, no solo visuales:**
- Los tokens de color (`--bg`, `--surf`, `--ok/--warn/--high/--crit`, etc.) se copiaron literalmente del mockup a `src/index.css`, con bloques `[data-theme="dark"]` / `[data-theme="light"]`. Los 4 colores de severidad siguen siendo exclusivos de Normal/Sospechoso/Alto/Crítico -- se mantiene la convención de todo el proyecto.
- `recharts` se sacó de `package.json` -- ya no se usa. `ActivityChart.tsx` y `RiskDonut.tsx` ahora son SVG a mano, con la misma lógica de interpolación Catmull-Rom que traía el mockup (portada de su `chart()`/`tip()` a un componente React), alimentada con los datos reales de `/api/dashboard/activity-series`, no con la data de ejemplo fija del mockup.
- `lucide-react` se reemplazó por iconos Phosphor vía CDN (`<link>` en `index.html`, clases `<i class="ph ph-xxx">`) en todos los componentes del dashboard -- igual que el mockup original ya los cargaba, sin paquete npm nuevo. `LoginGate.tsx` sigue usando `lucide-react` (no es parte de este rediseño, sigue siendo réplica de `login.html`).
- Toggle de tema claro/oscuro real (`App.tsx`, estado + `localStorage`), no estaba antes.
- El nombre de usuario del topbar ahora sale de `GET /me` (endpoint que ya existía en el servidor, no se creó nada nuevo) en vez de un texto fijo "Analista".

**Convención nueva de dato de prueba (a pedido explícito, reemplaza el "—" / "archivo no identificado" anterior):** donde el backend no tiene manera de conseguir un dato real todavía (no es un cero real, es un hueco estructural -- ver "Atribución de proceso en eventos de archivo" y "Panel de Control en React" más arriba), se muestra un valor obviamente de prueba: **99** para números faltantes, **"aquí va el dato"** para texto faltante (`src/lib/placeholder.ts`). Aplica hoy a `recent_alerts[].process`, `honeyfile_activity.recent[].file_name` y `summary.alerts_trend_pct` (cuando no hay datos de las 24h previas). No aplica a valores que son honestamente cero (ej. `endpoints_isolated`).

**Bug real encontrado y corregido:** `vite.config.ts` no tenía `/me` en el proxy hacia `:8000` -- el pedido caía en el fallback de SPA de Vite y devolvía el `index.html` en vez de JSON (probado en vivo, `GET /me` devolvía 200 con HTML). Se agregó `/me` junto a `/api`, `/login` y `/static`.

**Identidad AGETIC en el sidebar:** franja de bandera boliviana y el pie "AGETIC · Estado Plurinacional de Bolivia" son elementos de marca fijos (igual que el mockup), no datos del sistema -- no hay nada que verificar contra la base ahí.

**Verificado de punta a punta (2026-08-15):** `tsc -b --force` sin errores; prueba real con `pgserver` + `uvicorn` + Vite juntos (desde una copia en disco nativo de Linux, mismo motivo que la entrada anterior -- el montaje de Windows no tolera la caché de dependencias de Vite): login real (200), `GET /me` con nombre real de usuario a través del proxy (200, `{"username":"aldahir","full_name":"Aldahir Fernandez",...}`), logo real a través del proxy (200, PNG real), `GET /api/dashboard/overview` con datos reales y los huecos esperados en `null` (200).

---

## Campana, menú de usuario, logo real + pantalla Endpoints en React (2026-08-15)

**Arreglos sobre el reskin anterior (a pedido explícito, cosas que quedaron a medias):**
- **Campana de notificaciones:** no hacía nada al hacer clic. Ahora `NotificationsBell.tsx` abre un dropdown real con las alertas `NEW` (`GET /alerts/open`, endpoint que ya existía en el servidor, pensado justo para esto -- no se creó nada nuevo). Se cierra al hacer clic afuera (`useClickOutside.ts`).
- **Rol del usuario:** decía "Analista de seguridad" fijo. Ahora sale de `GET /me` → `roles` (real, de la sesión). Importante: **no existe ninguna tabla de traducción rol→español en el servidor** (confirmado en `server/templates/usuarios.html`: "Hoy solo existe el rol admin... no se muestra una matriz de roles con permisos") -- se capitaliza el valor real tal cual (`admin` → `Admin`), no se inventó una etiqueta.
- **Menú de usuario:** el botón no desplegaba nada. Ahora `UserMenu.tsx` abre un dropdown real con "Mi perfil" (→ `/perfil`, página Jinja2 real) y "Cerrar sesión" (`POST /logout`, endpoint real que ya existía -- limpia la sesión de verdad, verificado en vivo: después de logout, `GET /me` pasa a devolver 401).
- **Logo:** el sidebar tenía un ícono genérico de escudo (Phosphor) en vez del logo real. Ahora usa `/static/logo-icon.png` (el mismo archivo real que ya usa `login.html` y `LoginGate.tsx`, vía el proxy existente).

**Cambios de soporte:** `vite.config.ts` sumó `/logout` y `/alerts` al proxy (antes solo tenía `/api`, `/login`, `/me`, `/static` -- sin esto, esos pedidos también hubieran caído en el fallback de SPA de Vite, el mismo bug que ya se había encontrado con `/me`).

**Pantalla nueva: Endpoints (React).** Segunda pantalla real del panel (antes solo existía el Dashboard) -- navegación interna sin recargar la página (`App.tsx` ahora tiene un estado `page: "dashboard" | "endpoints"`, `Sidebar.tsx` cambia sus dos primeros ítems de `<a href>` reales a botones que cambian ese estado; el resto de los ítems del menú siguen siendo enlaces reales a Jinja2, sin cambios). Mismo sistema de diseño exacto del Panel de Control -- ningún token, componente base ni patrón visual nuevo, a pedido explícito ("no rediseñes el sistema visual").

**Backend nuevo:** `GET /api/endpoints` (`server/main.py`), con paginación y filtros (`search`, `status`, `risk`, `os_family`). Reutiliza `_endpoint_cte()`, la misma función que ya usa `/endpoints` (Jinja2) -- no es una fuente de verdad paralela. Diferencia real a propósito: esta pantalla pidió un solo valor de "Estado" (Online/Offline/Aislado, con Aislado con prioridad sobre el estado de conexión crudo), mientras que `/endpoints` (Jinja2) usa tres categorías de conectividad más finas (ok/attention/offline) sin conjunto "aislado" propio. Se conservó esa distinción más fina aparte, como "Agente" (Healthy/Warning/Offline, derivado 1:1 de `status_bucket`). Riesgo (Normal/Sospechoso/Alto/Crítico) sigue siendo un eje totalmente aparte, igual que en el resto del sistema -- nunca se mezcla con conectividad.

Dos columnas nuevas, reales, que no existían en ninguna vista de endpoints hasta ahora:
- **Alertas:** cuenta de alertas `NEW` por agente (subquery real contra `alerts`).
- **Última actividad:** `MAX(events.detected_at)` por agente (real, de la tabla `events` ya poblada por el agente). Cuando un endpoint no tiene ningún evento registrado todavía, se muestra "Sin actividad registrada" -- esto es honesto (`NULL` genuino porque no pasó nada, no un hueco estructural), así que **no** usa la convención de placeholder "99"/"aquí va el dato".

**Bug real encontrado y corregido:** ninguno nuevo en el backend (probado en vivo con filtros reales antes de tocar el frontend). El único bug de esta sesión fue el de proxy (`/logout`, `/alerts`) mencionado arriba.

**Verificado de punta a punta (2026-08-15):** `tsc -b --force` sin errores; con `pgserver` + `uvicorn` + Vite corriendo juntos (misma copia en disco nativo de Linux por el mismo motivo de siempre): login (200), `GET /alerts/open` a través del proxy con alertas reales, `GET /api/endpoints` a través del proxy con filtros (`search`, paginación) devolviendo datos reales, `POST /logout` a través del proxy invalidando la sesión de verdad (confirmado con `GET /me` → 401 después).

---

## Drawer de detalles de endpoint en React (2026-08-15)

**Qué se pidió:** al hacer clic en "Detalles" de un endpoint (pantalla Endpoints, React), abrir un panel lateral desde la derecha sin salir de la página, usando exclusivamente información real ya disponible -- nada de tablas nuevas, columnas nuevas ni datos ficticios.

**Investigación previa (antes de construir nada):** ya existía `GET /api/endpoints/{agent_id}/drawer` en `server/main.py`, construido para el mismo propósito y **ya en uso hoy** por `server/templates/endpoints.html` (Jinja2) -- no es un endpoint nuevo, es el mismo que ya alimenta el drawer de la consola vieja. Se reutilizó tal cual, extendiéndolo (sin romper el contrato que ya consume `endpoints.html`) con campos que faltaban para cubrir el pedido, todos derivados de datos/fórmulas que el sistema ya calcula en otro lado:
- `agent_health` -- misma fórmula de `_endpoint_cte()` (Healthy/Warning/Offline según último heartbeat vs. el umbral configurado), para que el drawer diga lo mismo que la lista.
- `last_seen_ago`, `honeyfiles_violated_ago` -- mismo `time_ago()` que usa el resto de la consola.
- `alerts_active` -- mismo criterio que `/api/endpoints` (`alerts.status = 'NEW'` por agente).
- `incidents_total` / `incidents_active` -- `COUNT(*)` real sobre `incidents` por `agent_id` (columna que ya existe, nunca se había expuesto contada por endpoint).

**Lo que NO se hizo, a propósito:**
- **Aislar endpoint:** el botón existe en el drawer pero queda deshabilitado con el mismo texto honesto que ya usa `endpoints.html` ("ALFA-Sentinel no puede aislar un host todavía: el agente no tiene forma de recibir ni ejecutar un comando remoto") -- confirmado que no existe ningún endpoint que escriba en `host_isolations`, ni función de liberar aislamiento. No se construyó un flujo de confirmación falso para una acción que no existe de verdad.
- **Actividad reciente:** no hay un log unificado de eventos por endpoint (heartbeats, cambios de estado y aislamientos no se registran como eventos discretos). La timeline del drawer es intencionalmente mínima -- solo 3 entradas posibles, cada una atada a un dato 100% real ya presente en la respuesta (última alerta, honeyfile violado si existe, fecha de registro). No se inventó un sistema de eventos nuevo para llenarla.
- **MAC address / arquitectura:** el drawer las trae como `null` (el agente nunca las recolecta) -- se omiten en la UI en vez de mostrar un campo vacío o inventado.
- **Alertas:** el drawer solo trae la última alerta (no una lista completa) -- en vez de duplicar toda la sección Alertas, se muestra esa última alerta como resumen y un enlace real a `/detecciones?agent_id={id}` (el mismo patrón de filtro por agente que ya usa `endpoints.html` con su botón "Ver Incidentes").

**Componentes nuevos:** `EndpointDrawer.tsx` (panel con overlay, animación de entrada/salida por transform+opacity, cierre por X/clic afuera/Escape), reemplaza el clic de fila que antes navegaba a `/endpoints/{id}` -- ahora `EndpointsTable.tsx` tiene un botón "Detalles" explícito por fila que abre el drawer sin recargar la página. Mismo sistema visual de la pantalla Endpoints -- ningún token, color ni componente base nuevo.

**Verificado de punta a punta (2026-08-15):** `tsc -b --force` sin errores; con `pgserver` + `uvicorn` + Vite corriendo juntos (misma copia en disco nativo de Linux, mismo motivo de siempre): login (200), `GET /api/endpoints/{id}/drawer` a través del proxy para un endpoint con alertas/honeyfiles (200, datos reales) y para uno sin actividad (200, campos en `null`/0 honestos), 404 real para un id inexistente.

---

## Prompt maestro de diseño para el resto de la interfaz React (2026-08-15)

**Referencia viva.** El autor entregó un prompt maestro extenso que rige el diseño de las 7 pantallas que faltan en React (todo lo que no es Panel de Control ni Endpoints, que ya están hechos). Se resume acá para no perder las reglas -- cualquier pantalla nueva debe revisarse contra esto antes de construirse.

**Regla de diseño:** una sola plataforma coherente -- reusar exactamente los tokens, tarjetas, tablas, badges, botones, iconos, drawers, filtros y jerarquía visual ya establecidos en Panel de Control/Endpoints. Consistencia por encima de creatividad. Nada de estética "hacker", neón, ni gráficos decorativos sin propósito.

**Regla de datos (la más importante, ya veníamos siguiéndola):** el `schema.sql` real es la única fuente de verdad. No inventar tablas, columnas ni relaciones. No crear datos ficticios "temporales" para rellenar la interfaz -- si un dato no existe, se omite o se muestra un estado vacío honesto (ej. "Proceso no disponible", "Sin responsable asignado", "Sin activaciones"). Puntos ya confirmados por el autor sobre el estado real del sistema (coinciden con lo que esta sesión ya había encontrado por su cuenta):
- `agent_rule` existe pero no tiene datos ni código que la use -- no mostrarla como si hubiera configuración por agente.
- `host_isolations` es estructuralmente real pero el mecanismo de aislamiento es un placeholder -- la UI puede mostrar la estructura/concepto pero no fingir que la acción funciona.
- `alerts` no tiene relación directa con `events` -- no inventar que una alerta siempre puede mostrar un proceso o archivo concreto.
- `system_settings` solo tiene `agent_stale_seconds` como parámetro real editable -- no mostrar controles para heartbeat/sincronización de reglas como si fueran configurables.
- Severidad: `severity_levels` con NORMAL (0-29.99) / SUSPICIOUS (30-59.99) / HIGH (60-79.99) / CRITICAL (80-100) -- son los únicos 4 niveles, mismos colores en toda la app.

**Orden de construcción acordado (2026-08-15), siguiendo el propio flujo del autor (MONITOREAR → DETECTAR → ALERTAR → INVESTIGAR → RESPONDER → CONTENER → RESOLVER):**
1. Alertas (tabla + drawer, con `alert_rule` para reglas asociadas)
2. Incidentes (gestión de casos, la pantalla más completa: alertas relacionadas vía `incident_id`, timeline armada solo con datos temporales reales, `host_isolations`)
3. Honeyfiles (honeyfiles reales + plantillas + asignaciones + activaciones -- explícitamente separados, no confundir plantilla con honeyfile instalado)
4. Reglas Heurísticas (comprensible, no una consola técnica)
5. Acciones de Respuesta (centrada en `host_isolations`, automático vs. manual)
6. Reports (`reports`: SECURITY/ENDPOINTS/INCIDENTS, PDF/XLSX -- sin tipos inventados)
7. Administración con 4 subsecciones: Usuarios y roles, Agentes, Configuración (solo `agent_stale_seconds`), Registro de actividad (`audit_logs`, dentro de Administración, no como módulo aparte del sidebar)

**Drawers en todos lados donde tenga sentido** (Endpoints, Alertas, Incidentes, Honeyfiles, Acciones), consistente con el patrón ya construido en `EndpointDrawer.tsx` -- mismo comportamiento (overlay sutil, cierre por X/clic afuera/Escape, animación corta, sin navegar a otra página).

**Consistencia entre módulos:** una misma entidad (ej. `PC-CONT-03`, un nivel de severidad, un estado, un usuario) debe verse exactamente igual en cualquier pantalla donde aparezca.

---

## Módulo de Configuración: 4 pestañas reales (2026-08-12)

**Qué se pidió:** un mockup detallado de 4 pestañas (Detección con sub-pestañas Reglas/Severidades, Agentes, Usuarios y Roles, Auditoría), incluyendo `agent_rule` (excepciones por agente), Severidades editables con "acción automatizada" (aislamiento automático en Crítico), Intervalo de Heartbeat / Tolerancia de Conexión / Sincronización de Reglas como parámetros de Agentes, y una matriz de roles Administrador/Analista SOC.

**Investigación previa (antes de construir nada):** se confirmó contra el código real del agente y del servidor que varias piezas del mockup no tienen mecanismo detrás hoy: el agente (`agent/main.py`) manda un solo heartbeat al arrancar -- no hay bucle, no existe "intervalo" como concepto; no hay forma de que el agente sincronice reglas desde el servidor (a diferencia de honeyfiles, que sí tiene `GET /agent/honeyfile-policy`) -- `umbral`/`ventana` siguen hardcodeados en `agent/heuristic_engine.py`; los rangos de `severity_levels` están duplicados como literales en Python (`get_risk_level()`) y nunca se leen de la base; `agent_rule` existe en el schema pero tiene 0 filas y 0 código (ni agente ni servidor) que la lea o escriba; solo 2 endpoints en toda la app (`POST /users`, `POST /enrollment-tokens`) exigen rol admin -- el resto no distingue por rol; solo existe el rol `admin`, nunca se sembró "Analista SOC"; el agente no tiene canal de comandos remotos, así que el aislamiento automático en Crítico no se puede ejecutar.

**Decisión (confirmada con el autor, opción recomendada en las 4 preguntas):** en vez de construir UI decorativa para lo que no existe, o sacarlo sin dejar rastro, se separó lo real de lo pendiente:

1. **`system_settings`** (tabla nueva, `database/schema.sql` sección 23 + `system_settings_migration.sql`): reemplaza la constante fija `AGENT_STALE_SECONDS = 120` de `server/main.py`. Ahora es genuinamente editable desde la pestaña Agentes (`PATCH /settings/{key}`, whitelist `KNOWN_SETTINGS` -- hoy solo `agent_stale_seconds` -- para que no aparezcan parámetros editables que nada consume). Los otros 3 campos del mockup para Agentes (Intervalo de Heartbeat, Sincronización de Reglas, y el propio Timeout antes de este cambio) se muestran como texto no editable con la razón arquitectónica explicada en la propia pestaña, no se ocultan.
2. **`audit_logs` conectado de verdad**: la tabla existía desde antes pero nada escribía ahí (bug/vacío documentado ya en este archivo). Se agregó `log_audit()` en `server/main.py` y se llamó desde los 7 puntos donde ya existía una acción administrativa real: `assign_incident`/`unassign`, `update_rule` (peso/estado), `update_setting`, `update_incident_status`, `update_alert_status`, `create_user`, `update_user`. La pestaña Auditoría muestra estas filas reales, paginadas -- no hay generación automática de eventos de auditoría más allá de estas 7 acciones.
3. **`PATCH /users/{user_id}`** (nuevo): antes solo se podía crear y listar usuarios, no editar nombre/correo/rol ni desactivar una cuenta. Se agregó, admin-only, con su propio registro de auditoría (`UPDATE_USER`). `usuarios.html` se reescribió del estilo viejo (`page-hero`) al estándar `pc-*` del resto de la app, con modal compartido de crear/editar.
4. **Severidades**: se muestran como tabla de solo lectura (no editable) con una columna "Acción esperada (manual)" que describe la respuesta humana esperada -- explícitamente no "acción automatizada", y un cartel aclarando que el agente tiene su propia copia hardcodeada de estos mismos umbrales, no los lee de esta tabla.
5. **`agent_rule` (Sobrescrituras por Agente)**: se dejó visible en la pestaña Detección (no se sacó del diseño) con el botón "+ Agregar Excepción por Agente" deshabilitado y un texto explicando que la tabla existe en el schema pero ningún código la usa todavía -- construirla de verdad requiere primero el mecanismo de sincronización de reglas que no existe (mismo camino propuesto que en la sección "Página de Reglas real" más arriba, vía `GET /agent/rule-policy` análogo a honeyfiles).
6. **Matriz de roles Administrador/Analista SOC**: no se construyó -- se reemplazó por una nota honesta en `usuarios.html` explicando que hoy solo `admin` tiene permisos diferenciados reales, y en apenas 2 endpoints. No se muestra una matriz con permisos que no se aplican.
7. **Aislamiento automático en Crítico**: no se construyó -- ver "El agente no tiene canal de comandos remotos" en los hallazgos de investigación arriba. Sigue siendo el mismo pendiente que "Aislar Host" en Dashboard/Endpoints/Incidentes.

**Verificado de punta a punta:** `py_compile` + barrido Jinja sobre todos los templates + `node --check` sobre los scripts de `configuracion.html`/`usuarios.html`/`endpoints.html`/`honeyfiles.html`/`reportes.html`, más una corrida real con Postgres (`pgserver`) y `TestClient`: login, las 5 combinaciones de pestaña/sub-pestaña de `/configuracion`, `PATCH /rules/1`, `PATCH /settings/agent_stale_seconds` (200) y `PATCH /settings/bogus_key` (404, confirma que la whitelist rechaza claves no soportadas), `POST /users`, `PATCH /users/{id}`, desasignar un incidente, cambiar estado de una alerta -- y se confirmó que las 6 acciones esperadas aparecen en `audit_logs` con la descripción correcta.

---

## Pantalla Alertas en React (2026-08-15)

**Primera pantalla construida del orden de 7 acordado en el prompt maestro** (Alertas → Incidentes → Honeyfiles → Reglas Heurísticas → Acciones de Respuesta → Reports → Administración). Sigue el mismo patrón que Endpoints: resumen (5 tarjetas), búsqueda + filtros, tabla, paginación y un drawer lateral -- sin inventar un diseño nuevo.

**Backend, todo reutilizado o extendido, nada duplicado:**
- `GET /api/alerts` (nuevo, `server/main.py`): lista dedicada de alertas sueltas para React -- a diferencia de `/incidentes` (Jinja2), que unifica incidentes agrupados y alertas sueltas en un `COMBINED_CTE`, acá se listan filas de `alerts` tal cual. Mismas tablas y mismas etiquetas ES (`ALERT_STATUS_LABELS_ES`, `ALERT_SEVERITY_LABELS_ES`, `ALERT_RULE_LABELS_ES`) que el resto del sistema -- no es una fuente de verdad paralela. Devuelve resumen (total/activas/críticas/en investigación/resueltas), lista de reglas disponibles para el filtro como `{value, label}` (el valor crudo de `heuristic_rules.name` viaja aparte de la etiqueta en español, para que el filtro compare contra la columna real), y la página de alertas con paginación.
- `GET /api/incidentes/alert/{id}/drawer`: no se creó un endpoint nuevo -- se extendió `get_incidente_drawer` (el mismo que ya usa `/incidentes` en Jinja2 para su panel lateral, que ya soportaba `kind="alert"`) con `incident_id`, `resolved_at` y `rules` (todas las filas de `alert_rule` con su peso y fecha, vía join a `heuristic_rules`). Extensión aditiva -- no se quitó ni renombró ningún campo que ya consumía `/incidentes`.
- Detalle técnico: `DISTINCT ON (alerts.id)` obliga a que el `ORDER BY` de Postgres empiece por `alerts.id`, no por fecha -- se reordena la lista en Python después del fetch (`rows.sort(..., reverse=True)`) para mostrar lo más reciente primero, con un comentario en el código explicando por qué.

**Frontend:** `types/alerts.ts`, `fetchAlerts`/`fetchAlertDrawer` en `api/client.ts`, `AlertsSummaryCards`, `AlertsFilters` (severidad, estado, periodo, tipo de detección), `AlertsTable`, `AlertsPagination`, `AlertDrawer.tsx` (mismo patrón de overlay/panel/animación que `EndpointDrawer.tsx`) y `AlertsPage.tsx`. Estado de la alerta (Nueva/En investigación/Confirmada/Cerrada/Falso positivo) usa una escala de color aparte (`--info`/`--brand`/`--off`, `lib/alertStatus.ts`) -- nunca los 4 colores de severidad, que quedan exclusivos al nivel de riesgo. "Alertas" pasó de enlace real a `/incidentes` a pantalla interna de React en `Sidebar.tsx`/`App.tsx` (`Page = "dashboard" | "endpoints" | "alerts"`); "Incidentes" sigue apuntando a la consola Jinja2 real hasta que se construya esa pantalla.

**Actividad relacionada, honesto:** el drawer muestra el array `timeline` (correlación por ventana de tiempo, ya usada en `/incidentes`) con una aclaración explícita en la propia UI de que es una correlación aproximada, no un vínculo real alerta→evento (no existe esa FK en el schema). Sin incidente agrupado, el drawer dice explícitamente "Esta alerta no forma parte de un incidente agrupado" en vez de ocultar la sección.

**Verificado:** `npx tsc -b --force` sin errores; todos los `.tsx` nuevos transformados sin error de sintaxis a través del dev server de Vite; corrida real end-to-end (`pgserver` + `uvicorn` + `vite`, proxy incluido) con login real y datos reales: resumen `{"total":2,"active":2,"critical":1,"investigating":0,"resolved":0}`, filtro `severity=CRITICAL` devolviendo 1 de 2, y el drawer de la alerta 1 devolviendo `rules` con el peso y fecha reales del `alert_rule` correspondiente.

---

## Pantalla Incidentes en React (2026-08-15)

**Segunda pantalla del orden acordado.** "Incidentes" unifica, igual que `/incidentes` en Jinja2, incidentes ya agrupados (varias alertas relacionadas) y alertas sueltas sin escalar en una sola matriz (`COMBINED_CTE`) -- no se separó en dos listas para React, sería inconsistente con el modelo real.

**Backend, todo reutilizado o extendido, nada duplicado:**
- `GET /api/incidentes` (nuevo, `server/main.py`): versión JSON de `incidentes_page` -- mismo `COMBINED_CTE`, mismos filtros (estado unificado, severidad, regla, periodo, búsqueda) y mismos KPIs (incidentes críticos, alertas activas, hosts aislados vía `host_isolations` -- hoy siempre 0, de verdad, nada lo escribe todavía -- y MTTR promedio). Devuelve además las listas de opciones (`status_options`, `severity_options`, `rule_options`, `since_options`, `assignable_users`) para que los filtros y el selector de responsable del frontend no dupliquen esos vocabularios.
- Acciones del drawer -- **ningún endpoint nuevo**, todos ya existían y los usaba `incidentes.html`: `PATCH /incidents/{id}/status`, `PATCH /incidents/{id}/assign`, `PATCH /incidents/{id}/classification`, y `POST /incidents` (escala una alerta suelta a incidente; si la alerta ya tenía incidente, devuelve ese en vez de crear uno duplicado).
- `GET /api/incidentes/{kind}/{id}/drawer`: sin cambios en esta pasada -- ya soportaba `kind="incident"` desde antes (extendido para `kind="alert"` en la pantalla Alertas).
- `vite.config.ts`: se agregó `/incidents` (sin la 'e', son las rutas de acción reales del servidor) a la lista de proxy -- si no, las llamadas `PATCH`/`POST` hubieran caído en el fallback de SPA de Vite, mismo bug ya visto tres veces antes con `/me`/`/logout`/`/alerts`. Esta vez se agregó de entrada, antes de necesitar depurarlo.

**Frontend:** `types/incidentes.ts`, `lib/incidentStatus.ts` (traduce `IncidentStatus`/`IncidentClassification`, copia directa de las constantes del servidor -- no hay endpoint que las liste dinámicamente porque son vocabularios fijos del propio código), `fetchIncidentes`/`fetchIncidenteDrawer`/`updateIncidentStatus`/`assignIncident`/`classifyIncident`/`escalateAlertToIncident` en `api/client.ts`, `IncidentesSummaryCards` (4 tarjetas), `IncidentesFilters`, `IncidentesTable` (columna Código con ícono distinto para incidente/alerta suelta), `IncidentesPagination`, `IncidentDrawer.tsx` (generaliza el patrón de `AlertDrawer.tsx` para ambos `kind`) y `IncidentesPage.tsx`. "Incidentes" pasó de enlace real a pantalla interna (`Page = "dashboard" | "endpoints" | "alerts" | "incidentes"`).

**`IncidentDrawer.tsx` es la primera pantalla con acciones editables reales** (no solo lectura): para un incidente agrupado, el estado, el responsable y la clasificación son selects que llaman a los endpoints reales de inmediato y refrescan tanto el propio drawer como la lista de fondo. Para una alerta suelta sin incidente, hay un botón real "Escalar a incidente" (`POST /incidents`). El botón "Aislar endpoint" reusa el mismo patrón honesto ya establecido en `EndpointDrawer.tsx` -- deshabilitado, con el mismo tooltip explicando que el agente no tiene canal de comandos remotos.

**Verificado:** `npx tsc -b --force` sin errores; todos los `.tsx` nuevos transformados sin error de sintaxis vía Vite; corrida real end-to-end con login real: `GET /api/incidentes` devolviendo las 2 alertas sueltas reales; `POST /incidents` escalando una a incidente real (`INC-00001`); la lista recalculándose sola (una fila `kind:"incident"` nueva, la otra alerta se queda suelta); `PATCH status/assign/classification` aplicados en secuencia sobre ese incidente y confirmados releyendo el drawer (`IN_PROGRESS`, responsable `Aldahir Fernandez`, clasificación `Posible amenaza`).

---

## Pantalla Honeyfiles en React (2026-08-15)

**Tercera pantalla del orden acordado.** A diferencia de Alertas/Incidentes, acá casi todo el backend ya existía y ya lo usaba `honeyfiles.html` -- el Wizard de Despliegue de 2 pasos (Parámetros de trampa / Agentes destino) se replicó casi literal desde el HTML real, mismos campos, mismas opciones, mismo texto explicativo, sin inventar un flujo nuevo.

**Backend:**
- `GET /api/honeyfiles` (nuevo, `server/main.py`): versión JSON de `honeyfiles_page` -- misma consulta, mismos KPIs, mismas listas para el wizard (`available_agents`, `distinct_os`). No pagina, igual que la versión Jinja2 (el inventario real hoy es chico).
- **Corrección aplicada solo en este endpoint nuevo, documentada acá para que no se pierda:** `honeyfiles_page` (Jinja2) filtraba `status=TRIGGERED` directo contra la columna `honeyfiles.status`, pero esa columna nunca guarda literalmente `'TRIGGERED'` -- solo `ACTIVE`/`INACTIVE`. `TRIGGERED` es un estado calculado en Python (`ACTIVE` + `activations_count > 0`). Eso significa que en la consola Jinja2 real, filtrar por "🔴 Activados / Comprometidos" nunca devuelve nada, aunque sí haya honeyfiles activados -- un bug preexistente, no introducido en esta pasada. En `/api/honeyfiles` el filtro de estado se aplica en Python, después de calcular `TRIGGERED`, así que en React el filtro sí funciona. La plantilla Jinja2 no se tocó (migración progresiva) -- el bug ahí sigue, documentado acá para cuando se migre esa pantalla o se decida parchearla aparte.
- **Sin endpoints nuevos para el resto:** `GET /api/honeyfiles/{id}/detail` (drawer), `POST /api/honeyfiles/{id}/toggle-status` (activar/desactivar) y `POST /api/honeyfiles/deploy` (crear plantilla + asignar a agentes) ya existían tal cual y ya los usaba `honeyfiles.html` -- se reusaron sin cambios.

**Frontend:** `types/honeyfiles.ts`, `lib/honeyfileStatus.ts` (ACTIVE/INACTIVE/TRIGGERED reusan los extremos de la escala `--ok`/`--off`/`--crit`, mismo patrón ya establecido en `lib/endpointStatus.ts` para ONLINE/OFFLINE/ISOLATED -- un honeyfile activado es, en los hechos, tan grave como una alerta CRÍTICA, aunque no sea un valor de `severity_levels`), `fetchHoneyfiles`/`fetchHoneyfileDetail`/`toggleHoneyfileStatus`/`deployHoneyfile` en `api/client.ts`, `HoneyfilesSummaryCards` (5 tarjetas), `HoneyfilesFilters` (con el botón "Desplegar honeyfile"), `HoneyfilesTable`, `HoneyfileDrawer.tsx` (info del archivo + hash SHA-256 real + historial de activaciones + botón real activar/desactivar) y `DeployHoneyfileWizard.tsx` (modal centrado de 2 pasos, no un drawer lateral -- es un formulario de creación, no el detalle de algo existente). "Honeyfiles" pasó de enlace real a pantalla interna (`Page` ganó `"honeyfiles"`).

**Verificado:** `npx tsc -b --force` sin errores; los 6 `.tsx` nuevos transformados sin error de sintaxis vía Vite; corrida real end-to-end con login real: `GET /api/honeyfiles` con el honeyfile real existente (`Presupuesto.xlsx`, `PC-CONT-03`) y los 3 agentes reales para el wizard; `GET /api/honeyfiles/1/detail` con hash y datos reales; `POST toggle-status` alternando `ACTIVE -> INACTIVE -> ACTIVE` y confirmado con el filtro `status=INACTIVE` encontrándolo en el paso intermedio (prueba de que la corrección del filtro funciona); `POST /api/honeyfiles/deploy` creando una plantilla real asignada a 2 agentes, con `pending_deployments` subiendo de 0 a 2 en el resumen.

---

## Pantalla Reglas Heurísticas en React (2026-08-15)

**Cuarta pantalla del orden acordado.** Antes vivía como una sub-pestaña técnica dentro de Configuración (`/configuracion?tab=deteccion`); ahora es su propia pantalla, pensada para leerse de un vistazo ("comprensible, no una consola técnica", como pide el orden acordado) -- una tarjeta por regla en vez de una tabla densa de parámetros.

**Backend:**
- `GET /api/rules` (nuevo, `server/main.py`): misma consulta exacta que la sub-pestaña Detección > Reglas de `configuracion_page` (peso, umbral, ventana, tipo de evento, alertas de los últimos 30 días, última activación), envuelta en un resumen (total/activas/inactivas/alertas 30d).
- Sin endpoint de escritura nuevo: `PATCH /rules/{id}` ya existía y ya lo usaba `configuracion.html`. Se agregó `/rules` a la lista de proxy de Vite (mismo bug que ya se vio con `/me`/`/logout`/`/alerts`/`/incidents` si no se agrega a tiempo).
- Solo se exponen `weight` e `is_active` como editables en la UI -- son los únicos dos campos que la consola real también deja tocar (el propio código documenta que `threshold`/`window_seconds`, aunque reales y ya consumidos por el agente vía `GET /agent/rule-policy`, se muestran de solo lectura a propósito). Se preservó esa misma decisión de diseño en React, no se inventó edición nueva para campos que la consola real mantiene de solo lectura.

**Frontend:** `types/rules.ts`, `fetchRules`/`updateRule` en `api/client.ts`, `RulesSummaryCards` (4 tarjetas), `RuleCard.tsx` (tarjeta por regla con el peso editable inline con botón "Guardar" que aparece solo si el valor cambió, y un toggle de estado que llama al PATCH de inmediato) y `RulesPage.tsx`. "Reglas heurísticas" pasó de enlace real a `/configuracion?tab=deteccion` a pantalla interna (`Page` ganó `"reglas"`).

**Verificado:** `npx tsc -b --force` sin errores; los 3 `.tsx` nuevos sin error de sintaxis vía Vite; corrida real end-to-end: `GET /api/rules` con las 4 reglas reales (`mass_file_activity`, `honeyfile_access`, `ransomware_extension_rename`, `mass_deletion`) y sus alertas/pesos/umbrales reales; `PATCH /rules/1` cambiando peso a 75 y luego `is_active` a `false`, confirmado releyendo `/api/rules` (resumen `active` bajando de 4 a 3); revertido a los valores originales (peso 30, activa) al terminar la prueba para no dejar la base de prueba en un estado distinto al inicial.

---

## Pantalla Acciones de Respuesta en React (2026-08-15)

**Quinta pantalla del orden acordado, la más chica de las 7.** `/respuesta` en Jinja2 hoy es directamente un `render_placeholder()` -- no hay ninguna funcionalidad real detrás, ni una tabla con datos, nada: solo un mensaje honesto explicando que el aislamiento automático no está implementado (`host_isolations` existe en el schema, pero el agente no tiene canal de comandos remotos, así que nada escribe ahí nunca). Construir esta pantalla en React con botones de "aislar" que no hacen nada real hubiera sido exactamente el tipo de fabricación que este proyecto evita a propósito -- así que en vez de eso, la pantalla muestra lo que sí es real y útil: qué incidentes necesitarían esa contención manual ahora mismo, y el historial real de `host_isolations` (vacío, con la razón explicada en la propia tabla en vez de solo un espacio en blanco).

**Backend:** `GET /api/respuesta` (nuevo, `server/main.py`) -- tres cosas reales: (1) el conteo actual de hosts aislados (siempre 0 hoy, consulta real sobre `host_isolations`), (2) el historial completo de `host_isolations` (join a `endpoints`/`users`, hoy siempre vacío), y (3) los incidentes abiertos de severidad Alta o Crítica -- estos sí existen de verdad y son la razón por la que esta pantalla es útil aunque el aislamiento automático no lo esté. `isolation_type`/`status` de `host_isolations` se devuelven tal cual (sin traducir a español) porque son `VARCHAR` libres sin `CHECK constraint` y, al no haberse usado nunca, no existe ningún vocabulario fijo en el código para traducirlos -- inventar etiquetas para valores que nunca ocurrieron hubiera sido fabricar significado que no existe.

**Frontend:** `types/respuesta.ts`, `fetchRespuesta` en `api/client.ts`, `RespuestaSummaryCards` (3 tarjetas), `CriticalIncidentsTable` (con estado vacío positivo: "No hay incidentes de alta o crítica severidad abiertos ahora mismo" + ícono de escudo, en vez de una tabla vacía sin explicación), `IsolationsHistoryTable` (estado vacío explicando por qué nunca hay filas) y `RespuestaPage.tsx`, que además reproduce el mismo texto honesto del placeholder real de `/respuesta` como banner fijo arriba de todo. "Acciones de respuesta" pasó de enlace placeholder (`/incidentes`, un parche temporal de una pasada anterior) a pantalla interna real (`Page` ganó `"respuesta"`).

**Verificado:** `npx tsc -b --force` sin errores; los 4 `.tsx` nuevos sin error de sintaxis vía Vite; corrida real end-to-end: `GET /api/respuesta` devolviendo `isolated_now: 0` y `isolations: []` (honesto, tal como se esperaba) y **el incidente real creado durante la verificación de la pantalla Incidentes** (`INC-00001`, `PC-RRHH-02`, severidad Alta, en investigación, asignado a Aldahir Fernandez) apareciendo correctamente en `critical_incidents` -- confirma que el filtro de severidad Alta/Crítica sobre incidentes abiertos funciona con datos reales, no solo con la lista vacía.

---

## Pantalla Reports en React (2026-08-15)

**Sexta pantalla del orden acordado.** A diferencia de Acciones de Respuesta, acá todo el backend ya era una funcionalidad completa y real (`/reportes` había dejado de ser un placeholder desde el 12/08) -- generación real de PDF/XLSX con `reportlab`/`openpyxl`, guardado en disco, y descarga del archivo exacto que quedó auditado.

**Backend:**
- `GET /api/reportes` (nuevo, `server/main.py`): versión JSON de `reportes_page` -- mismo historial, mismos KPIs (total de informes, último generado y por quién), mismas opciones (tipo/período/endpoint).
- **Sin endpoints nuevos para generar ni descargar:** `POST /reportes/generar` (arma el PDF/XLSX en el momento con datos reales del período elegido y lo inserta en `reports`) y `GET /reportes/{id}/archivo` (sirve el archivo ya guardado en disco, no regenera -- así la copia descargada siempre coincide con la que quedó auditada) ya existían tal cual y ya los usaba `reportes.html`. Se agregó `/reportes` a la lista de proxy de Vite.
- La descarga en React es un `<a href="/reportes/{id}/archivo">` real (no un `fetch`), igual que en la consola Jinja2 -- así el navegador maneja la descarga del binario (PDF/XLSX) directamente, sin pasarlo por JS.

**Frontend:** `types/reports.ts`, `fetchReportes`/`generateReport` en `api/client.ts`, `ReportsSummaryCards` (2 tarjetas), `GenerateReportForm` (tipo/período/endpoint/formato, sin modal -- es la acción principal de la pantalla, no un detalle secundario), `ReportsHistoryTable` (con el link de descarga real), `ReportsPagination` y `ReportsPage.tsx`. "Reports" pasó de enlace real a `/reportes` a pantalla interna (`Page` ganó `"reportes"`).

**Verificado:** `npx tsc -b --force` sin errores; los 5 `.tsx` nuevos sin error de sintaxis vía Vite; corrida real end-to-end con login real: `GET /api/reportes` con historial vacío inicial; `POST /reportes/generar` generando un Informe de Seguridad General real (`REP-2026-0001`); `GET /api/reportes` mostrando el informe recién creado con los datos correctos (`total_reports: 1`, último generado por Aldahir Fernandez); y la descarga real a través del proxy de Vite devolviendo un PDF válido de verdad (`PDF document, version 1.4, 1 pages`, confirmado con `file`), no solo un 200 vacío.

---

## Pantalla Administración en React -- séptima y última pantalla del orden acordado (2026-08-15)

**Cierra la migración progresiva del prompt maestro.** Cuatro subsecciones dentro de una sola pantalla con tabs internos (estado de React, sin rutas separadas), mapeadas 1:1 a capacidades reales que ya existían repartidas en `/usuarios` y las pestañas `agentes`/`auditoria` de `/configuracion` -- ninguna es nueva, solo se reorganizaron bajo "Administración" como pidió el prompt maestro (Registro de actividad, en particular, deja de ser una pestaña más de Configuración y pasa a vivir ahí, no como módulo aparte del sidebar).

**Backend, 3 endpoints JSON nuevos, todas las escrituras reutilizadas tal cual:**
- `GET /api/users` -- versión JSON de `/usuarios`, misma consulta exacta. Igual que la página real, cualquier sesión válida puede leerla; el `is_admin` de la respuesta es lo que la UI usa para mostrar u ocultar los botones de crear/editar (el propio servidor sigue siendo la única barrera real -- `POST /users`/`PATCH /users/{id}` exigen rol admin de todas formas, ocultar el botón en el cliente es solo UX, no la validación de seguridad).
- `GET /api/config/agentes` -- versión JSON de Configuración > Agentes, solo `agent_stale_seconds` (el único parámetro real).
- `GET /api/audit-logs` -- versión JSON de Configuración > Auditoría, misma consulta paginada sobre `audit_logs`.
- Sin endpoints de escritura nuevos: `POST /users`, `PATCH /users/{id}`, `PATCH /settings/{key}` y `POST /enrollment-tokens` ya existían tal cual y ya los usaban `usuarios.html`/`configuracion.html`. Se agregaron `/users`, `/settings` y `/enrollment-tokens` a la lista de proxy de Vite.

**Frontend:** `types/admin.ts`, las funciones correspondientes en `api/client.ts`, `AdminTabs` (4 pestañas internas), `UsersPanel` + `UserFormModal` (crear/editar, con el aviso "hoy solo existe el rol `admin`" igual que en `usuarios.html`, y las acciones deshabilitadas de verdad -- no solo visualmente -- para quien no es admin), `AgentsPanel` (generación de token de enrolamiento con el token mostrado una sola vez y botón de copiar), `ConfigPanel` (mismo texto exacto de `configuracion.html` para los dos parámetros no aplicables -- Intervalo de Heartbeat y Sincronización de Reglas -- copiado literal, no resumido, para no perder matices ya documentados), `AuditLogPanel` (paginado) y `AdministracionPage.tsx`. `App.tsx` ahora calcula `isAdmin` desde `fetchMe().roles` (antes solo se usaba para la etiqueta de rol en el topbar) y se lo pasa a esta pantalla.

**Con esta pantalla, las 9 rutas del sidebar tienen todas pantalla real en React** -- la migración progresiva acordada el 2026-08-15 ("Jinja2 puede mantenerse temporalmente para las vistas que ya existen... a medida que avancemos con los demás módulos del sistema, los iremos migrando a React") llegó a su fin para el sidebar principal. Las rutas Jinja2 siguen vivas y se siguen usando como destino de varios links cruzados reales (`/incidentes/{id}`, `/reportes/{id}/archivo`, etc.), pero ya no queda ningún ítem del menú que abra una pantalla Jinja2 completa.

**Verificado:** `npx tsc -b --force` sin errores; los 7 `.tsx`/`.tsx` nuevos (más `App.tsx`/`Sidebar.tsx` modificados) sin error de sintaxis vía Vite; corrida real end-to-end con login real: `GET /api/users` con el usuario real (`aldahir`, admin); `POST /users` creando `analista_test` real; `PATCH /users/2` desactivándolo, confirmado en la relectura; `GET /api/config/agentes` con `120`, `PATCH /settings/agent_stale_seconds` a `180` y confirmado, revertido a `120`; `POST /enrollment-tokens` generando un token real de un solo uso; y `GET /api/audit-logs` devolviendo las **9 entradas reales** acumuladas por todas las acciones de prueba de las 6 pantallas anteriores de esta sesión (crear/editar regla, asignar incidente, cambiar su estado, crear/editar usuario, cambiar el parámetro de agentes) -- la mejor confirmación posible de que `audit_logs` es una fuente de verdad real y consistente en toda la aplicación, no datos de muestra aislados por pantalla.

---

## Ajustes post-migración: sidebar siempre oscuro + Incidentes solo-incidentes (2026-08-15)

**Pedido tras terminar las 7 pantallas:**

1. **Barra lateral siempre oscura, incluso en tema claro.** Se envolvió `<Sidebar>` en un `<div data-theme="dark" className="contents">` dentro de `App.tsx` -- las variables CSS del tema (`--surf`, `--tx`, `--brand`, etc.) se resuelven en cascada por `data-theme` en `index.css`, así que anidar un `data-theme="dark"` alrededor del sidebar hace que solo él resuelva siempre la paleta oscura, sin tocar `Sidebar.tsx` ni el resto de la app. `className="contents"` (`display:contents`) evita que el `div` agregue una caja extra al layout flex de `App.tsx` -- el `<aside>` sigue siendo un hijo flex directo a efectos de layout, la franja de bandera boliviana también queda con la opacidad de modo oscuro (`--band-op`) de forma consistente.

2. **Incidentes: la lista ya no mezcla alertas sueltas.** Hasta ahora `GET /api/incidentes` reproducía el mismo `COMBINED_CTE` que `/incidentes` en Jinja2 (incidentes agrupados + alertas sin escalar en una sola matriz). Se pidió que la pantalla en React muestre solo incidentes -- las alertas sueltas ya tienen su propia pantalla dedicada (Alertas), así que mezclarlas acá era redundante y hacía la lista más lenta de leer. Cambio: se agregó `kind = 'incident'` como condición fija en el `WHERE` de `api_incidentes` (antes de cualquier otro filtro). El filtro de "Estado" también se acotó a los 4 buckets que un incidente puede tener de verdad (`nuevo`/`investigando`/`contenido`/`cerrado`) -- `confirmado` y `falso_positivo` son exclusivos de `alerts.status` y, sin alertas en la lista, siempre hubieran devuelto una lista vacía si se dejaban como opción de filtro. El endpoint `/incidentes` en Jinja2 no se tocó -- sigue unificando ambas cosas, como corresponde a su diseño original.

3. **Botón rápido "Aislar equipo" en la tabla.** Se agregó al lado de "Ver más detalles" (antes decía solo "Detalles") en `IncidentesTable.tsx`, para no tener que abrir el drawer para llegar a esa acción. Reusa exactamente el mismo patrón honesto ya establecido en `EndpointDrawer.tsx`/`IncidentDrawer.tsx`: deshabilitado, con el mismo tooltip explicando que el agente no tiene forma de recibir ni ejecutar un comando remoto -- no se fabricó una versión "rápida" que sí funcione cuando la real (en el drawer) tampoco lo hace.

**Verificado:** `npx tsc -b --force` sin errores; corrida real end-to-end: `GET /api/incidentes` devolviendo únicamente `kind: "incident"` en `items`, `status_options` acotado a los 4 buckets reales, y `status=falso_positivo` (ahora inválido para este endpoint) cayendo de forma segura al comportamiento sin filtro en vez de romper o devolver un error.

---

## "Mi perfil" y campana de notificaciones: navegación real (2026-08-15)

**Qué se pidió:** tres arreglos de navegación. (1) "Mi perfil" en el menú de usuario redirigía al dashboard en vez de mostrar el perfil. (2) Al hacer clic en una notificación puntual de la campana, debe abrir la alerta/incidente correspondiente, no quedarse sin hacer nada. (3) "Ver todas las alertas" (pie del dropdown de la campana) debe llevar a la pantalla Alertas.

**(1) "Mi perfil":** mismo bug de proxy encontrado ya varias veces en esta sesión (`/me`, `/logout`, `/alerts`, etc.) -- `@app.get("/perfil")` en `server/main.py` es una página Jinja2 real y completa (confirmado leyendo el código, no es un placeholder), pero `vite.config.ts` no tenía `/perfil` en su lista de proxy hacia `:8000`. Sin eso, el pedido caía en el fallback de SPA de Vite (devuelve `index.html`, no la página real) y React arrancaba de nuevo en su estado por defecto -- de ahí la sensación de "me redirige al dashboard". Se agregó `/perfil` al proxy. No hizo falta tocar `UserMenu.tsx`: su `<a href="/perfil">` ya apuntaba al lugar correcto, el problema era solo de enrutamiento del dev server.

**(2) y (3) Campana de notificaciones:** antes, tanto cada alerta individual como "Ver todas las alertas" eran enlaces `<a href="/incidentes">` -- residuo de antes de que existiera la pantalla Alertas en React dedicada, y que además ni siquiera abrían la alerta puntual, solo la lista general de incidentes. Se cambió a navegación interna real:
- `NotificationsBell.tsx` pasó de `<a>` a `<button>`, con dos props nuevas: `onSelectAlert(id)` (clic en una alerta puntual) y `onViewAll()` (clic en "Ver todas las alertas").
- `Topbar.tsx` recibe y reenvía esas dos props a `NotificationsBell`.
- `App.tsx` las provee: `onSelectAlert` guarda `{ id }` en un estado nuevo (`alertsInitialSelection`, envuelto en un objeto nuevo en cada clic a propósito, para que abrir la misma alerta dos veces seguidas dispare el efecto de todas formas) y cambia a la pantalla Alertas; `onViewAll` solo cambia de pantalla.
- `AlertsPage.tsx` acepta la nueva prop `initialAlertSelection` y, vía `useEffect`, abre el `AlertDrawer` de esa alerta apenas se recibe.

**Decisión de alcance (no over-engineering):** se pidió "la alerta o incidente en cuestión". `GET /alerts/open` (la fuente de datos real de la campana) no expone si una alerta ya fue escalada a un incidente. En vez de agregar ese campo al backend solo para esto, se aprovechó que `AlertDrawer.tsx` **ya** muestra un enlace "Ver incidente #X" cuando la alerta escalada tiene `incident_id` -- así que siempre se navega a Alertas y se abre el drawer de esa alerta puntual; si esa alerta ya es parte de un incidente, el camino a verlo sigue estando a un clic, sin inventar lógica de "¿es alerta o incidente?" en el cliente.

**Verificado de punta a punta (2026-08-15):** `npx tsc -b --force` sin errores. Corrida real con `pgserver` + `uvicorn` + Vite juntos (base nueva sembrada con `database/schema.sql`, un usuario, un endpoint/agente y 2 alertas reales): login real (200), `GET /perfil` a través del proxy devolviendo la página real (200, `<title>ALFA-Sentinel</title>`, contenido de perfil) en vez de caer al fallback de SPA, `GET /alerts/open` a través del proxy devolviendo las 2 alertas sembradas con sus ids reales (la misma respuesta que consume `NotificationsBell.tsx`), y `GET /api/alerts` a través del proxy devolviendo esos mismos ids con toda la data que `AlertDrawer.tsx` necesita. El nuevo wiring de props (`onSelectAlert`/`onViewAll`/`initialAlertSelection`) es lógica pura de cliente sin llamada a red adicional -- queda cubierto por el type-check limpio más la confirmación de que los datos que consume (`/alerts/open`, `/api/alerts`) fluyen correctamente a través del proxy.

---

## Perfil nativo en React + escalamiento manual de alerta a incidente (2026-08-15)

**Corrección sobre el arreglo anterior de "Mi perfil":** el fix del 2026-08-15 de más arriba dejó `<a href="/perfil">` apuntando a la página Jinja2 real (`perfil.html`) a través del proxy de Vite -- funcionaba (dejó de "redirigir al dashboard"), pero abría una pantalla con un sistema de diseño completamente distinto al Nocturne del resto de la consola React (otro layout, otro sidebar, otra tipografía). Se pidió explícitamente que Perfil sea una pantalla nativa de React, construida con los mismos patrones ya establecidos en el resto de la app -- no una reutilización visual de la versión Jinja2 vieja. `server/templates/perfil.html` y `@app.get("/perfil")` **no se tocaron** -- siguen existiendo tal cual, accesibles por URL directa, pero ya nada en la UI de React enlaza ahí.

**Backend, un endpoint JSON nuevo, cero lógica nueva:**
- `GET /api/perfil` -- misma consulta exacta que ya usaba `perfil_page()` (username, full_name, email, created_at, last_login_at), más `is_active` (columna real de `users` que `perfil_page` no seleccionaba) y `roles` (ya viene en la sesión, no hace falta otra consulta).
- `PUT /me` y `POST /me/password` **ya existían y funcionaban** (`update_profile`/`change_password`) pero no los usaba ninguna pantalla React todavía -- se conectaron tal cual, sin cambiarles una línea.

**Frontend:** `pages/PerfilPage.tsx` + dos cards con el mismo patrón visual que `ConfigPanel.tsx`/`UserFormModal.tsx` (mismos bordes, radios, tipografía, inputs, botón "Guardar" que aparece solo cuando hay cambios sin guardar):
- `ProfileInfoCard.tsx`: nombre completo y correo editables (`PUT /me`, real); username, rol, estado de la cuenta y último inicio de sesión de solo lectura (no editables porque no hay endpoint de self-service para eso -- rol lo cambia un admin desde Administración, username no se puede editar, estado/último login los administra el propio sistema).
- `ProfileSecurityCard.tsx`: cambio de contraseña (`POST /me/password`, real, exige la contraseña actual correcta).
- Se llega desde "Mi perfil" en `UserMenu.tsx` (ahora un botón con navegación interna `onOpenProfile`, ya no un `<a href="/perfil">`), no desde el sidebar -- igual que la página Jinja2 tampoco estaba en el nav lateral.

**No se agregó a propósito** (siguiendo el pedido explícito de no inflar la pantalla): estadísticas, actividad, sesiones activas, 2FA, ni ninguna configuración que ya vive en Administración (eso sigue siendo "administración del sistema", Perfil sigue siendo "la cuenta de quien está logueado" -- no se mezclaron).

**Escalamiento manual de alerta a incidente:** ya existía el endpoint real (`POST /incidents`, `create_incident()`) y hasta el flujo de UI completo -- pero vivía en `IncidentDrawer.tsx`, en una rama `selected.kind === "alert"` que quedó **inalcanzable** desde que Incidentes se acotó a mostrar solo incidentes (ver entrada "Ajustes post-migración" más arriba) -- nada llama más a ese drawer con `kind: "alert"`. El pedido fue traer esa misma funcionalidad a donde sí se usa hoy: `AlertDrawer.tsx`, en la pantalla Alertas.

- **Sin incidente todavía:** botón "Escalar a incidente" (estilo `--brand`, no `--crit` -- es una acción de gestión, no destructiva, a propósito distinta del tratamiento de "Aislar endpoint"). Abre `EscalateAlertModal.tsx` (nuevo, mismo patrón de modal que `UserFormModal.tsx`) con confirmación real: título, endpoint, severidad, risk score, fecha y regla asociada (si existe) -- todo dato ya cargado en el drawer, nada inventado. Confirmar llama a `escalateAlertToIncident()` (ya existía en `api/client.ts`, apuntando a `POST /incidents`, reusado tal cual).
- **Con incidente:** el bloque pasa a mostrar "Incidente asociado" + el código (`INC-00025`, mismo formato `f"INC-{id:05d}"` que ya usa el resto del sistema) y un botón "Ver incidente" que navega internamente a Incidentes y abre ese incidente puntual -- reemplaza el `<a href="/incidentes/{id}">` que había antes (mismo problema de fondo que "Mi perfil": mandaba a la consola Jinja2 vieja).
- El escalamiento manual **no reemplaza** el automático -- `create_incident()` no se tocó, sigue siendo el mismo endpoint que ya usaba el motor heurístico indirectamente (vía `alerts.incident_id`); ambos caminos terminan en la misma columna. No se restringió el botón por rol: `POST /incidents` usa `Depends(get_current_user)`, no `require_role`, así que cualquier sesión válida puede escalar hoy -- el frontend no inventa una restricción que el backend no aplica.
- **Alerta de origen en el incidente:** `get_incidente_drawer()` (`GET /api/incidentes/{kind}/{id}/drawer`) ahora también devuelve `origin_alert` (solo para `kind == "incident"`) -- la primera alerta, por fecha, vinculada a ese incidente (código, severidad, risk score), sea que haya llegado ahí por el motor automático o por escalamiento manual. `IncidentDrawer.tsx` la muestra en una sección nueva "Alerta de origen" con un botón "Ver alerta original" que navega a Alertas y abre esa alerta puntual. Se reutilizó la consulta que ya traía las alertas vinculadas a un incidente (antes solo se usaba para calcular `is_honeyfile`/`anchor_ts`) agregándole `alerts.id`, `severity_levels.name` y `alerts.risk_score` -- no se creó tabla, relación ni historial nuevo, todo sale de `alerts.incident_id`, que ya existía.
- De paso se expuso `created_at` en la respuesta del drawer (ya se calculaba como `anchor_ts` para la ventana de la cadena de evidencia, pero nunca se devolvía) -- lo usa tanto el modal de confirmación de escalamiento como, en general, cualquier pantalla que abra este drawer.

**Navegación interna reutilizada, mismo patrón que la campana de notificaciones (entrada anterior):** `App.tsx` ahora tiene `incidentesInitialSelection` (mismo patrón que `alertsInitialSelection`, objeto nuevo en cada click) y dos funciones compartidas, `openAlert(id)`/`openIncident(id)`, usadas tanto por la campana como por "Ver incidente"/"Ver alerta original" -- una sola forma de navegar entre Alertas e Incidentes en toda la app, no una implementación distinta por cada botón.

**Distinción conceptual respetada:** Alertas sigue mostrando únicamente alertas (`GET /api/alerts` no se tocó) e Incidentes únicamente incidentes (`GET /api/incidentes` sigue con `kind = 'incident'` fijo, sin cambios) -- la relación entre ambas pantallas viaja solo a través de `alerts.incident_id`, nunca mezclando los dos listados.

**Verificado de punta a punta (2026-08-15):** `npx tsc -b --force` sin errores. Corrida real con `pgserver` + `uvicorn` + Vite juntos (base nueva, un usuario, un endpoint/agente, una alerta `HIGH` con una regla real vinculada vía `alert_rule`): `GET /api/perfil` con los 7 campos reales; `PUT /me` actualizando nombre/correo y confirmado en una relectura posterior; `POST /me/password` rechazando la contraseña actual incorrecta (401) y aceptando la correcta (200); drawer de la alerta antes de escalar (`incident_id: null`, `origin_alert: null`, `created_at` poblado, regla real en `rules[]`); `POST /incidents` escalando esa alerta (`{"incident_id": 1}`); drawer de la misma alerta después (`incident_id: 1`); drawer del incidente resultante con `origin_alert` completo (`ALT-00001`, `HIGH`, `78.0`) y `created_at` poblado; y `GET /api/incidentes` mostrando el incidente nuevo en la lista, igual que cualquier otro.

---

## Drawers no deben auto-abrirse + fila seleccionada resaltada (2026-08-15)

**Bug real encontrado y corregido (root cause):** desde el arreglo de la campana de notificaciones (entrada de más arriba), `App.tsx` guarda la selección pendiente de una notificación en `alertsInitialSelection`/`incidentesInitialSelection` -- estado que vive en `App.tsx`, no en `AlertsPage.tsx`/`IncidentesPage.tsx` (esas páginas se desmontan por completo cada vez que se cambia de pantalla, porque `App.tsx` las renderiza con una cadena de ternarios que intercambia el tipo de componente). El problema: esos dos estados **nunca se limpiaban** después de usarse. Resultado real observado: si alguna vez se entraba a una alerta/incidente desde una notificación, esa selección quedaba en memoria para siempre -- la próxima vez que se entraba a Alertas o Incidentes **por el sidebar** (navegación común, sin ninguna intención de ver ese registro puntual), `AlertsPage`/`IncidentesPage` se remontaban, leían el mismo `initialAlertSelection`/`initialSelection` todavía no nulo, y reabrían el drawer de esa vieja notificación. Esto es justo el síntoma descrito: "el drawer se abre solo al entrar a la pantalla".

**Corrección:** `App.tsx` ahora distingue explícitamente dos tipos de navegación:
- `navigateTo(page)` -- navegación "plana" (clic en el sidebar, "Mi perfil", "Ver todas las alertas" de la campana): **siempre** limpia `alertsInitialSelection` y `incidentesInitialSelection` antes de cambiar de pantalla. Es la única vía por la que se llega a Alertas/Incidentes sin querer ver un registro puntual, así que es el único lugar responsable de que el drawer arranque cerrado.
- `openAlert(id)` / `openIncident(id)` -- navegación con intención explícita de ver un registro concreto (clic en una notificación, "Ver incidente" desde una alerta, "Ver alerta original" desde un incidente): estas sí dejan la selección pendiente a propósito, es la excepción válida que pidió el requerimiento.

`Sidebar`'s `onNavigate`, `onViewAllAlerts` y `onOpenProfile` pasaron de `setPage` directo a `navigateTo`. `openAlert`/`openIncident` no cambiaron -- ya hacían lo correcto, el problema nunca fue esa parte.

**Registro seleccionado resaltado visualmente:** nuevo hook compartido `hooks/useRowFlash.ts` y helper `lib/rowSelection.ts`, usados igual en las 4 tablas con drawer de detalle (`AlertsTable`, `IncidentesTable`, `EndpointsTable`, `HoneyfilesTable`):
- Al abrir un drawer, la fila correspondiente recibe el mismo tratamiento visual que ya usa el ítem activo del sidebar (`background: var(--brand-soft)` + barra izquierda `var(--brand)`, ver `Sidebar.tsx`) -- mismo lenguaje visual ya establecido en la app, no un color ni efecto nuevo.
- A los ~6.5s ese fondo se desvanece solo, vía una transición CSS (`transition: background-color 2.5s ease`), sin ningún `setTimeout` que corte el color de golpe -- queda solo la barra izquierda, un indicador persistente y sutil, mientras el drawer de ese registro siga abierto.
- Al cerrar el drawer (`selectedId` vuelve a `null`), la fila pierde tanto el fondo como la barra -- no queda nada marcado.
- Al seleccionar otro registro, `selectedId` cambia de valor -- la fila anterior automáticamente deja de cumplir la comparación `id === selectedId` (vuelve a normal) y la nueva la cumple (recibe el flash + la barra) en el mismo render, sin lógica adicional para "desactivar la anterior".
- La barra izquierda de selección no choca con el borde de color por severidad que ya tenían las tablas (`boxShadow: inset 3px 0 0 accent` en la primera celda) -- son elementos distintos (una vive en el `<tr>` como `borderLeft`, la otra en el primer `<td>` como `boxShadow`), así que ambos se ven al mismo tiempo sin pisarse.
- Se corrigieron de paso los manejadores `onMouseEnter`/`onMouseLeave` de las 4 tablas: antes `onMouseLeave` siempre restauraba el fondo a `""` (vacío), lo que hubiera borrado el resaltado de selección al sacar el mouse de una fila seleccionada -- ahora restaura al fondo que le corresponde según su propio estado (`transparent` o `var(--brand-soft)` si sigue "flasheando"), no a un valor fijo.
- Incidentes compara por una clave combinada `"kind:id"` (ej. `"incident:7"`) en vez de solo `id`, porque su tipo de selección incluye `kind` -- incluso aunque hoy la tabla de Incidentes solo muestra `kind: "incident"` (ver "Ajustes post-migración" más arriba), se dejó preparado por si ese acotamiento cambia más adelante.

**No incluido a propósito, siguiendo el pedido explícito:** ninguna tabla nueva, columna nueva, ni cambio de API o de base de datos -- las 4 tablas ya recibían `onSelect`/el id seleccionado vivía en la página; lo único nuevo es un id extra (`flashId`) calculado en el cliente con un `setTimeout`, y un par de propiedades de estilo por fila.

**Verificado:** `npx tsc -b --force` sin errores en los 12 archivos tocados (`App.tsx`, 4 páginas, 4 tablas, el hook y el helper nuevos). No hubo llamada de red nueva que verificar (el pedido fue explícitamente "no cambiar la API ni la base de datos") -- la corrección es lógica de estado y estilos 100% del lado del cliente, revisada línea por línea: los cuatro pares página/tabla siguen exactamente el mismo patrón (`selectedId`/`flashId` para Alertas, Endpoints y Honeyfiles; `selectedKey`/`flashKey` para Incidentes), y el flujo de `App.tsx` (`navigateTo` vs. `openAlert`/`openIncident`) se repasó contra los 5 casos del pedido (entrada normal, ver detalles, cerrar, abrir otro registro, entrada desde notificación) confirmando que cada uno cae en la rama correcta.

---

## Motor de reglas heurísticas -- especificación definitiva (2026-08-16)

**Qué se pidió:** una especificación funcional de 40 secciones para reescribir por completo el motor de detección: separar detección / cálculo de riesgo / alerta / incidente / aislamiento en responsabilidades distintas, pasar de 4 a 12 reglas heurísticas (HR-01 a HR-12), mover el cálculo del `risk_score` y la severidad del agente al servidor, agregar una tabla `metric_types`, definir una bonificación de correlación entre reglas (HR-12) y políticas explícitas de cuándo crear un incidente automáticamente y cuándo recomendar aislamiento -- con la restricción explícita de no inventar tablas/columnas, no simular datos que el agente no recopila, y documentar qué falta en vez de fingir que existe.

**Investigación previa (antes de tocar nada):** se leyó `database/schema.sql` completo, `agent/heuristic_engine.py`, `agent/file_monitor.py`, y las secciones relevantes de `server/main.py` (`report_alert`, `AlertCreate`, `get_rule_policy`, `create_incident`, los diccionarios de etiquetas en español, y las ~50 consultas que ya leen `heuristic_rules`/`ALERT_RULE_LABELS_ES` de forma genérica). Confirmado: `metric_types` **no existía** (la especificación asumía que sí) -- se creó desde cero. El motor viejo tenía 4 reglas hardcodeadas en el agente, que calculaba su propio score y severidad (`FileActivityAnalyzer.calculate_score()`/`get_risk_level()`) y mandaba una sola regla por alerta (`rule_name`) -- incompatible con el requisito de explicabilidad multi-regla (`alert_rule` guardando **todas** las reglas que participaron).

**Decisión de diseño central: el servidor pasa a ser la autoridad del score, el agente solo detecta.** Nuevo contrato de `POST /agent/alerts` (`AlertCreate`): el agente ya no manda `severity`/`risk_score`/`rule_name` -- manda `matched_rules: list[str]`, los nombres de las reglas que detectó activas en este evento. El servidor (`report_alert`, reescrito) es quien: busca el peso real de cada regla en `heuristic_rules`, inserta una fila en `alert_rule` por cada regla nueva (sin duplicar evidencia ya registrada del mismo episodio), calcula la bonificación de correlación (HR-12), suma y acota a 100, deriva la severidad consultando `severity_levels WHERE score BETWEEN min_score AND max_score` (nunca un diccionario Python hardcodeado que se pueda desincronizar de la base), decide si corresponde crear un incidente, y evalúa (sin ejecutar) si se cumple la condición de aislamiento.

**Triage de las 12 reglas -- 9 implementables ahora, 3 diferidas (sección 40 de la especificación, aplicada literalmente):**
- **Implementables con datos que el agente ya recopila** (ruta + tipo de evento de `watchdog`, sin inspeccionar proceso ni contenido): HR-01 (`mass_file_activity`), HR-02 (`ransomware_extension_rename`), HR-03 (`honeyfile_access`), HR-04 (`intensive_write_activity`, nueva), HR-07 (`shared_path_access`, nueva -- clasifica rutas UNC/`//servidor/recurso` por patrón), HR-08 (`mass_temp_file_creation`, nueva -- extensión `.tmp`/carpeta `temp`), HR-09 (`mass_deletion`), HR-10 (`user_file_activity`, nueva -- carpetas `Documents/Desktop/Downloads/Pictures/...` por patrón de ruta), HR-12 (`multi_indicator_correlation`, aritmética pura del servidor).
- **Diferidas, sembradas con `is_active=FALSE`** porque requieren datos que el agente NO recopila hoy y que **no se simularon**: HR-05 `suspicious_process` (necesita atribuir un proceso a cada evento de archivo -- watchdog no lo expone), HR-06 `high_cpu_usage` (necesita muestreo de CPU por proceso, el agente nunca lo mide), HR-11 `automated_repetitive_activity` (mismo problema de atribución de proceso que HR-05). Cada una queda con su `description` explicando exactamente qué le falta al agente, visible en la pantalla de Reglas Heurísticas -- no se ocultan, se muestran deshabilitadas con motivo.
- **Guardrail agregado que la especificación no pedía explícitamente pero se dedujo necesario:** `PATCH /rules/{id}` ahora rechaza (422) activar una de estas 3 reglas desde `/configuracion` o `RulesPage.tsx`, con un mensaje explicando por qué -- sin este bloqueo, un admin podría poner `is_active=TRUE` desde la UI y la regla seguiría sin evaluarse nunca (el agente ni siquiera la conoce, `agent/heuristic_engine.py::RULE_NAMES` no la incluye), lo que hubiera sido una función fantasma. `RuleCard.tsx` refleja lo mismo del lado del cliente: en vez del botón "Inactiva" clickeable, estas 3 muestran una etiqueta "Diferida" no interactiva con tooltip.

**HR-03 (honeyfile) llega a `risk_score = 100` sin ningún caso especial en el código:** su fila en `heuristic_rules` tiene `weight = 100` directamente, así que la fórmula genérica `MIN(100, suma_de_pesos + correlación)` da 100 automáticamente en cuanto `honeyfile_access` participa -- exactamente el comportamiento pedido ("no usar +40, no esperar a otras reglas") sin un `if is_honeyfile: score = 100` separado que hubiera sido una segunda fuente de verdad.

**HR-12 (correlación) se implementó como una fila sintética, no como una regla de conteo:** existe una fila real en `heuristic_rules` (`multi_indicator_correlation`, `metric_type = MULTI_INDICATOR_CORRELATION`) para que aparezca en la UI de explicabilidad existente sin cambios, pero el servidor no la evalúa por threshold/window -- cuenta cuántas reglas *distintas* (sin contar la fila de correlación misma) están vinculadas a la alerta y aplica la bonificación por tramos (2 reglas -> +5, 3 -> +10, 4+ -> +15), guardando el valor real aplicado en `alert_rule.weight_applied` (no el peso "de catálogo" de la fila, que es solo un valor documental de referencia, 15.00). Respeta `is_active` como cualquier otra regla: si se desactiva desde `/configuracion`, deja de sumar bonificación.

**"Mismo episodio", explícito y documentado (no un valor mágico oculto):** una ráfaga de eventos del mismo agente se agrupa en una sola alerta (actualizando `risk_score`/`severity`/`alert_rule` in situ) en vez de crear una alerta nueva por evento, mientras la alerta siga `NEW`/`ACKNOWLEDGED` y tenga menos de `EPISODE_WINDOW_SECONDS = 120` segundos -- constante nombrada en `server/main.py`, con el razonamiento en el comentario (generosa respecto a las ventanas de 10-20s de las reglas individuales, para que una ráfaga que dispara varias reglas en sucesión caiga en la misma alerta). Reenviar una regla ya vinculada a la alerta del episodio no duplica su fila en `alert_rule` ni vuelve a sumar su peso.

**Política de incidente automático (sección 28) y de aislamiento (sección 30), implementadas literalmente, con la interpretación de "evidencia/indicador fuerte" documentada en el código** (`STRONG_RULE_NAMES` = las reglas de peso >= 15: `mass_file_activity`, `ransomware_extension_rename`, `honeyfile_access`, `intensive_write_activity`, `shared_path_access`, `mass_deletion`):
- Incidente automático: `score >= 75` Y (honeyfile activado, O correlación de >= 3 reglas distintas, O >= 2 reglas "fuertes" distintas).
- Aislamiento (Condición A): honeyfile + al menos 1 regla fuerte de actividad de archivos (sin contar el honeyfile mismo).
- Aislamiento (Condición B): `score >= 75` + al menos 2 reglas fuertes de actividad de archivos distintas.
- El aislamiento **solo se evalúa si ya existe un incidente** (coherente con el diagrama de la sección 1: alerta -> ¿incidente? -> si sí, ¿aislamiento?) -- nunca se evalúa aislamiento sobre una alerta sin incidente.
- Se registra como recomendación, no como ejecución real: `host_isolations` gana un status nuevo, `'RECOMMENDED'` (`agent_id`, `incident_id`, `isolation_type='NETWORK'`, `reason` con el detalle de qué condición se cumplió y con qué reglas) -- honesto con la limitación de siempre: el agente sigue sin canal de comandos remotos (`agent/main.py` de una sola pasada), así que nada ejecuta el aislamiento de verdad. `GET /api/respuesta` (pantalla Acciones de Respuesta, que ya existía como placeholder honesto porque `host_isolations` estaba siempre vacía) ahora sí puede mostrar filas reales -- se le agregaron `ISOLATION_STATUS_LABELS_ES`/`ISOLATION_TYPE_LABELS_ES` (`RECOMMENDED` -> "Recomendado (no ejecutado)") y se actualizó el texto de `RespuestaPage.tsx`/`IsolationsHistoryTable.tsx` para no seguir diciendo "nunca hay nada acá" ahora que puede haberlo.

**Escalamiento manual (sección 29):** no se tocó -- ya funcionaba (`POST /incidents`, ver entrada "Perfil nativo..." más arriba) y sigue coexistiendo con el automático sin ninguna relación especial entre ambos, tal como pedía la especificación.

**Etiquetas en español actualizadas a los 4 niveles pedidos (BAJO/MEDIO/ALTO/CRÍTICO):** se decidió **no** renombrar los valores internos de `severity_levels.name` (siguen siendo `NORMAL`/`SUSPICIOUS`/`HIGH`/`CRITICAL`, usados como literal en decenas de consultas SQL y en `frontend/src/types/dashboard.ts`) -- renombrarlos hubiera sido un cambio de arquitectura no necesario para cumplir el pedido (sección 40: "no cambies la arquitectura existente sin necesidad"). Lo que pide la especificación (que el usuario vea "Bajo/Medio/Alto/Crítico") se resolvió en la capa de traducción: `RISK_LABELS_ES`/`ALERT_SEVERITY_LABELS_ES` en `server/main.py` y `SEVERITY_LABEL` en `frontend/src/lib/severity.ts` pasaron de Normal/Sospechoso/Alto/Crítico a Bajo/Medio/Alto/Crítico, junto con los mismos textos hardcodeados en `dashboard_page`/`api_dashboard_overview` (listas `risk_distribution`) y en el toast de notificaciones de `base.html`. Los rangos de `severity_levels` sí se actualizaron de verdad: 0-24.99 / 25-49.99 / 50-74.99 / 75-100 (antes 0-29.99 / 30-59.99 / 60-79.99 / 80-100).

**`ALERT_RULE_LABELS_ES` reescrito con las 12 reglas** (`"HR-01 · Modificación masiva de archivos"`, etc., incluidas las 3 diferidas marcadas `"(diferida)"` y la de correlación) -- como esta constante ya se leía de forma genérica desde ~15 lugares distintos de `server/main.py` (dashboard, reportes PDF/XLSX, exportaciones, drawers, `/configuracion`), actualizar solo el diccionario propagó las 12 reglas a todos esos lugares sin tocarlos uno por uno.

**No se implementó (a propósito, siguiendo la sección 40):** entropía (HR-FUTURE, explícitamente fuera de alcance), ejecución real de aislamiento (`host_isolations.status` en `'REQUESTED'`/`'EXECUTED'` sigue sin que nada lo escriba -- el agente sigue sin canal remoto), y ninguna de las 3 reglas diferidas con datos simulados.

**Verificado de punta a punta (2026-08-16), con un arnés de pruebas real contra `pgserver` + `uvicorn` (base sembrada desde `database/schema.sql` tal cual, sin atajos) -- 30 verificaciones, todas en verde:**
- HR-01 sola -> `risk_score=25.0`, `SUSPICIOUS` (Medio), sin incidente.
- Mismo episodio + HR-02 -> misma alerta, `score=50.0` (25+20+5 de correlación de 2 reglas), `HIGH` (Alto).
- + HR-09 + HR-10 en el mismo episodio -> `score=85.0` (25+20+15+10+15 de correlación de 4 reglas), `CRITICAL`, incidente creado automáticamente (score>=75 + 3 reglas fuertes), aislamiento recomendado (Condición B, 3 reglas fuertes de archivos).
- Reenviar HR-01 ya vinculada -> el score no cambia y `alert_rule` sigue con una sola fila para esa regla (no duplica evidencia).
- Honeyfile solo, episodio nuevo -> `score=100.0`, `CRITICAL`, incidente creado (evidencia fuerte por sí sola), **sin** aislamiento recomendado (Condición A exige honeyfile + otro indicador fuerte, que acá no está).
- Honeyfile + `mass_deletion` (mismo evento, agente nuevo) -> `CRITICAL`, aislamiento recomendado (Condición A cumplida).
- `GET /api/rules` -> exactamente las 12 reglas esperadas por nombre, las 3 diferidas con `is_active=false`, `honeyfile_access.weight=100`.
- `PATCH /rules/{id_diferida}` con `is_active=true` -> `422`, con el motivo explicado.
- `GET /agent/rule-policy` -> 9 reglas activas (las 8 evaluables por el agente + correlación); `FileActivityAnalyzer.from_policy()` ignora `multi_indicator_correlation` sin romperse y termina con exactamente las 8 reglas que sabe evaluar.
- Ventana deslizante real: 20 eventos `file_deleted` sintéticos activan HR-09 (`mass_deletion`).
- `GET /api/respuesta` -> refleja una fila real `status=RECOMMENDED`, con `status_label="Recomendado (no ejecutado)"`.

Además, `npm run build` (`tsc -b && vite build`) del frontend completo sin errores, cubriendo los tipos nuevos/tocados (`types/respuesta.ts`, `IsolationsHistoryTable.tsx`, `RuleCard.tsx`, `lib/severity.ts`).

---

## Pantalla de Reglas Heurísticas ampliada + edición por modal (2026-08-16)

**Qué se pidió:** completar la pantalla "Reglas heurísticas" para que muestre el modelo completo de cada una de las 12 reglas (identificación, métrica con su unidad, evento, parámetros, actividad real y auditoría), y que cada regla se pueda editar desde un modal que reutilice exactamente el patrón visual ya existente en la app -- sin rediseñar nada, sin ocultar ninguna de las 12 reglas, sin inventar datos que no existen.

**`heuristic_rules` no tenía `created_at`** (a pesar de que la especificación, tanto esta como la del motor heurístico de más arriba, asumía que sí) -- se agregó la columna (`DEFAULT CURRENT_TIMESTAMP`, mismo patrón que el resto de tablas del sistema) porque la pantalla la pide explícitamente ("Fecha de creación") y es la única forma honesta de mostrarla sin inventar una fecha. Los valores de las 12 reglas sembradas quedan con la fecha real de cuando se cargó el schema -- no se fabricó una fecha "más vieja" para simular antigüedad.

**`GET /api/rules` reescrito** para traer, además de lo que ya devolvía (peso/umbral/ventana/activa/actualizada, alertas en 30 días, última activación -- todo esto ya real), lo que faltaba: `metric_type_name`/`metric_type_description`/`metric_unit` (JOIN nuevo contra `metric_types`, la unidad sigue viviendo solo ahí, no se duplicó en `heuristic_rules`), `event_type_description` (ya existía en `event_types`, no se usaba), y `created_at`. También devuelve tres banderas calculadas en el servidor -- `is_deferred`, `is_honeyfile`, `has_fixed_scoring` -- para que el frontend no tenga que mantener su propia copia de qué reglas son especiales (antes `RuleCard.tsx` tenía su propio `DEFERRED_RULE_NAMES` hardcodeado, duplicado del que ya existía en `server/main.py`; ahora hay una sola fuente de verdad, la misma que valida `PATCH /rules/{id}`).

**`PATCH /rules/{id}` con validación real por regla, no genérica:**
- El peso ahora se valida 0-100 (antes solo se rechazaba negativo).
- Nueva constante `FIXED_SCORING_RULE_NAMES = {"honeyfile_access", "multi_indicator_correlation"}`: bloquea (422, con el motivo explicado) cualquier intento de cambiar `weight`/`threshold`/`window_seconds` en estas dos reglas, porque ninguna de las dos funciona como una regla convencional de puntuación -- el peso de honeyfile es 100 fijo (es lo que hace que cualquier interacción llegue a CRÍTICO automáticamente, ver la entrada de más arriba) y la bonificación de correlación la calcula `report_alert` por tramos fijos, sin leer la columna `weight` de esa fila (que es solo documental). `is_active` sigue editable en ambas -- eso sí tiene efecto real.
- La auditoría (`log_audit`, tabla `audit_logs` ya existente, sin tabla nueva) ahora registra valor **anterior y nuevo** de cada campo cambiado (`"peso: 25.00 -> 30.0"`), no solo el nuevo como antes -- se leen los valores viejos con un `SELECT` antes del `UPDATE`, en la misma transacción.

**Frontend, sin inventar un sistema de componentes nuevo:**
- `RuleCard.tsx` se amplió (mismo contenedor, mismos bordes/radios/tipografía) con una cuadrícula de 12 datos por regla: métrica + unidad, evento, estado, threshold, ventana, peso, alertas (30 días), última activación, creada, última actualización -- reemplazando el input de peso inline y el botón de estado clickeable por un badge de solo lectura (Activa/Inactiva/Diferida) y un botón "Editar" que abre el modal. Los campos fijos de honeyfile/correlación muestran "No aplica" en vez de un número que no significa nada. Cuando no hay actividad, se muestra "Sin actividad registrada" / "No disponible" -- nunca un valor inventado.
- `RuleEditModal.tsx` (nuevo) reutiliza el patrón exacto de `UserFormModal.tsx` (overlay + tarjeta centrada `rounded-2xl`, header eyebrow + título + X, cuerpo con inputs `fieldStyle`, footer Cancelar/Guardar): arriba un bloque de contexto de solo lectura (nombre, métrica, evento -- los campos que la especificación prohíbe editar), luego, según el tipo de regla: para HR-03 un aviso en rojo (`--crit-soft`) explicando que clasifica automáticamente a CRÍTICO con risk score 100 fijo, sin campos de peso; para la correlación un aviso informativo (`--info-soft`) explicando la bonificación por tramos; para el resto, los tres inputs editables (Weight/Threshold/Window) con su unidad debajo de cada uno. El checkbox "Regla activa" se deshabilita con tooltip para las 3 reglas diferidas que siguen inactivas (coherente con el bloqueo que ya hace el servidor).
- El botón "Editar" y el modal existen para las 12 reglas por igual -- ninguna se oculta ni se excluye, incluidas las 3 diferidas (que siguen mostrando su explicación de qué le falta al agente) y las 2 de puntuación fija.

**Verificado de punta a punta (2026-08-16):** `npm run build` (`tsc -b && vite build`) sin errores. Corrida real contra `pgserver` + `uvicorn` con la base sembrada desde `database/schema.sql` -- 25 verificaciones, todas en verde: las 12 reglas se devuelven completas con métrica/unidad/evento/fechas reales; `alerts_30d`/`last_triggered_at` en `0`/`None` para una regla sin actividad (no inventado); las banderas `is_deferred`/`is_honeyfile`/`has_fixed_scoring` correctas para HR-01/HR-03/HR-05/HR-12; editar el peso de HR-01 devuelve `200` y la auditoría queda con `"peso: 25.00 -> 30.0"`; `weight=150` rechazado (422, fuera de 0-100); cambiar el peso de honeyfile rechazado (422) pero cambiar su `is_active` sí funciona (200); cambiar el `threshold` de la regla de correlación rechazado (422); activar una regla diferida sigue rechazado (422, mismo guardrail de antes).

---

## Traducción a español de `heuristic_rules.name` y `metric_types.name` (2026-08-16)

**Qué se pidió:** el usuario reportó, al inspeccionar su base real con `psql` (`\d heuristic_rules`, `\d metric_types` y `SELECT` directos), que le faltaba `heuristic_rules.created_at` (causa real de "Reglas Heurísticas no se pudo cargar" -- ver entrada de arriba) y que el texto de `metric_types.description` estaba corrupto (mojibake: `"archivos se±uelo"` en vez de `"archivos señuelo"`, `"modificaci¾n"` en vez de `"modificación"`). Pedido explícito del usuario: **"quiero que cambies los nombres de metric_types y heuristic_rules"** -- traducir también los identificadores `name` de ambas tablas (que hoy están en inglés) al español, no solo arreglar el texto corrupto.

**Antes de tocar nada se verificó dónde se usa cada `name` como identificador de código** (no solo como dato), porque eso determina el riesgo real de renombrar:
- `metric_types.name` (ej. `FILE_MODIFICATIONS`) **nunca** se usa como literal en lógica Python/TypeScript -- solo aparece en `database/schema.sql` (`SELECT id FROM metric_types WHERE name = 'X'` al sembrar `heuristic_rules`) y en comentarios/documentación. Renombrarlo es cosmético, bajo riesgo.
- `heuristic_rules.name` (ej. `mass_file_activity`) sí se usa como literal en `server/main.py` (`DEFERRED_RULE_NAMES`, `FIXED_SCORING_RULE_NAMES`, `ALERT_RULE_LABELS_ES`, consultas SQL con `WHERE name = '...'`), en `agent/heuristic_engine.py` (`RULE_NAMES`, `DEFAULT_RULES`, todos los `if "X" in self.rules`), en `agent/file_monitor.py` (`RULE_TITLES`) y en un comentario de `agent/honeyfile_deployer.py`. Renombrarlo exige actualizar código real en varios archivos, no solo la base.

**Los 12 nombres nuevos (español), uno por regla/métrica:**

| # | `heuristic_rules.name` nuevo | `metric_types.name` nuevo |
|---|---|---|
| HR-01 | `modificacion_masiva_archivos` | `MODIFICACIONES_ARCHIVOS` |
| HR-02 | `renombrado_extension_anomala` | `RENOMBRADOS_ARCHIVOS` |
| HR-03 | `acceso_honeyfile` | `ACCESO_HONEYFILE` |
| HR-04 | `escritura_intensiva_archivos` | `ESCRITURAS_ARCHIVOS` |
| HR-05 | `proceso_sospechoso` | `PROCESOS_SOSPECHOSOS` |
| HR-06 | `consumo_cpu_elevado` | `CPU_PROCESO` |
| HR-07 | `acceso_recursos_compartidos` | `ACCESO_RECURSOS_COMPARTIDOS` |
| HR-08 | `creacion_masiva_temporales` | `CREACION_ARCHIVOS_TEMPORALES` |
| HR-09 | `eliminacion_anomala_archivos` | `ELIMINACIONES_ARCHIVOS` |
| HR-10 | `actividad_archivos_usuario` | `ACTIVIDAD_ARCHIVOS_USUARIO` |
| HR-11 | `actividad_repetitiva_automatizada` | `ACTIVIDAD_AUTOMATIZADA_ARCHIVOS` |
| HR-12 | `correlacion_multiples_indicadores` | `CORRELACION_MULTIPLES_INDICADORES` |

**Código actualizado** (reemplazo literal en todo el archivo, confirmado con `grep` que no queda ningún nombre viejo y con `py_compile` que los 4 archivos Python siguen siendo válidos): `server/main.py`, `agent/heuristic_engine.py`, `agent/file_monitor.py`, `agent/honeyfile_deployer.py` (solo un comentario), `database/schema.sql` (seed de ambas tablas). En `frontend/src/components/RuleCard.tsx` se aprovechó para sacar el único literal de nombre de regla que quedaba en el frontend (`rule.name === "multi_indicator_correlation"`) y reemplazarlo por la bandera `rule.has_fixed_scoring` que ya calcula el servidor -- una mejora aparte, no dependía del idioma del nombre.

**Migración para la base real del usuario (`database/migration_2026-08-16_reglas_heuristicas.sql`, reescrita):** la v1 de este archivo (de la entrada anterior) asumía que la base no tenía `metric_types` ni `heuristic_rules.metric_type_id` -- asunción incorrecta que el propio usuario corrigió ("yo mismo agregue esas tablas"). La v2 parte de lo que su `\d`/`SELECT` real mostró: `metric_types` ya existe con nombres en inglés; `heuristic_rules` ya tiene `metric_type_id` pero le falta `created_at`; sus 12 `heuristic_rules.name` son un tercer set de nombres en inglés, distinto tanto del original del repo como del nuevo español (ej. `mass_file_modification`, no `mass_file_activity`). La v2 solo hace `UPDATE` sobre filas existentes -- nunca `INSERT`/`DELETE` -- así que no cambia ningún `id` (protege las referencias reales de `alert_rule.rule_id`) y no toca `weight`/`threshold`/`window_seconds`/`is_active` (los valores que el usuario ya haya ajustado a mano quedan intactos, a diferencia de la v1 que los sobrescribía con `ON CONFLICT ... DO UPDATE`). Los 12 `UPDATE` de `metric_types` de paso corrigen el texto corrupto de `description`, reemplazándolo por el mismo texto limpio que usa `schema.sql` para instalaciones nuevas. Al final rellena `heuristic_rules.metric_type_id` solo donde esté en `NULL` (nunca pisa un valor ya cargado).

**Verificado (2026-08-16):**
- Instalación limpia: `pgserver` + `schema.sql` (con los nombres nuevos) + `uvicorn` real -- `GET /api/rules` devuelve las 12 reglas con los 12 nombres en español exactos (comparación de conjuntos, sin diferencias); `PATCH /rules/{id}` sobre una regla normal funciona; sobre `acceso_honeyfile` rechaza cambio de peso (422) con el mismo mensaje de siempre; sobre `correlacion_multiples_indicadores` rechaza cambio de `threshold` (422).
- Migración contra una base que **simula la base real del usuario** (nombres en inglés tal como los pegó, sin `created_at`, con una fila real en `alert_rule` apuntando a `heuristic_rules.id`): tras aplicar la migración, los 12 nombres quedan en español, `created_at` existe, `metric_types.description` queda limpio, y el `id` al que apunta `alert_rule.rule_id` **no cambió** (se comprobó explícitamente antes/después). Los valores de `weight`/`threshold`/`window_seconds`/`is_active` de la regla editada tampoco cambiaron. Se corrió la migración una segunda vez sobre la misma base -- mismo resultado, sin duplicar filas ni errores (idempotente).
- `npm run build` (`tsc -b && vite build`) sin errores tras el cambio en `RuleCard.tsx`.

**Pendiente para el usuario:** correr `database/migration_2026-08-16_reglas_heuristicas.sql` contra su base real (`psql -U <usuario> -d alfa_sentinel -f migration_2026-08-16_reglas_heuristicas.sql`, o pegarlo en pgAdmin). Se recomienda un `pg_dump` antes por costumbre, aunque el script no borra nada.

---

## Auditoría: eliminar catálogos hardcodeados que duplican tablas de PostgreSQL (2026-08-16)

**Qué se pidió:** especificación de 25 secciones ("ALFA_SENTINEL — ELIMINAR DATOS DUPLICADOS HARDCODEADOS Y USAR LA BD COMO FUENTE DE VERDAD") pidiendo revisar todo el proyecto en busca de diccionarios/listas/constantes que dupliquen catálogos que ya existen en PostgreSQL (`heuristic_rules`, `metric_types`, `event_types`, `severity_levels`, `roles`) y eliminarlos, sin crear tablas ni columnas nuevas, y sin mover lógica de negocio legítima a la base. Se hizo una auditoría completa primero (con un subagente de investigación, sin tocar código) y se presentó el hallazgo antes de cambiar nada, tal como pidió el usuario.

**Decisiones confirmadas por el usuario antes de tocar código:**
- `heuristic_rules.name` se muestra tal cual en la interfaz (sin diccionario de traducción, sin reformatear guiones bajos ni agregar prefijo "HR-XX").
- `STRONG_RULE_NAMES`/`STRONG_FILE_ACTIVITY_RULES`/`FIXED_SCORING_RULE_NAMES` se dejan como código: son lógica de negocio (qué reglas cuentan como "fuertes" para incidentes/aislamiento, qué reglas tienen puntuación fija), no un catálogo de la BD, y no hay columna para representarlos sin agregar una (que el usuario pidió explícitamente no hacer).

**Eliminado (server/main.py):**
- `EVENT_TYPE_LABELS_ES` y sus 2 copias idénticas `EVENT_LABELS` (una de ellas ya estaba desincronizada de `event_types.description`: decía "renombrado / movido" contra "renombrado o movido" en la BD). Reemplazado por `event_types.description` leído en cada consulta -- ya sea agregando la columna al `SELECT`/`JOIN` existente, o vía el helper nuevo `_event_type_labels(cursor)` (consulta `SELECT name, description FROM event_types`, 4 filas, costo despreciable) en los ~20 lugares que lo usaban (`/eventos`, `/eventos/{id}`, `/api/eventos/{id}/drawer`, `/api/eventos/live`, `/eventos/export.csv`, el feed de "actividad reciente" del dashboard, `GET /api/rules`).
- `ALERT_RULE_LABELS_ES` (diccionario `heuristic_rules.name -> "HR-XX · Label"`, ~25 usos). Reemplazado por `heuristic_rules.name` directo en todos los lugares -- incluye `GET /api/rules`, `/api/incidentes`, `/api/alertas`, reportes PDF/XLSX, los selectores de filtro de Alertas/Incidentes (que antes ofrecían las 12 reglas hardcodeadas del diccionario; ahora se arman con `SELECT name FROM heuristic_rules`, así que si el día de mañana se agrega una regla 13 en la BD, aparece sola en los filtros sin tocar código).
- `MANUAL_ALERT_RISK_SCORE_BY_SEVERITY` (constante con el punto medio de cada banda de severidad, usada al convertir un evento en alerta manual). Reemplazado por `(min_score + max_score) / 2` calculado en el momento desde `severity_levels`, sin la constante paralela que podía desincronizarse si alguien editaba los rangos.
- `STATUS_LABEL` redefinido localmente en `frontend/src/components/AlertsFilters.tsx` (código muerto: duplicaba, dentro del mismo frontend, el que ya existe en `frontend/src/lib/alertStatus.ts` sin siquiera importarlo). Se importa el real y se borra la copia.

**Roles -- selector real + validación de verdad (el hallazgo de mayor riesgo):** no existía `GET /api/roles`, y tanto `POST /users` como `PATCH /users/{id}` aceptaban cualquier string en el campo `role` y, si no coincidía con ninguna fila de `roles`, **creaban una fila nueva silenciosamente** (`INSERT INTO roles ...` con la descripción `"Rol '<lo que sea>'"`). Cualquier typo en el `<input type="text">` de `UserFormModal.tsx` generaba un rol basura real en la base. Se corrigió:
- Nuevo `GET /api/roles` (lee `roles` tal cual).
- `POST /users` y `PATCH /users/{id}` ahora **rechazan** (422) un rol que no exista en la tabla, en vez de crearlo.
- `UserFormModal.tsx`: el campo "Rol" pasó de `<input type="text">` (con un default hardcodeado `"admin"`) a un `<select>` poblado con `GET /api/roles`, con manejo de carga/error propio.

**Bug preexistente encontrado durante la verificación (no relacionado con la auditoría, pero corregido de paso):** `GET /eventos/export.csv` nunca funcionaba -- la ruta `@app.get("/eventos/{event_id}")`, registrada antes en el archivo, interceptaba cualquier request a `/eventos/algo` (FastAPI/Starlette resuelve por orden de declaración, y un parámetro de ruta sin converter explícito matchea cualquier string a nivel de ruteo; la validación a `int` recién falla después, en vez de probar la siguiente ruta). Fix de una palabra: `@app.get("/eventos/{event_id:int}")` -- con el converter explícito, Starlette no matchea esa ruta para `export.csv` y prueba la siguiente. Verificado que ahora el CSV se descarga bien y que `/eventos/{id}` real sigue funcionando igual que antes. No se auditaron sistemáticamente el resto de las rutas del archivo por el mismo patrón -- puede haber más casos similares sin descubrir.

**Verificado (2026-08-16):** `python3 -m py_compile server/main.py` limpio. `npm run build` (`tsc -b && vite build`) limpio. Corrida real contra `pgserver` + `uvicorn`: `GET /api/roles` devuelve el catálogo real; `GET /api/rules` devuelve `label` = `name` crudo (sin "HR-"), `is_deferred`/`has_fixed_scoring` siguen correctos; `POST /users` con un rol inexistente rechaza con 422 y **no** crea la fila (confirmado con un `GET /api/roles` posterior); `POST /users` con un rol real funciona; `PATCH /rules/{id}` sobre honeyfile sigue rechazando cambio de peso; `GET /eventos` (Jinja2) muestra el label traducido desde la BD; `GET /eventos/export.csv` funciona; `GET /incidentes` y `GET /api/incidentes` cargan bien con el selector de reglas armado desde la BD.

---
