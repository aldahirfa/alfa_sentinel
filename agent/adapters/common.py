import json
import os
import subprocess
import sys

import psutil


def enrich_pid(pid):
    """Dado un PID ya conocido (obtenido por un mecanismo nativo del
    SO -- fanotify en Linux, ETW en Windows, ver linux_fanotify.py/
    windows_etw.py), completa nombre, ruta del ejecutable y usuario
    vía psutil. Devuelve None si el proceso ya no existe para cuando
    se consulta (procesos de vida muy corta: el kernel ya vio el
    evento, pero el proceso terminó antes de que psutil llegara a
    inspeccionarlo) -- nunca se inventa un valor parcial (sección 9 de
    la especificación de atribución: 'si el proceso ya terminó...
    process_id = NULL, process_name = NULL. Eso es válido')."""

    try:
        process = psutil.Process(pid)
        with process.oneshot():
            name = process.name()
            try:
                exe = process.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                # Ruta del ejecutable no disponible (proceso de otro
                # usuario/sistema) -- no impide reportar el resto.
                exe = None
            try:
                username = process.username()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                username = None
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None

    return {
        "process_id": pid,
        "process_name": name,
        "executable_path": exe,
        "username": username,
    }


def find_process_for_open_file(file_path):
    """FALLBACK (sección 2/8 de la especificación de atribución de
    procesos, 2026-08-16: "NO eliminar inmediatamente este mecanismo,
    mantenerlo como fallback") -- se usa cuando el mecanismo nativo
    del SO (fanotify/ETW) no está disponible o no tiene un dato
    fresco para esta ruta puntual. Recorre los procesos vivos buscando
    cuál tiene 'file_path' abierto ahora mismo (Process.open_files()).
    Compartido entre windows_adapter.py y linux_adapter.py -- usa
    os.path.normcase(), que ya es sensible al SO por sí solo (en
    Windows normaliza a minúsculas y unifica separadores; en POSIX es
    un no-op, porque ahí sí importan mayúsculas/minúsculas), así que
    la comparación de rutas ya es correcta por plataforma sin lógica
    adicional acá.

    Costo: O(procesos vivos) por llamada, cada uno con una syscall
    real (open_files()). Se llama una vez por evento de archivo, no en
    un loop de polling -- el propio ritmo de eventos de archivo limita
    la frecuencia. Con el mecanismo nativo como primario (cuando está
    disponible), este recorrido completo pasa a ser la excepción, no
    la regla."""

    target = os.path.normcase(os.path.abspath(file_path))

    for process in psutil.process_iter(["pid"]):

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
                enriched = enrich_pid(process.pid)
                if enriched is not None:
                    return enriched

    return None


# Límite para un recorrido completo de archivos abiertos (ver open_files_index).
OPEN_FILES_SCAN_TIMEOUT_SECONDS = 20

# El recorrido corre en un proceso aparte: el mismo código de abajo, sin
# depender de ningún módulo del agente.
_SCAN_SCRIPT = r"""
import json, os, sys, psutil
index = {}
for process in psutil.process_iter(["pid"]):
    try:
        open_files = process.open_files()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        continue
    except Exception:
        continue
    for open_file in open_files:
        index.setdefault(os.path.normcase(os.path.abspath(open_file.path)), process.pid)
sys.stdout.write(json.dumps(index))
"""


def open_files_index(timeout=OPEN_FILES_SCAN_TIMEOUT_SECONDS):
    """Un solo recorrido de procesos (el mismo de find_process_for_open_file)
    que devuelve {ruta normalizada: pid} con TODOS los archivos abiertos
    en este momento. En Windows cada recorrido tarda varios segundos
    (medido: ~18 s con ~170 procesos), así que file_monitor.py lo hace una
    vez por lote de eventos en vez de una vez por evento (2026-10-05).

    Corre en un PROCESO APARTE con límite de tiempo (2026-10-06): en una
    prueba con RanSim el agente quedó congelado 27 minutos (sin heartbeat,
    sin eventos, sin detectar un honeyfile) con el proceso vivo. La consulta
    de archivos abiertos de Windows puede quedar trabada con ciertos tipos
    de handle, y dentro del agente se llevaba consigo a todos los hilos. Si
    el recorrido no termina a tiempo se descarta: ese lote de eventos queda
    sin proceso atribuido (lo mismo que cuando no se puede atribuir)."""

    try:
        result = subprocess.run(
            [sys.executable, "-c", _SCAN_SCRIPT],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"⚠ El recorrido de archivos abiertos superó {timeout} s y se descartó (lote sin atribución de proceso).")
        return {}
    except OSError as error:
        print(f"⚠ No se pudo recorrer los archivos abiertos: {error}")
        return {}
    if result.returncode != 0:
        print(f"⚠ El recorrido de archivos abiertos falló: {(result.stderr or '').strip()[-300:]}")
        return {}
    try:
        return {path: int(pid) for path, pid in json.loads(result.stdout or "{}").items()}
    except (ValueError, AttributeError):
        return {}
