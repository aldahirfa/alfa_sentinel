import os

import psutil


def find_process_for_open_file(file_path):
    """Recorre los procesos vivos buscando cuál tiene 'file_path'
    abierto ahora mismo (Process.open_files()). Compartido entre
    windows_adapter.py y linux_adapter.py -- usa os.path.normcase(),
    que ya es sensible al SO por sí solo (en Windows normaliza a
    minúsculas y unifica separadores; en POSIX es un no-op, porque ahí
    sí importan mayúsculas/minúsculas), así que la comparación de rutas
    ya es correcta por plataforma sin lógica adicional acá.

    Costo: O(procesos vivos) por llamada, cada uno con una syscall
    real (open_files()) -- no hay forma de evitarlo sin Sysmon/auditd
    (ver comentario en adapters/__init__.py). Se llama una vez por
    evento de archivo, no en un loop de polling -- el propio ritmo de
    eventos de archivo limita la frecuencia."""

    target = os.path.normcase(os.path.abspath(file_path))

    for process in psutil.process_iter(["pid", "name", "exe"]):

        try:
            open_files = process.open_files()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Procesos del sistema o de otro usuario -- no se puede
            # inspeccionar sin privilegios elevados. Se saltea, no se
            # cuenta como "no sospechoso" ni como "sospechoso": no hay
            # dato, así que no participa de la atribución.
            continue

        for open_file in open_files:
            candidate = os.path.normcase(os.path.abspath(open_file.path))
            if candidate == target:
                try:
                    info = process.as_dict(attrs=["pid", "name", "exe"])
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                return {
                    "process_id": info.get("pid"),
                    "process_name": info.get("name"),
                    "executable_path": info.get("exe"),
                }

    return None
