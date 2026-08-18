"""HR-05 (Proceso Sospechoso) con atribución REAL (sección 20 de la
especificación de atribución de procesos, 2026-08-16): "Crear un
proceso controlado de laboratorio. Debe poder ejecutarse desde una
ruta que el motor considere sospechosa... Verificar: process_id,
process_name, executable_path y después: HR-05. No simular el proceso
responsable."

No se simula nada: se copia el intérprete de Python real a una
carpeta temporal (ruta que el motor SÍ considera atípica, ver
heuristic_engine._is_suspicious_executable_path) y se lo corre desde
ahí -- psutil.Process.exe() resuelve /proc/[pid]/exe, el inodo real
del binario en ejecución, así que la ruta "sospechosa" es genuina, no
inventada.

Ejecutar: python3 tests/heuristic/test_hr05_proceso_sospechoso.py
"""
import os
import shutil
import sys
import tempfile

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import get_process_for_file_event  # noqa: E402
from heuristic_engine import FileActivityAnalyzer  # noqa: E402
import lab_processes as lab  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


LAB_DIR = tempfile.mkdtemp(prefix="alfa_hr05_lab_")

try:
    # ---------------- Proceso NORMAL (ruta estándar) ----------------
    # El propio intérprete que corre esta prueba -- en un sistema
    # instalado normalmente vive en /usr/bin (Linux) o Program Files
    # (Windows), ambos en STANDARD_PROGRAM_MARKERS.
    file_normal = os.path.join(LAB_DIR, "normal.txt")
    proc_normal = lab.spawn_handshake_writer(file_normal)
    try:
        lab.wait_ready(file_normal)
        process_info_normal = get_process_for_file_event(file_normal, "file_modified")
        check("Proceso normal: atribución real obtenida", process_info_normal is not None, str(process_info_normal))
        if process_info_normal:
            print("   executable_path real:", process_info_normal.get("executable_path"))

        analyzer_normal = FileActivityAnalyzer.from_policy([
            {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
        ])
        matched_normal = analyzer_normal.register_event(
            file_normal, "file_modified", process_info=process_info_normal
        )
        check("HR-05 NO dispara para el intérprete real desde su ruta estándar", "Proceso Sospechoso" not in matched_normal, str(matched_normal))
    finally:
        lab.signal_go(file_normal)
        proc_normal.wait(timeout=10)

    # ---------------- Proceso SOSPECHOSO (ruta atípica real) ----------------
    relocated_interpreter = lab.make_relocated_interpreter(os.path.join(LAB_DIR, "ruta_atipica"))
    check("Se copió un intérprete real a una ruta atípica (carpeta temporal)", os.path.exists(relocated_interpreter))

    file_suspicious = os.path.join(LAB_DIR, "sospechoso.txt")
    proc_suspicious = lab.spawn_handshake_writer(file_suspicious, interpreter=relocated_interpreter)
    try:
        ready = lab.wait_ready(file_suspicious)
        check("Proceso desde ruta atípica: se abrió el archivo", ready)

        process_info_suspicious = get_process_for_file_event(file_suspicious, "file_modified")
        check("Proceso sospechoso: atribución real obtenida", process_info_suspicious is not None, str(process_info_suspicious))
        if process_info_suspicious:
            check(
                "Proceso sospechoso: executable_path apunta a la ruta atípica real (no inventada)",
                process_info_suspicious.get("executable_path") == relocated_interpreter,
                str(process_info_suspicious),
            )
            check("Proceso sospechoso: process_id = PID real del proceso relocalizado", process_info_suspicious["process_id"] == proc_suspicious.pid)

        analyzer_susp = FileActivityAnalyzer.from_policy([
            {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
        ])
        matched_susp = analyzer_susp.register_event(
            file_suspicious, "file_modified", process_info=process_info_suspicious
        )
        check("HR-05 SÍ dispara para un proceso real corriendo desde una ruta atípica real", "Proceso Sospechoso" in matched_susp, str(matched_susp))
    finally:
        lab.signal_go(file_suspicious)
        proc_suspicious.wait(timeout=10)

    # ---------------- Regla de oro: no inventar sospecha por ausencia de dato ----------------
    analyzer_none = FileActivityAnalyzer.from_policy([
        {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
    ])
    matched_none = analyzer_none.register_event("/tmp/no_existe.txt", "file_modified", process_info=None)
    check(
        "HR-05 NO trata 'no se pudo atribuir' (process_info=None) como sospechoso",
        "Proceso Sospechoso" not in matched_none,
        str(matched_none),
    )

finally:
    shutil.rmtree(LAB_DIR, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_hr05_proceso_sospechoso.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
