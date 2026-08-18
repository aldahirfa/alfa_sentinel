# Pruebas -- Honeyfiles: despliegue, rutas, integridad, reconciliación

`test_honeyfiles_e2e.py` prueba de punta a punta, con código REAL (nunca
reimplementado ni mockeado) y sin ransomware ni datos simulados, los 10
escenarios pedidos en la especificación "Honeyfiles: despliegue
automático, rutas, integridad, reconciliación y ejecución en tiempo
real" (2026-08-17, ver `PENDIENTES.md`).

`test_h_honeyfiles.py`, `test_g_monitorizacion_global.py` y
`test_critico_combinado.py` prueban, con el mismo criterio (código
real, `watchdog.Observer` real, `pgserver` + `uvicorn` reales), los
escenarios H1-H8/G1-G6/prueba crítica combinada de la especificación
"Honeyfiles + monitorización completa del endpoint + detección por
comportamiento anómalo + correlación de indicadores" (2026-08-17, ver
`PENDIENTES.md`) -- ver tabla más abajo.

No usa `pytest`. Mismo estilo que `tests/heuristic/`: cada script es
standalone con `check()`/`sys.exit(0/1)`.

## Cómo correr

```
python3 tests/honeyfiles/test_honeyfiles_e2e.py
python3 tests/honeyfiles/test_h_honeyfiles.py
python3 tests/honeyfiles/test_g_monitorizacion_global.py
python3 tests/honeyfiles/test_critico_combinado.py
```

Necesita las dependencias de `agent/requirements.txt` + `server/requirements.txt` + `pgserver` (Postgres embebido efímero, no toca la base real).

## Qué prueba (sección 33 de la especificación)

| # | Escenario | Qué confirma |
|---|---|---|
| 1 | Primer instalación | `auto_deploy=TRUE` crea el honeyfile solo, sin intervención manual |
| 2 | Reinicio no duplica | Una segunda sincronización sobre un honeyfile intacto no crea una segunda fila ni reescribe el archivo (mismo `id`, mismo hash) |
| 3 | Asignación nueva sin reiniciar | Se ejercita `HoneyfileSyncThread._sync_once()` real (el mismo código que arranca `agent/main.py`) para confirmar que una asignación hecha mientras el agente sigue corriendo se materializa y se suma a `HoneyfileMonitor.known_paths` en caliente |
| 4 | Borrado + reconciliación | El archivo desaparece de disco -> se recrea (caso B), conservando el mismo `id` en `honeyfiles` (UPSERT, no INSERT) |
| 5 | Modificación + no restauración | El hash real ya no coincide -> se registra el hash nuevo (`MODIFIED`), el contenido alterado NUNCA se restaura, la asignación sigue `CREATED` |
| 6 | `auto_deploy=TRUE` | Alcanza a un endpoint sin asignación manual previa |
| 7 | `auto_deploy=FALSE` | Solo llega al endpoint asignado a mano, nunca a otro |
| 8 | Incompatibilidad de SO (ambos sentidos) | Una plantilla `LINUX` no se asigna a un agente Windows, y viceversa; confirmación positiva de que sí cruza cuando el SO coincide |
| 9 | Dos endpoints, asignaciones propias | Cada agente ve únicamente lo que se le asignó a él, nunca lo del otro |
| 10 | Fallo real de creación + reintento | `PermissionError` real (carpeta sin permiso de escritura, no simulado) -> `FAILED`; una vez resuelto el problema, la siguiente sincronización reintenta sola y termina en `CREATED` |

Además valida, como precondición, que `database/schema.sql` ya incluye
`honeyfiles.template_id` (sección 20B) -- la migración aparte
(`database/migration_2026-08-17_honeyfiles_template_id.sql`) es para
aplicar a mano sobre una base YA existente, nunca se corre contra la
base real del usuario desde este código (ver PENDIENTES.md).

## Metodología

- Servidor: Postgres embebido efímero (`pgserver`) + `uvicorn` real en subproceso, igual que `tests/heuristic/test_endpoint_config_and_e2e.py`.
- Agente: se llama directo a `agent/honeyfile_deployer.py::apply_honeyfile_policy()`, `agent/honeyfile_monitor.py::HoneyfileMonitor` y `agent/honeyfile_sync.py::HoneyfileSyncThread` -- el mismo código que corre `agent/main.py`, no una reimplementación de prueba.
- Filesystem: `agent/paths.py::_DEV_HONEYFILES_DIR` se monkeypatchea a una carpeta temporal propia de la corrida (nunca `agent/honeyfiles/` del repo), para no ensuciar el repositorio ni pisar honeyfiles de otra ejecución.

## Qué prueba H1-H8 (`test_h_honeyfiles.py`, sección 37, 15/15 OK)

| # | Escenario | Qué confirma |
|---|---|---|
| H1 | El agente CREA un honeyfile | NO dispara 'Acceso Honeyfile' (HR-03) -- es actividad interna |
| H2 | El agente RECREA un honeyfile borrado (reconciliación) | Tampoco dispara HR-03 |
| H3 | Un proceso EXTERNO modifica un honeyfile | SÍ dispara HR-03, `risk_score=100`/`CRÍTICO` |
| H4 | Un proceso EXTERNO elimina un honeyfile | SÍ dispara HR-03 |
| H5 | Un proceso EXTERNO renombra un honeyfile | SÍ dispara HR-03 (evalúa el nombre VIEJO contra `known_paths`, ver bug corregido en `on_moved()`, `PENDIENTES.md`) |
| H6 | Crear una subcarpeta dentro de `ALFA_ARCHIVOS` | NO dispara HR-03 |
| H7 | Crear un archivo AJENO (no honeyfile) dentro de `ALFA_ARCHIVOS` | Se registra el evento, NO se etiqueta como honeyfile |
| H8 | Modificar ese archivo ajeno | Sigue sin disparar HR-03 |

## Qué prueba G1-G6 (`test_g_monitorizacion_global.py`, sección 38, 11/11 OK)

| # | Escenario | Qué confirma |
|---|---|---|
| G1 | Crear/modificar un archivo en Videos | Se registran eventos reales fuera de `ALFA_ARCHIVOS` |
| G2 | Modificar muchos archivos en Videos | Dispara HR-01 (Modificación Masiva) |
| G3 | Escritura intensiva en Documents | Dispara HR-04 (Escritura Intensiva) |
| G4 | Eliminación masiva en Pictures | Dispara HR-09 (Eliminación Anómala) |
| G5 | Un mismo proceso real, varias operaciones en Music | Dispara HR-11 (Actividad Repetitiva), agrupado por PID real |
| G6 | Las reglas de G1-G5 coinciden en el mismo episodio | HR-12 (Correlación) participa con una bonificación real > 0 |

## Qué prueba la crítica combinada (`test_critico_combinado.py`, sección 39, 20/20 OK)

Un mismo atacante: (1) modifica Videos, (2) escribe intensivamente en
Documents, (3) elimina en Pictures, (4) repite actividad con un
proceso real en Music, y (5) finalmente toca un honeyfile real.
Confirma contra la base real: evidencia acumulada de comportamiento
anómalo en el MISMO episodio ANTES del honeyfile (score calculado, no
100); al tocar el honeyfile, HR-03 se suma al MISMO episodio (mismo
`alert_id`) y el score sube a exactamente 100/CRÍTICO; la evidencia
previa (HR-01/04/09/11 + HR-12) se conserva sin duplicarse; se crea un
incidente y una recomendación de aislamiento (`RECOMMENDED`, nunca
ejecutada).

## Notas de metodología específicas de H/G/crítica

- **Deduplicación de episodios:** el servidor agrupa ráfagas del mismo
  agente en una sola alerta mientras siga `NEW`/`ACKNOWLEDGED` dentro
  de `EPISODE_WINDOW_SECONDS` (120s, `server/main.py::report_alert`) y
  no duplica una fila de `alert_rule` para una regla ya vinculada a ESE
  episodio. Por eso estas pruebas comparan conteos ANTES/DESPUÉS de
  cada acción (`honeyfile_hit_count()`, `alert_rule_names_ever()`) en
  vez de mirar solo "la alerta más reciente", y cierran el episodio a
  mano (`close_current_episode()`) entre escenarios de H que sí
  necesitan un episodio fresco propio.
- **Atribución de proceso bajo carga (G5 y el paso 4 de la crítica):**
  la atribución real (`agent/adapters/`, fallback `psutil.open_files()`
  en este sandbox sin `CAP_SYS_ADMIN`) exige que el archivo siga
  abierto en el instante en que el hilo de watchdog la consulta. Con el
  proceso de laboratorio (`tests/heuristic/lab_processes.py::spawn_multi_writer`)
  liberando cada archivo apenas se le da la señal, el hilo de watchdog
  -- ocupado también procesando el ruido propio de los marcadores
  `.ready`/`.go` del handshake -- puede llegar tarde. Estas pruebas no
  sueltan `signal_go()` hasta confirmar que el evento YA llegó
  atribuido al PID real (`event_attributed()`), y NO llaman a
  `cleanup_markers()` -- el proceso de laboratorio limpia sus propios
  marcadores, y borrarlos desde el padre puede ganarle la carrera al
  hijo y hacerlo esperar su timeout completo (mismo patrón, sin este
  problema, en `tests/heuristic/test_attribution.py`).
- **Overrides de umbral por endpoint:** G y la crítica bajan el
  `threshold` de HR-01/04/09/11 a 5 (vía `PATCH /api/agents/{id}/rules/{id}`,
  mecanismo ya existente, no inventado para la prueba) para correr en
  segundos en vez de minutos -- y pasan la política EFECTIVA real
  (`GET /agent/rule-policy`) a `start_file_monitor(rule_policy=...)`,
  nunca `None` (que haría caer al analizador a los umbrales por
  defecto, ignorando el override).

## Nota sobre el entorno de pruebas

El sandbox donde se corrieron estas pruebas define variables de entorno de proxy (`ALL_PROXY`, etc.) para otras herramientas del entorno. `agent/client.py` usa `httpx` sin `trust_env=False` a propósito (así debe comportarse en un despliegue real). El script de prueba limpia esas variables SOLO en su propio proceso antes de llamar al agente -- no es un cambio al código del agente, es exclusivamente para que la prueba pueda correr en este sandbox.
