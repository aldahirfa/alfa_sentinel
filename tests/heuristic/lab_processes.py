"""Utilidades compartidas del laboratorio de pruebas (sección 18 de la
especificación de atribución de procesos, 2026-08-16: "crear o
completar un laboratorio de pruebas... el laboratorio debe permitir
provocar comportamientos controlados. No necesito ransomware real. No
usar ransomware real.").

Todos los procesos que lanza este módulo son procesos Python reales
(el propio intérprete que corre las pruebas, vía sys.executable) --
nada se simula: los PID, nombres de proceso, rutas de ejecutable y
consumo de CPU que se miden son datos reales del sistema operativo.
"""
import os
import shutil
import subprocess
import sys
import time

LAB_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/lab_scripts"


def _script(name):
    return os.path.join(LAB_SCRIPTS_DIR, name)


def spawn_handshake_writer(file_path, interpreter=None):
    """Lanza un proceso que abre 'file_path' y lo mantiene abierto
    hasta llamar a signal_go(file_path). Usar wait_ready(file_path)
    antes de consultar la atribución -- evita adivinar cuánto tardó el
    proceso en abrir el archivo con un sleep fijo.

    'interpreter' permite correr el script con un binario de Python
    distinto al que corre las pruebas (ver make_relocated_interpreter)
    -- así HR-05 se prueba con un proceso real ejecutándose desde una
    ruta atípica, no con un PID inventado."""
    return subprocess.Popen([interpreter or sys.executable, _script("handshake_writer.py"), file_path])


def spawn_multi_writer(directory, count):
    """Lanza UN proceso que escribe 'count' archivos secuenciales
    dentro de 'directory', cada uno con el mismo handshake. Los
    archivos se llaman op_0.txt, op_1.txt, ... op_{count-1}.txt."""
    return subprocess.Popen([sys.executable, _script("multi_writer.py"), directory, str(count)])


def wait_ready(file_path, timeout=10.0):
    """Bloquea hasta que el proceso de laboratorio señale que el
    archivo ya está abierto (o hasta 'timeout'). Devuelve True/False."""
    marker = file_path + ".ready"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(marker):
            return True
        time.sleep(0.02)
    return False


def signal_go(file_path):
    """Le indica al proceso de laboratorio que ya puede cerrar el
    archivo y seguir (o terminar)."""
    open(file_path + ".go", "w").close()


def spawn_short_lived_writer(file_path):
    """Abre, escribe y cierra el archivo, y el proceso TERMINA antes
    de devolver el control -- para la Prueba C (atribución de un
    proceso que ya no existe). No usa handshake a propósito: el punto
    de esta prueba es que no haya nada que consultar para cuando se
    llama a la atribución."""
    script = f"open({file_path!r}, 'w').write('x')"
    proc = subprocess.Popen([sys.executable, "-c", script])
    proc.wait(timeout=10)
    return proc


def make_relocated_interpreter(lab_dir):
    """Copia el intérprete de Python real a una carpeta temporal --
    para HR-05 ('ejecución desde ubicación atípica'). No es una
    simulación: es un ejecutable real corriendo desde una ruta real
    distinta a la original. psutil.Process.exe() resuelve
    /proc/[pid]/exe (el inodo real del binario en ejecución, no
    argv[0]), así que refleja la ruta atípica de verdad."""
    os.makedirs(lab_dir, exist_ok=True)
    dest = os.path.join(lab_dir, os.path.basename(sys.executable))
    if not os.path.exists(dest):
        shutil.copy(sys.executable, dest)
        os.chmod(dest, 0o755)
    return dest


def spawn_cpu_burner(duration_seconds):
    """Proceso real que ocupa un núcleo de CPU al ~100% durante
    'duration_seconds' -- ver lab_scripts/cpu_burner.py."""
    return subprocess.Popen([sys.executable, _script("cpu_burner.py"), str(duration_seconds)])


def cleanup_markers(file_path):
    for suffix in (".ready", ".go"):
        try:
            os.remove(file_path + suffix)
        except OSError:
            pass
