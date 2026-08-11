# Pendientes técnicos

Registro de trabajo identificado pero diferido a propósito, para no perderlo. Cada entrada explica el problema real, por qué no se resolvió todavía, y el camino propuesto para cuando se retome.

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

**Estado:** resuelto (2026-08-11). Tabla puente `alert_events` (alert_id, event_id) -- una alerta nace de varios eventos (todos los archivos de la ventana), así que un FK simple en `alerts` no alcanzaba.

**Qué cambió:** `agent/heuristic_engine.py` (`FileActivityAnalyzer` guarda el `event_id` que devuelve el servidor junto a cada evento de la ventana), `agent/file_monitor.py` (manda `send_event` antes que nada para tener el ID, lo pasa al analizador, y lo incluye en `send_alert` como `event_ids`), `server/main.py` (`AlertCreate.event_ids`, `report_alert` inserta en `alert_events` validando que los eventos sean del mismo agente), `database/schema_updates.sql` sección 5 (tabla + índices -- **falta correrlo contra la base real**, todavía no se aplicó). `deteccion_detail.html` ahora muestra "Eventos relacionados" y `evento_detail.html` muestra "Detección relacionada", con datos reales vía join.

**Importante:** esto solo empieza a llenarse con eventos NUEVOS a partir de que se corra `schema_updates.sql` y se reinicie el agente con el código actualizado -- no relaciona retroactivamente alertas/eventos que ya existían en la base antes de este cambio.

---

## Incidente ↔ detecciones que agrupa

**Estado:** resuelto (2026-08-11). Igual razonamiento que `alert_events`: `incidents.alert_id` (NOT NULL) obligaba a que un incidente fuera 1 a 1 con la detección que lo originó -- no alcanzaba para armar un caso con varias detecciones relacionadas. Tabla puente `incident_alerts` (incident_id, alert_id). `alert_id` se conserva como "la detección que lo disparó"; `incident_alerts` es la lista completa (incluida esa primera).

**Qué cambió:** `database/schema_updates.sql` secciones 7-9 (`incident_alerts`, columnas `assigned_to`/`assigned_at`/`updated_at` en `incidents`, `incident_notes` -- **falta correrlas contra la base real**). `server/main.py`: `POST /incidents` ahora también inserta en `incident_alerts`; nuevos endpoints `POST /incidents/{id}/alerts` (vincular detección adicional), `PATCH /incidents/{id}/status`, `PATCH /incidents/{id}/classification`, `PATCH /incidents/{id}/assign`, `PATCH /incidents/{id}/description`, `POST /incidents/{id}/notes`. `incidentes.html`/`incidente_detail.html` reconstruidos con datos reales (severidad y cantidad de detecciones se derivan de `incident_alerts`, no son columnas propias).

**Lo que se dejó afuera a propósito (no fabricado):** un incidente sigue ligado a un único endpoint (`incidents.agent_id`) -- no hay forma real de representar "varios endpoints afectados" sin otro cambio de schema. La sección "Respuesta asociada" del detalle muestra una nota honesta en vez de datos de `host_isolations`, porque ningún endpoint del servidor escribe ahí todavía (`/respuesta` sigue siendo placeholder).

## Historial de cambios de estado de un incidente

**Estado:** no implementado. `incidents.status` guarda el valor actual nada más -- no hay registro de cuándo pasó de "Abierto" a "En investigación" o a "Contenido". La "Línea temporal" del incidente por eso solo muestra los hechos con fecha real disponible (detecciones generadas, apertura, asignación, cierre), no cada transición de estado intermedia.

**Camino propuesto:** una tabla `incident_status_history` (incident_id, status, changed_by, changed_at), poblada desde `PATCH /incidents/{id}/status` cada vez que cambia. Chico y mecánico, pero no se hizo ahora para no seguir agrandando el alcance de esta pasada.
