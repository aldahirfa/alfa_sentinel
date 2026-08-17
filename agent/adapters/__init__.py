import platform

# Atribución de proceso a evento de archivo (2026-08-16, ver
# PENDIENTES.md, "Implementación final del motor heurístico y
# configuración por endpoint"). Interfaz común para HR-05 (Proceso
# Sospechoso) y HR-11 (Actividad Repetitiva Automatizada), que
# necesitan saber QUÉ proceso tocó un archivo -- dato que watchdog no
# expone (ver PENDIENTES.md, sección "Atribución de proceso en eventos
# de archivo" -- limitación documentada del SO, no de la librería).
#
# LO QUE ESTO NO ES: no es Sysmon (Windows) ni auditd (Linux), que
# serían la forma "correcta" de hacer esto con precisión (interceptan
# el evento de E/S a nivel de kernel/auditoría del SO). Instalar y
# configurar esos sistemas está fuera del alcance de este agente (son
# servicios externos con privilegios elevados que un admin instala por
# separado, no algo que este proyecto pueda instalar o gestionar por
# sí mismo -- y la tarea explícitamente prohíbe tocar el kernel o
# instalar drivers).
#
# LO QUE ES: un best-effort real usando psutil (ya es dependencia del
# proyecto, agent/process_monitor.py) -- en el instante en que llega
# el evento de archivo, se recorren los procesos vivos y se busca cuál
# tiene ESE archivo abierto ahora mismo (Process.open_files()). Cuando
# lo encuentra, es una atribución real, no inventada. Limitación
# honesta y documentada: si el proceso ya cerró el archivo para cuando
# se lo consulta (escritura muy rápida, abrir-escribir-cerrar en
# microsegundos), no hay forma de saber quién fue -- se devuelve None
# en vez de adivinar. Esto es exactamente la razón por la que HR-05/11
# son heurísticas de "lo que se pudo observar", no una atribución
# garantizada al 100%.
from .common import find_process_for_open_file


def get_process_for_file_event(file_path, event_type):
    """Punto de entrada único, sin importar el SO. Devuelve
    {"process_id", "process_name", "executable_path"} si se pudo
    determinar el proceso responsable, o None si no se pudo (nunca
    inventa un valor parcial -- sección 8 de la especificación:
    "no inventar process_id ni process_name")."""

    system = platform.system()

    if system == "Windows":
        from .windows_adapter import get_process_for_file_event as _impl
    elif system == "Linux":
        from .linux_adapter import get_process_for_file_event as _impl
    else:
        # macOS u otro SO no cubierto explícitamente por la
        # especificación -- se usa la implementación compartida
        # (psutil funciona igual ahí) en vez de fallar.
        def _impl(path, evt):
            return find_process_for_open_file(path, case_sensitive=True)

    return _impl(file_path, event_type)
