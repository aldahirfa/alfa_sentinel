# Laboratorio de pruebas -- motor heurístico y atribución de procesos

Este directorio prueba, con procesos reales de laboratorio (nunca ransomware real, nunca datos inventados), la atribución de procesos y las reglas heurísticas HR-05, HR-06 y HR-11 implementadas el 2026-08-16 (ver `PENDIENTES.md`, "Atribución de procesos y completado del motor heurístico"), además de una regresión de las reglas de archivos preexistentes y una prueba end-to-end de la configuración por endpoint.

No usa `pytest` (no es una dependencia del proyecto). Cada `test_*.py` es un script standalone con sus propios `assert`/`check()` y `sys.exit(0/1)`, el mismo estilo que ya usaba `agent/test_mass_activity.py`.

## Cómo correr las pruebas

Todas las pruebas de este directorio necesitan que `agent/` esté en el `PYTHONPATH` (los archivos ya lo resuelven solos con `sys.path.insert`, no hace falta configurar nada a mano) y las dependencias de `agent/requirements.txt` instaladas (`httpx`, `psutil`, `watchdog`). `test_endpoint_config_and_e2e.py` además necesita las de `server/requirements.txt` más `pgserver` (Postgres embebido efímero -- no toca tu base real).

Correr todo:

```
python3 tests/heuristic/run_all.py
```

Correr un archivo puntual:

```
python3 tests/heuristic/test_attribution.py
```

### Sobre `.venv`

El agente se desarrolla con un `.venv` local (`agent/.venv`, `server/.venv`) creado en Windows -- no es utilizable directamente en un sandbox Linux (no tiene un intérprete de Linux adentro). Estas pruebas se corrieron con un `python3` que ya tenía instaladas las dependencias necesarias (`psutil`, `watchdog`, `httpx`, `pgserver`, `psycopg`) sin modificar el entorno global de forma permanente ni instalar nada nuevo. Si corrés esto en tu propio `.venv` de Windows, activalo primero (`agent\.venv\Scripts\activate`) y instalá `pip install -r agent/requirements.txt -r server/requirements.txt pgserver` antes de ejecutar `run_all.py`.

## Qué prueba cada archivo

### `test_attribution.py` -- Pruebas A-D de atribución de procesos

Usa procesos de laboratorio reales (`lab_processes.py`, `lab_scripts/`) sincronizados con archivos `.ready`/`.go` (para no depender de `sleep()` adivinados).

| Prueba | Qué provoca | Qué se espera |
|---|---|---|
| A | Un proceso abre y mantiene abierto un archivo | `process_id`/`process_name` reales del proceso, más `username` |
| B | Un mismo proceso hace 4 operaciones secuenciales | Las 4 quedan atribuidas al mismo PID |
| C | Un proceso abre, escribe, cierra y TERMINA antes de consultar | `process_id`/`process_name` = `None` -- válido, no es un error |
| D | Dos procesos distintos, simultáneos | Cada archivo atribuido a su propio PID, sin mezclarse |

### `test_hr05_proceso_sospechoso.py` -- HR-05 con atribución real

Copia el intérprete de Python real a una carpeta temporal (`/tmp/...`) y lo ejecuta desde ahí -- `psutil.Process.exe()` resuelve `/proc/[pid]/exe` (el inodo real), así que la "ruta atípica" es genuina, no simulada. Compara ese proceso relocalizado contra el mismo intérprete corriendo desde su ruta estándar (`/usr/bin/python3.10`), y confirma que `process_info=None` nunca se trata como sospechoso.

### `test_hr06_cpu_elevado.py` -- HR-06 con un proceso real

`lab_scripts/cpu_burner.py` ocupa un núcleo al ~100% de verdad. Prueba positiva: CPU sostenida por encima del umbral durante toda la ventana -> dispara. Prueba negativa: el proceso termina antes de completar la ventana -> no dispara. Usa `agent/cpu_monitor.py::CpuMonitor` real, no una reimplementación -- solo con `threshold`/`window_seconds`/`SAMPLE_INTERVAL_SECONDS` de prueba (más cortos que los de producción, para que la prueba tarde segundos y no minutos).

**Nota de calibración encontrada durante esta tarea:** la primerísima lectura de `psutil.Process.cpu_percent()` para un proceso siempre devuelve `0.0` (es como funciona psutil, no es un bug). Con una ventana de prueba muy ajustada respecto al intervalo de muestreo, esa lectura inicial en `0.0` puede alcanzar a impedir que se cumpla `covers_window` antes de que el proceso de prueba termine. La prueba usa una ventana de 3s con muestreo cada 0.5s para tener margen real una vez que esa muestra inicial se poda -- no es una limitación de `CpuMonitor` en producción (ahí la ventana por defecto es de 10s), es un ajuste de la prueba en sí.

### `test_hr11_actividad_repetitiva.py` -- HR-11 con procesos reales

Positiva: un único proceso de laboratorio hace 4 operaciones (el umbral de prueba) -> dispara en la última. Negativa: dos procesos reales reparten 6 operaciones (3 cada uno, por debajo del umbral individual) -> ninguno dispara, aunque el total del "endpoint" sí llegaría al umbral -- confirma que HR-11 agrupa por PID, no por endpoint (a diferencia de HR-01/HR-04).

### `test_fanotify_parsing_synthetic.py` -- parseo de eventos fanotify

fanotify_init() no se puede probar de punta a punta en este entorno (ver limitaciones abajo), así que esta prueba fabrica el mismo layout binario que documenta `<linux/fanotify.h>` (`struct fanotify_event_metadata`, 24 bytes) apuntando a un `fd` real que abre la propia prueba, para confirmar que `FanotifyWatcher._handle_buffer()` parsea correctamente un evento, varios eventos concatenados en un mismo buffer, y que la caché respeta su TTL. También confirma que `start()` sin privilegios devuelve `False` de forma limpia, sin lanzar una excepción.

### `test_hr05_hr11_unit_synthetic.py` / `test_hr06_unit_synthetic.py`

Complemento rápido y determinístico de las pruebas con procesos reales de arriba -- `process_info`/muestras de CPU armadas a mano en vez de procesos de laboratorio, para poder correr en cada cambio de `heuristic_engine.py`/`cpu_monitor.py` sin esperar a que arranquen subprocesos.

### `test_file_rules_regression.py` -- HR-01, 02, 03, 04, 07, 08, 09, 10

Regresión de las reglas que ya existían antes de esta tarea, para confirmar que la nueva atribución de procesos no las rompió. Lee `threshold`/`window_seconds` reales de `agent/heuristic_engine.py::DEFAULT_RULES` en vez de duplicar los números a mano en el archivo de prueba -- si algún día cambian los valores por defecto, la prueba se ajusta sola.

### `test_endpoint_config_and_e2e.py` -- configuración por endpoint + traza completa

Levanta un Postgres embebido efímero (`pgserver`, no toca tu base real) + `uvicorn` real, y prueba los 5 escenarios de configuración por endpoint más una traza de integración completa:

| Endpoint | Qué prueba |
|---|---|
| A | Sin override -- usa la configuración global tal cual |
| B | Override solo de `threshold` -- `weight` sigue heredando el global |
| C | Override solo de `weight` -- una alerta real usa el peso EFECTIVO de ese endpoint, no el global |
| D | Override de `window_seconds`, reflejado en `GET /agent/rule-policy` |
| E | Regla desactivada por override -- desaparece de la política de ESE endpoint, otro endpoint sin override la sigue viendo activa; tras `DELETE` del override, vuelve a heredar el global |

Traza completa: evento -> `matched_rules` -> `POST /agent/alerts` -> resolución de configuración efectiva -> `risk_score` -> severidad -> alerta -> incidente automático -> condición de aislamiento (`host_isolations`, siempre `RECOMMENDED`, nunca ejecutado de verdad) -- verificado tanto en la respuesta HTTP como directo contra las tablas de Postgres.

## Limitaciones de este entorno (honestas, no simuladas)

**fanotify (Linux) no se pudo probar de punta a punta.** `fanotify_init()` exige el privilegio `CAP_SYS_ADMIN` -- confirmado en este sandbox (usuario sin `sudo`, sin acceso a `root`, y ni siquiera un *user namespace* con `--map-root-user` lo habilita, porque fanotify es un recurso del namespace de usuario INICIAL del kernel, no delegable a namespaces sin privilegios). El código de `agent/adapters/linux_fanotify.py` es real -- se probó exhaustivamente su lógica de parseo (`test_fanotify_parsing_synthetic.py`) y su degradación limpia al fallback cuando no hay privilegios (confirmada en vivo, no simulada) -- pero la ruta "fanotify entrega un evento real del kernel" en sí no se ejecutó ni una vez. Para probarla de verdad hace falta correr el agente como root (o con `CAP_SYS_ADMIN` otorgado explícitamente) en una máquina Linux real.

**ETW (Windows) no se pudo probar en absoluto.** Este entorno de desarrollo es un sandbox Linux -- no hay ninguna máquina Windows disponible para ejecutar `agent/adapters/windows_etw.py` ni una sola vez. Ese módulo está escrito siguiendo la API pública documentada de `pywintrace`, con manejo defensivo de nombres de clave desconocidos (ver el aviso al inicio del archivo), pero **no está verificado**. Antes de confiar en él en producción hace falta correrlo en Windows real, como Administrador (ETW sobre un proveedor de kernel exige `SeSystemProfilePrivilege`), y confirmar los nombres de clave reales que devuelve la versión de `pywintrace` instalada.

**En ambos casos, el fallback (`psutil.open_files()`) sí está probado de punta a punta** con procesos reales (`test_attribution.py`, `test_hr05_proceso_sospechoso.py`, `test_hr11_actividad_repetitiva.py`) -- es el mecanismo que de hecho se ejerce hoy en este entorno, y es el mismo que ya venía funcionando antes de esta tarea.

## Qué NO hace este laboratorio

No instala el agente como servicio de Windows ni como unidad de `systemd`, no prueba despliegue en múltiples endpoints físicos, no usa ransomware real ni simula datos que el sistema operativo no entregó de verdad. Esas etapas quedan fuera de alcance a propósito (ver la especificación "ATRIBUCIÓN DE PROCESOS Y COMPLETADO DEL MOTOR HEURÍSTICO", sección 26).
