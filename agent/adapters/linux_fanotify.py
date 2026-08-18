"""Mecanismo PRIMARIO de atribución de procesos en Linux (2026-08-16,
ver PENDIENTES.md, "Atribución de procesos y completado del motor
heurístico"): observa aperturas/escrituras de archivo a nivel de
sistema operativo con fanotify, en vez de recorrer todos los procesos
del sistema como hace el mecanismo anterior (adapters/common.py, que
se conserva como FALLBACK, sección 2/8 de la especificación -- no se
elimina).

Por qué fanotify y no auditd/Sysmon: fanotify es una API del propio
kernel de Linux (desde 2.6.37), sin necesidad de instalar ni
configurar ningún servicio externo aparte del agente -- auditd
requeriría que el administrador del sistema lo instale y configure
reglas de auditoría por separado, algo que la especificación prohíbe
como dependencia OBLIGATORIA (sección 5: "NO utilizar auditd como
dependencia obligatoria").

Requisito de privilegios, documentado sin rodeos: fanotify_init()
exige el privilegio CAP_SYS_ADMIN (en la práctica, casi siempre correr
como root) -- sección 6 de la especificación: "si ETW o fanotify
requieren permisos especiales, documentarlos claramente". Sin ese
privilegio, fanotify_init() devuelve EPERM y este módulo se desactiva
limpiamente -- FanotifyWatcher.start() devuelve False, el llamador
(linux_adapter.py) cae al fallback de psutil sin que el agente se
entere de que pasó nada raro. Confirmado en el entorno de desarrollo
actual (sandbox Linux sin privilegios elevados, usuario sin acceso a
sudo): fanotify_init() devuelve EPERM ahí -- NO se simula que funcione
cuando no funciona (sección 30 de la especificación)."""

import ctypes
import ctypes.util
import os
import struct
import threading
import time


# ------------------------------------------------------------
# Constantes fanotify (<linux/fanotify.h>) -- Python no las expone en
# el módulo 'os' (a diferencia de algunas constantes de inotify), así
# que se hardcodean acá. Son parte de la ABI pública y estable del
# kernel de Linux, no cambian entre versiones ni distros.
# ------------------------------------------------------------
FAN_CLASS_NOTIF = 0x00000000
FAN_OPEN = 0x00000020
FAN_MODIFY = 0x00000002
FAN_CLOSE_WRITE = 0x00000008
FAN_Q_OVERFLOW = 0x00004000
FAN_MARK_ADD = 0x00000001
FAN_MARK_MOUNT = 0x00000010
FAN_NOFD = -2

O_RDONLY = 0
O_LARGEFILE = 0o0100000
AT_FDCWD = -100

# Qué se observa: apertura, modificación y cierre-tras-escritura. NO
# se pide FAN_CREATE/FAN_DELETE/FAN_MOVE -- eso requeriría
# FAN_REPORT_FID (kernel 5.1+) y a su vez open_by_handle_at(), que
# pide CAP_DAC_READ_SEARCH ADEMÁS de CAP_SYS_ADMIN -- un requisito de
# privilegios todavía mayor que no se justifica acá: 'watchdog' (ver
# file_monitor.py) ya detecta el TIPO de evento (creado/modificado/
# eliminado/renombrado); fanotify solo se usa como canal lateral para
# responder "¿qué PID tocó esta ruta hace un instante?", y para eso
# alcanza con ver cuándo se abre/escribe/cierra el archivo.
WATCH_MASK = FAN_OPEN | FAN_MODIFY | FAN_CLOSE_WRITE

# struct fanotify_event_metadata:
#   __u32 event_len; __u8 vers; __u8 reserved; __u16 metadata_len;
#   __aligned_u64 mask; __s32 fd; __s32 pid;
# Formato fijo (24 bytes, sin padding) mientras no se use
# FAN_REPORT_FID -- ver nota arriba. '=' fuerza tamaños estándar sin
# padding de alineación (los campos ya están alineados naturalmente:
# 4+1+1+2+8+4+4 = 24, sin relleno).
_METADATA_FORMAT = "=IBBHQii"
_METADATA_SIZE = struct.calcsize(_METADATA_FORMAT)


class FanotifyWatcher:
    """Hilo en background (mismo patrón que agent/cpu_monitor.py --
    CpuMonitor) que mantiene una caché corta (ruta normalizada -> (pid,
    timestamp)) de qué proceso tocó qué archivo. agent/adapters/
    linux_adapter.py la consulta cuando watchdog reporta un evento de
    archivo -- no recorre procesos activamente en el momento del
    evento, a diferencia del mecanismo de respaldo."""

    # Cuánto se considera "fresco" un dato de la caché. Watchdog
    # reporta el evento casi de inmediato después de que el kernel
    # entrega el evento de fanotify (típicamente milisegundos), así
    # que una ventana corta alcanza sin arriesgar atribuir un archivo
    # a un proceso que ya no tiene nada que ver con el evento actual.
    CACHE_TTL_SECONDS = 5.0

    def __init__(self):
        libc_path = ctypes.util.find_library("c")
        self._libc = ctypes.CDLL(libc_path, use_errno=True)
        self._libc.fanotify_init.restype = ctypes.c_int
        self._libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self._libc.fanotify_mark.restype = ctypes.c_int
        self._libc.fanotify_mark.argtypes = [
            ctypes.c_int, ctypes.c_uint, ctypes.c_uint64, ctypes.c_int, ctypes.c_char_p,
        ]

        self._fd = None
        self._recent = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self.available = False

    def start(self, mount_path):
        """Intenta inicializar fanotify sobre el punto de montaje que
        contiene 'mount_path'. Devuelve True si arrancó, False si no
        está disponible (sin privilegios, o el kernel no lo soporta).
        NUNCA lanza una excepción hacia el llamador -- el llamador
        (linux_adapter.py) cae al fallback de psutil si esto devuelve
        False, sin que el arranque del agente se vea afectado."""

        fd = self._libc.fanotify_init(FAN_CLASS_NOTIF, O_RDONLY | O_LARGEFILE)

        if fd < 0:
            errno_val = ctypes.get_errno()
            print(
                f"⚠ Atribución de procesos (Linux): fanotify no disponible "
                f"({os.strerror(errno_val)}, errno={errno_val}). Requiere el privilegio "
                f"CAP_SYS_ADMIN (típicamente correr como root) -- en un entorno de "
                f"desarrollo sin privilegios elevados esto es esperable, no un error del "
                f"agente. Se usa el mecanismo de respaldo (psutil.open_files())."
            )
            return False

        mark_result = self._libc.fanotify_mark(
            fd,
            FAN_MARK_ADD | FAN_MARK_MOUNT,
            WATCH_MASK,
            AT_FDCWD,
            os.path.abspath(mount_path).encode(),
        )

        if mark_result < 0:
            errno_val = ctypes.get_errno()
            print(
                f"⚠ Atribución de procesos (Linux): fanotify_mark falló sobre "
                f"'{mount_path}' ({os.strerror(errno_val)}, errno={errno_val}). Se usa el "
                f"mecanismo de respaldo (psutil.open_files())."
            )
            os.close(fd)
            return False

        self._fd = fd
        self.available = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"Atribución de procesos (Linux): fanotify activo sobre el punto de montaje de '{mount_path}'.")
        return True

    def stop(self):
        self._stop_event.set()
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                raw = os.read(self._fd, 4096)
            except OSError:
                break
            if not raw:
                break
            self._handle_buffer(raw)

    def _handle_buffer(self, raw):
        """Separado de _run() a propósito -- así se puede probar el
        parseo de eventos con un buffer sintético en las pruebas
        (tests/heuristic/), sin necesitar privilegios reales para
        fabricar eventos de fanotify de verdad."""

        offset = 0
        while offset + _METADATA_SIZE <= len(raw):
            event_len, vers, reserved, metadata_len, mask, event_fd, pid = struct.unpack_from(
                _METADATA_FORMAT, raw, offset
            )
            offset += event_len if event_len >= _METADATA_SIZE else _METADATA_SIZE

            if mask & FAN_Q_OVERFLOW:
                # Se perdieron eventos por exceso de volumen -- no hay
                # nada que atribuir de esa ráfaga puntual. Se
                # documenta, no se inventa un dato para rellenar el
                # hueco.
                print("⚠ fanotify: se perdieron eventos por desborde de la cola (FAN_Q_OVERFLOW).")
                continue

            if event_fd == FAN_NOFD or event_fd < 0:
                continue

            try:
                real_path = os.readlink(f"/proc/self/fd/{event_fd}")
            except OSError:
                real_path = None
            finally:
                try:
                    os.close(event_fd)
                except OSError:
                    pass

            if not real_path:
                continue

            if real_path.endswith(" (deleted)"):
                real_path = real_path[: -len(" (deleted)")]

            with self._lock:
                self._recent[os.path.normcase(real_path)] = (pid, time.time())

    def lookup(self, file_path):
        """Devuelve el PID visto más recientemente para 'file_path'
        dentro de CACHE_TTL_SECONDS, o None si no hay dato fresco --
        nunca inventa un PID (sección 8/9 de la especificación: "no
        inventar procesos")."""

        key = os.path.normcase(os.path.abspath(file_path))

        with self._lock:
            entry = self._recent.get(key)
            if entry is None:
                return None
            pid, ts = entry
            if time.time() - ts > self.CACHE_TTL_SECONDS:
                del self._recent[key]
                return None
            return pid
