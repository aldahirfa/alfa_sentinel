import platform

# Atribución de proceso a evento de archivo. Interfaz común para HR-05
# (Proceso Sospechoso) y HR-11 (Actividad Repetitiva Automatizada),
# que necesitan saber QUÉ proceso tocó un archivo -- dato que watchdog
# no expone.
#
# Reescrito 2026-08-16 (ver PENDIENTES.md, "Atribución de procesos y
# completado del motor heurístico") para usar un mecanismo NATIVO del
# sistema operativo como vía principal -- fanotify en Linux
# (linux_fanotify.py), ETW sobre 'Microsoft-Windows-Kernel-File' en
# Windows (windows_etw.py, NO VERIFICADO en este entorno de
# desarrollo, ver aviso al inicio de ese módulo) -- en vez de recorrer
# todos los procesos del sistema cada vez que llega un evento. El
# mecanismo anterior (adapters/common.py, psutil.open_files()) se
# conserva sin cambios como FALLBACK: si el mecanismo nativo no está
# disponible (sin privilegios, librería no instalada) o no tiene un
# dato fresco para esta ruta puntual, cada adaptador de SO cae a él
# automáticamente.
#
# LO QUE ESTO NO ES: no es Sysmon (Windows) ni auditd (Linux) --
# ninguno de los dos es una dependencia obligatoria (secciones 4/5 de
# la especificación). Ambos serían la forma "más completa" de hacer
# esto, pero son servicios externos que un administrador instala y
# configura por separado; este agente usa APIs del propio SO (ETW,
# fanotify) sin necesitar esa instalación adicional. Tampoco se
# modifica el kernel, no se instalan drivers, no se hacen hooks ni
# inyección de procesos (sección 4/5).
#
# LO QUE ES: cadena de atribución con 3 pasos, documentada en detalle
# en cada adaptador de SO -- 1) mecanismo nativo, 2) psutil.open_files()
# como respaldo, 3) None si ninguno pudo atribuir. Nunca se inventa un
# valor parcial (sección 8/9: "no inventar process_id ni
# process_name"; "la atribución no es 100% -- eso es válido").
from .common import find_process_for_open_file


def get_process_for_file_event(file_path, event_type):
    """Punto de entrada único, sin importar el SO. Devuelve
    {"process_id", "process_name", "executable_path", "username"} si
    se pudo determinar el proceso responsable, o None si no se pudo
    (nunca inventa un valor parcial)."""

    system = platform.system()

    if system == "Windows":
        from .windows_adapter import get_process_for_file_event as _impl
    elif system == "Linux":
        from .linux_adapter import get_process_for_file_event as _impl
    else:
        # macOS u otro SO no cubierto explícitamente por la
        # especificación -- se usa la implementación compartida
        # (psutil funciona igual ahí) en vez de fallar. Sin mecanismo
        # nativo específico para macOS (no estaba pedido).
        def _impl(path, evt):
            return find_process_for_open_file(path)

    return _impl(file_path, event_type)
