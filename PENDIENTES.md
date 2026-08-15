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
