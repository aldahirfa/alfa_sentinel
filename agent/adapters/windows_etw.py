"""Mecanismo PRIMARIO de atribución de procesos en Windows (2026-08-16,
ver PENDIENTES.md, "Atribución de procesos y completado del motor
heurístico"): consume la sesión ETW (Event Tracing for Windows) del
proveedor de kernel 'Microsoft-Windows-Kernel-File' para saber qué PID
generó una operación de E/S sobre un archivo, en vez de recorrer todos
los procesos del sistema (adapters/common.py, que se conserva como
FALLBACK -- sección 2/8 de la especificación, no se elimina).

============================================================
AVISO EXPLÍCITO -- ESTE MÓDULO NO ESTÁ VERIFICADO EN ESTE ENTORNO
============================================================
El entorno de desarrollo actual donde se escribió y probó este agente
es un sandbox Linux (ver tests/heuristic/README.md) -- no hay ninguna
máquina Windows real disponible para ejecutar este código ni una sola
vez. Está escrito siguiendo la API pública documentada de la librería
'pywintrace' (paquete 'etw' en PyPI, https://github.com/fireeye/pywintrace)
y la estructura conocida de EVENT_HEADER/EVENT_RECORD de ETW, pero
NO se simula que funcione (sección 30 de la especificación: "no
simular, no inventar"). Antes de confiar en este mecanismo en
producción hace falta:
  1. Correr el agente en una máquina Windows real, como Administrador
     (ETW real-time tracing sobre un proveedor de kernel exige el
     privilegio SeSystemProfilePrivilege, que solo tienen las cuentas
     de Administrador -- ver sección 6 de la especificación: "si ETW
     ... requiere permisos especiales, documentarlos claramente").
  2. Confirmar los nombres de clave reales que pywintrace expone en el
     diccionario de cada evento (difieren entre versiones de la
     librería y no se pudieron confirmar sin poder ejecutarlo) -- por
     eso _extract_pid()/_extract_path() abajo prueban varias claves
     candidatas conocidas de la documentación pública en vez de asumir
     una sola, y si ninguna coincide, se registra el evento crudo una
     vez (no en cada evento) para poder diagnosticarlo con datos
     reales en vez de a ciegas.
Mientras tanto, el agente sigue funcionando igual en Windows: si
pywintrace no está instalado, si la sesión ETW no arranca (por
ejemplo por falta de privilegios), o si ocurre cualquier error al
consumir eventos, este módulo se desactiva limpiamente (available =
False) y adapters/windows_adapter.py cae al fallback de
psutil.open_files(), que sí está probado y funciona igual en Windows
que en Linux (ambos módulos comparten adapters/common.py).
============================================================
"""

import os
import threading
import time


# GUID público y estable del proveedor de kernel de E/S de archivos --
# documentado por Microsoft y usado ampliamente en herramientas de
# análisis de ETW (incluido Sysmon internamente, aunque este módulo no
# depende de Sysmon -- consume el proveedor de kernel directo, sin
# ningún servicio externo que un administrador tenga que instalar por
# separado, sección 4 de la especificación: "NO utilizar Sysmon como
# dependencia obligatoria").
KERNEL_FILE_PROVIDER_NAME = "Microsoft-Windows-Kernel-File"
KERNEL_FILE_PROVIDER_GUID = "{EDD08927-9CC4-4E65-B970-C2560FB5C289}"

SESSION_NAME = "AlfaSentinelFileIoTrace"

# Nombres de clave candidatos para el PID y la ruta del archivo dentro
# del evento que entrega pywintrace -- ver aviso arriba: no se pudo
# confirmar cuál usa la versión instalada sin poder ejecutar esto en
# Windows real, así que se prueban en orden.
_PID_KEYS = ("ProcessId", "ProcessID", "PID", "process_id")
_PATH_KEYS = ("FileName", "OpenPath", "FilePath", "TargetFileName", "file_name")


class EtwUnavailable(Exception):
    """La sesión ETW no pudo iniciarse -- casi siempre por falta de
    privilegios de Administrador, o porque pywintrace no está
    instalado en este entorno (por ejemplo, este mismo entorno de
    desarrollo, que es Linux)."""


class EtwFileIoWatcher:
    """Mismo patrón de caché que FanotifyWatcher (linux_fanotify.py):
    mantiene (ruta normalizada -> (pid, timestamp)) a partir de los
    eventos que va entregando la sesión ETW, y adapters/windows_adapter.py
    la consulta cuando watchdog reporta un evento de archivo."""

    CACHE_TTL_SECONDS = 5.0
    # Cuántos eventos con forma inesperada (sin ninguna clave
    # candidata reconocida) se registran en el log antes de dejar de
    # hacerlo -- para diagnosticar el problema real una vez que esto
    # se corra en Windows de verdad, sin inundar la consola si el
    # supuesto de nombres de clave está mal para TODOS los eventos.
    _MAX_UNPARSED_LOGGED = 3

    def __init__(self):
        self._recent = {}
        self._lock = threading.Lock()
        self._etw = None
        self.available = False
        self._unparsed_logged = 0

    def start(self):
        """Intenta iniciar la sesión ETW. Devuelve True si arrancó,
        False si no está disponible (librería no instalada, no es
        Windows, o sin privilegios de Administrador) -- NUNCA lanza
        hacia el llamador; adapters/windows_adapter.py cae al fallback
        de psutil si esto devuelve False."""

        try:
            from etw import ETW, ProviderInfo
            from etw.GUID import GUID
        except ImportError:
            print(
                "⚠ Atribución de procesos (Windows): la librería 'pywintrace' (paquete "
                "'etw') no está instalada -- se usa el mecanismo de respaldo "
                "(psutil.open_files()). Instalala con 'pip install pywintrace' dentro del "
                ".venv si querés probar la atribución vía ETW."
            )
            return False

        try:
            provider = ProviderInfo(KERNEL_FILE_PROVIDER_NAME, GUID(KERNEL_FILE_PROVIDER_GUID))
            self._etw = ETW(
                session_name=SESSION_NAME,
                providers=[provider],
                event_callback=self._on_event,
            )
            self._etw.start()
        except Exception as error:
            # No se acota a una excepción de Windows específica (ej.
            # pywin32's error) a propósito -- distintas versiones de
            # pywintrace envuelven el error de privilegios de forma
            # distinta (permiso denegado al abrir la sesión de
            # rastreo). Cualquier falla acá tiene que degradar al
            # fallback, no tumbar el agente.
            print(
                f"⚠ Atribución de procesos (Windows): no se pudo iniciar la sesión ETW "
                f"sobre '{KERNEL_FILE_PROVIDER_NAME}' ({error}). Requiere privilegios de "
                f"Administrador (SeSystemProfilePrivilege) -- se usa el mecanismo de "
                f"respaldo (psutil.open_files())."
            )
            self._etw = None
            return False

        self.available = True
        print(f"Atribución de procesos (Windows): sesión ETW activa sobre '{KERNEL_FILE_PROVIDER_NAME}'.")
        return True

    def stop(self):
        if self._etw is not None:
            try:
                self._etw.stop()
            except Exception:
                pass

    def _on_event(self, event_tuple):
        """Callback invocado por pywintrace en su propio hilo consumidor
        (no crea un thread propio acá, a diferencia de FanotifyWatcher,
        porque ETW.start() ya gestiona el suyo -- ver aviso al inicio
        del módulo sobre por qué esto no se pudo ejecutar ni una vez
        para confirmarlo). 'event_tuple' es (header, properties) según
        la documentación de pywintrace -- se acepta también la forma
        de un solo dict combinado por si la versión instalada difiere,
        para no romper en el primer evento real por un supuesto de
        forma equivocado."""

        try:
            if isinstance(event_tuple, tuple) and len(event_tuple) == 2:
                header, props = event_tuple
            else:
                header = props = event_tuple

            pid = self._extract(header, _PID_KEYS)
            if pid is None:
                pid = self._extract(props, _PID_KEYS)

            path = self._extract(props, _PATH_KEYS)
            if path is None:
                path = self._extract(header, _PATH_KEYS)

            if pid is None or not path:
                self._log_unparsed(header, props)
                return

            with self._lock:
                self._recent[os.path.normcase(os.path.abspath(path))] = (int(pid), time.time())

        except Exception as error:
            # Un evento con forma inesperada no puede tumbar el hilo
            # consumidor de ETW -- se registra y se sigue con el
            # próximo evento.
            print(f"⚠ ETW: error procesando un evento ({error}).")

    @staticmethod
    def _extract(source, candidate_keys):
        if not isinstance(source, dict):
            return None
        for key in candidate_keys:
            if key in source and source[key]:
                return source[key]
        return None

    def _log_unparsed(self, header, props):
        if self._unparsed_logged >= self._MAX_UNPARSED_LOGGED:
            return
        self._unparsed_logged += 1
        print(
            "⚠ ETW: evento recibido pero no se pudo extraer PID/ruta con las claves "
            f"candidatas conocidas -- header={header!r} properties={props!r}. Esto es "
            "esperable si pywintrace en tu versión usa otros nombres de clave (ver aviso "
            "al inicio de windows_etw.py); reportá este log para ajustar _PID_KEYS/"
            "_PATH_KEYS a los nombres reales."
        )

    def lookup(self, file_path):
        """Devuelve el PID visto más recientemente para 'file_path'
        dentro de CACHE_TTL_SECONDS, o None -- nunca inventa un PID."""

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
