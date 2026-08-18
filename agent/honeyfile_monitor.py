import os
import threading
import time


# Cuánto tiempo queda excluida una ruta después de que el AGENTE MISMO
# (no un proceso externo) la escribe -- sección 22 de la especificación
# de monitorización completa: "no activar HR-03 por sus propios
# eventos... NO utilizar sleep fijo como única solución". Esto no es un
# sleep que bloquea al hilo que escribe: es una marca con expiración
# que el hilo de watchdog consulta cuando le llega el evento. El valor
# es un margen de seguridad para la latencia real (típicamente
# sub-segundo) entre que se cierra el archivo y watchdog entrega el
# evento -- no "cuánto tarda la operación", que ya terminó para cuando
# se marca.
INTERNAL_OPERATION_GRACE_SECONDS = 5.0


class HoneyfileMonitor:
    """Sabe dos cosas, y solo dos (secciones 12/23/24 de la
    especificación de honeyfiles / monitorización completa):

    1. is_honeyfile(path) -- ¿esta ruta es una de las instancias REALES
       que el servidor confirmó ('honeyfiles', nunca 'cualquier archivo
       dentro de la carpeta ALFA_ARCHIVOS'; sección 23: "Crear
       Documents\\ALFA_ARCHIVOS\\otro.txt -> NO HR-03 automáticamente")?
    2. is_internal_operation(path) -- ¿el AGENTE MISMO la tocó hace un
       instante (creación/reconciliación), y por lo tanto un evento de
       watchdog que llegue ahora para esa ruta puntual no debe activar
       HR-03 (sección 22/34)?

    Ninguna lógica de detección de reglas vive acá -- eso es
    heuristic_engine.py. Esto es solo la fuente de verdad de "qué es
    honeyfile" y "qué acabo de escribir yo mismo"."""

    def __init__(self, known_paths=None):

        # Rutas reales de honeyfiles creados/reportados por este
        # agente (ver agent/honeyfile_deployer.py) -- pueden crecer en
        # caliente (agent/honeyfile_sync.py, sin reiniciar el agente).
        # Protegido con lock: el hilo de sincronización escribe,
        # watchdog lee en cada evento de archivo.
        self._lock = threading.Lock()
        self.known_paths = {
            os.path.abspath(p) for p in (known_paths or [])
        }

        # path absoluto -> timestamp (time.monotonic()) hasta el cual
        # un evento sobre esa ruta se considera actividad INTERNA del
        # agente, no una interacción externa real.
        self._internal_until = {}

    def add_known_path(self, file_path):
        """Suma una ruta nueva al conjunto vigilado sin reiniciar el
        agente -- lo llama agent/honeyfile_sync.py cada vez que
        detecta (por asignación nueva o por reconciliación) un
        honeyfile que todavía no estaba en 'known_paths'."""

        absolute_path = os.path.abspath(file_path)
        with self._lock:
            self.known_paths.add(absolute_path)

    def is_honeyfile(self, file_path):
        """Depende EXCLUSIVAMENTE de 'known_paths' -- la lista real de
        instancias que el servidor confirmó (tabla 'honeyfiles').

        Antes de esta tarea (2026-08-17, ver PENDIENTES.md,
        "Honeyfiles + monitorización completa del endpoint...") esto
        además hacía un fallback por prefijo de carpeta ("cualquier
        archivo dentro de la carpeta de honeyfiles es honeyfile"),
        heredado de cuando esa carpeta SOLO contenía honeyfiles reales.
        Ahora que ALFA_ARCHIVOS puede recibir archivos ajenos creados
        por un proceso externo (sección 24: "registrar file_created,
        NO etiquetarlo como Honeyfile"), ese fallback generaría falsos
        positivos de HR-03 -- se eliminó a propósito."""

        absolute_path = os.path.abspath(file_path)

        with self._lock:
            return absolute_path in self.known_paths

    def mark_internal_operation(self, file_path, grace_seconds=None):
        """Llamado por agent/honeyfile_deployer.py justo antes de
        escribir un honeyfile (creación o reconciliación). No bloquea
        al que escribe -- solo dice "un evento de watchdog sobre esta
        ruta, hasta dentro de 'grace_seconds', es mío, no de un proceso
        externo".

        'grace_seconds=None' (en vez de default=INTERNAL_OPERATION_GRACE_SECONDS
        directamente en la firma) a propósito: un default de parámetro
        se fija UNA sola vez, en el momento en que Python define la
        función -- si algo quisiera ajustar el margen en caliente (ej.
        una prueba) modificando el módulo, un default ya fijado nunca
        se enteraría. Leer el valor del módulo ACÁ ADENTRO sí lo
        respeta en cada llamada."""

        if grace_seconds is None:
            grace_seconds = INTERNAL_OPERATION_GRACE_SECONDS

        absolute_path = os.path.abspath(file_path)
        with self._lock:
            self._internal_until[absolute_path] = time.monotonic() + grace_seconds

    def is_internal_operation(self, file_path):
        """Consultado por file_monitor.py antes de activar HR-03. No
        elimina el evento de la telemetría (sección 34: "esos eventos
        pueden seguir registrándose") -- file_monitor.py sigue
        mandando el evento y evaluando las demás reglas igual; esto
        solo decide si CUENTA como interacción con un honeyfile para
        HR-03 puntualmente."""

        absolute_path = os.path.abspath(file_path)
        with self._lock:
            expires_at = self._internal_until.get(absolute_path)

        return expires_at is not None and time.monotonic() < expires_at
