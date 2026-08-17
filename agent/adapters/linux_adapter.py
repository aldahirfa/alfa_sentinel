from .common import find_process_for_open_file


def get_process_for_file_event(file_path, event_type):
    """Adaptador Linux. Usa la misma vía psutil que el resto (que en
    Linux lee /proc/[pid]/fd/* internamente), pero vive en su propio
    módulo a propósito: es el punto de extensión concreto para el día
    que se integre auditd (reglas de auditoría sobre las rutas
    vigiladas + parseo de /var/log/audit/audit.log, documentado como
    la vía "correcta" en PENDIENTES.md -- requiere que un admin
    instale y configure auditd por separado, fuera del alcance de este
    agente). Mientras eso no exista, esta es la mejor atribución
    posible sin tocar el kernel ni instalar drivers."""

    return find_process_for_open_file(file_path)
