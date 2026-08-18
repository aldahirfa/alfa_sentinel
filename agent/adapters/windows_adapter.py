import threading

from . import common
from .windows_etw import EtwFileIoWatcher

# Inicialización perezosa y global al módulo -- el primer evento de
# archivo arranca la sesión ETW una sola vez. Si no está disponible
# (pywintrace no instalado, o sin privilegios de Administrador),
# 'available' queda en False para siempre y cada evento futuro cae
# directo al fallback sin reintentar. Ver aviso de "no verificado en
# este entorno" al inicio de windows_etw.py.
_watcher = None
_watcher_lock = threading.Lock()


def _get_watcher():
    global _watcher
    with _watcher_lock:
        if _watcher is None:
            _watcher = EtwFileIoWatcher()
            _watcher.start()
    return _watcher


def get_process_for_file_event(file_path, event_type):
    """Adaptador Windows -- orden de atribución (sección 8 de la
    especificación de atribución de procesos, 2026-08-16):
    1) ETW sobre 'Microsoft-Windows-Kernel-File' (mecanismo nativo del
       SO, windows_etw.py) -- si está disponible (requiere
       Administrador, ver ese módulo) y tiene un dato fresco para
       esta ruta puntual;
    2) si no, psutil.open_files() (adapters/common.py, fallback
       preexistente, se conserva sin cambios de comportamiento);
    3) si tampoco, None -- nunca se inventa un proceso.

    Sysmon queda deliberadamente fuera como dependencia obligatoria
    (sección 4): requeriría que un administrador lo instale y
    configure por separado -- ETW, en cambio, es una API del propio
    Windows, sin instalación externa (aunque sí exige privilegios de
    Administrador para consumir un proveedor de kernel)."""

    watcher = _get_watcher()

    if watcher.available:
        pid = watcher.lookup(file_path)
        if pid is not None:
            enriched = common.enrich_pid(pid)
            if enriched is not None:
                return enriched
            # ETW vio un PID válido, pero el proceso ya no existe para
            # cuando se consulta psutil (vida muy corta) -- cae al
            # fallback en vez de reportar un proceso fantasma.

    return common.find_process_for_open_file(file_path)
