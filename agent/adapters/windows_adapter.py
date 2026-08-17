from .common import find_process_for_open_file


def get_process_for_file_event(file_path, event_type):
    """Adaptador Windows. Usa la misma vía psutil que el resto (psutil
    ya abstrae la syscall real de Windows -- NtQuerySystemInformation/
    handles abiertos -- detrás de Process.open_files()), pero vive en
    su propio módulo a propósito: es el punto de extensión concreto
    para el día que se integre una fuente de datos específica de
    Windows con mejor precisión (ej. el canal
    Microsoft-Windows-Sysmon/Operational vía pywin32, documentado como
    la vía "correcta" en PENDIENTES.md -- requiere que un admin instale
    y configure Sysmon por separado, fuera del alcance de este agente).
    Mientras eso no exista, esta es la mejor atribución posible sin
    tocar el kernel ni instalar drivers."""

    return find_process_for_open_file(file_path)
