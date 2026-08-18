import os
import threading

from . import common
from .linux_fanotify import FanotifyWatcher

# Inicialización perezosa y global al módulo -- el primer evento de
# archivo que llega arranca fanotify UNA vez (marca todo el punto de
# montaje que contiene ese archivo, no solo esa carpeta puntual --
# FAN_MARK_MOUNT cubre también honeyfiles en otras rutas del mismo
# disco). Si no está disponible (sin privilegios), 'available' queda
# en False para siempre y cada evento futuro cae directo al fallback
# sin volver a intentar ni repetir la advertencia en cada evento.
_watcher = None
_watcher_lock = threading.Lock()


def _get_watcher(file_path):
    global _watcher
    with _watcher_lock:
        if _watcher is None:
            _watcher = FanotifyWatcher()
            _watcher.start(os.path.dirname(os.path.abspath(file_path)) or "/")
    return _watcher


def get_process_for_file_event(file_path, event_type):
    """Adaptador Linux -- orden de atribución (sección 8 de la
    especificación de atribución de procesos, 2026-08-16):
    1) fanotify (mecanismo nativo del SO, linux_fanotify.py) -- si
       está disponible (requiere CAP_SYS_ADMIN, ver ese módulo) y
       tiene un dato fresco para esta ruta puntual;
    2) si no, psutil.open_files() (adapters/common.py, fallback
       preexistente, se conserva sin cambios de comportamiento);
    3) si tampoco, None -- nunca se inventa un proceso ni se asume
       'desconocido = sospechoso' (sección 8/9 de la especificación).

    Auditd queda deliberadamente fuera como dependencia obligatoria
    (sección 5): requeriría que un administrador lo instale y
    configure reglas de auditoría por separado -- fanotify, en
    cambio, es una API del propio kernel, sin instalación externa."""

    watcher = _get_watcher(file_path)

    if watcher.available:
        pid = watcher.lookup(file_path)
        if pid is not None:
            enriched = common.enrich_pid(pid)
            if enriched is not None:
                return enriched
            # fanotify vio un PID válido, pero el proceso ya no existe
            # para cuando se consulta psutil (vida muy corta) -- cae
            # al fallback en vez de reportar un proceso fantasma.

    return common.find_process_for_open_file(file_path)
