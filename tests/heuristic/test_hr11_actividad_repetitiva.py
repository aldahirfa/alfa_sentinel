"""HR-11 (Actividad Repetitiva Automatizada) con atribución REAL
(sección 22 de la especificación de atribución de procesos,
2026-08-16): "Prueba positiva: un único proceso realiza >= threshold
operaciones -> HR-11. Prueba negativa: dos procesos reparten las
operaciones -> NO HR-11."

Usa el mismo pipeline real que el agente en producción: adapters.get_process_for_file_event(...)
para atribuir cada evento a un PID real, y agent/heuristic_engine.py::FileActivityAnalyzer.register_event(...)
para evaluar la regla -- nada de esto está reimplementado ni
simulado.

Ejecutar: python3 tests/heuristic/test_hr11_actividad_repetitiva.py
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


THRESHOLD = 4
WINDOW_SECONDS = 15

LAB_DIR = tempfile.mkdtemp(prefix="alfa_hr11_lab_")

try:
    # ---------------- Prueba positiva: un solo proceso ----------------
    # Un único proceso de laboratorio realiza THRESHOLD operaciones
    # sobre archivos distintos -> HR-11 debe disparar en la última.
    positive_dir = os.path.join(LAB_DIR, "positiva")
    proc_single = lab.spawn_multi_writer(positive_dir, THRESHOLD)

    analyzer_positive = FileActivityAnalyzer.from_policy([
        {"name": "Actividad Repetitiva Automatizada", "threshold": THRESHOLD, "window_seconds": WINDOW_SECONDS},
    ])

    matched_history = []
    try:
        for i in range(THRESHOLD):
            file_path = os.path.join(positive_dir, f"op_{i}.txt")
            ready = lab.wait_ready(file_path)
            if not ready:
                matched_history.append(None)
                continue
            process_info = get_process_for_file_event(file_path, "file_modified")
            matched = analyzer_positive.register_event(file_path, "file_modified", process_info=process_info)
            matched_history.append(matched)
            lab.signal_go(file_path)
        proc_single.wait(timeout=15)
    finally:
        if proc_single.poll() is None:
            proc_single.kill()

    check(
        f"Positiva: se pudieron atribuir y registrar las {THRESHOLD} operaciones",
        all(m is not None for m in matched_history),
        str(matched_history),
    )
    check(
        "Positiva: HR-11 dispara en la operación que alcanza el umbral (mismo proceso real)",
        matched_history and "Actividad Repetitiva Automatizada" in matched_history[-1],
        str(matched_history),
    )
    check(
        "Positiva: HR-11 NO dispara antes de alcanzar el umbral",
        all("Actividad Repetitiva Automatizada" not in m for m in matched_history[:-1] if m is not None),
        str(matched_history),
    )

    # ---------------- Prueba negativa: dos procesos reparten las operaciones ----------------
    # Cada proceso hace THRESHOLD-2 operaciones (menos que el umbral
    # individualmente) -- el TOTAL del "endpoint" suma >= threshold,
    # pero HR-11 mide por PROCESO, no por endpoint (a diferencia de
    # HR-01/HR-04) -- ninguno de los dos debería disparar.
    ops_per_process = THRESHOLD - 1  # cada uno queda 1 por debajo del umbral
    dir_p1 = os.path.join(LAB_DIR, "negativa_p1")
    dir_p2 = os.path.join(LAB_DIR, "negativa_p2")
    proc_p1 = lab.spawn_multi_writer(dir_p1, ops_per_process)
    proc_p2 = lab.spawn_multi_writer(dir_p2, ops_per_process)

    analyzer_negative = FileActivityAnalyzer.from_policy([
        {"name": "Actividad Repetitiva Automatizada", "threshold": THRESHOLD, "window_seconds": WINDOW_SECONDS},
    ])

    any_matched = False
    total_ops_registered = 0
    try:
        for i in range(ops_per_process):
            for directory in (dir_p1, dir_p2):
                file_path = os.path.join(directory, f"op_{i}.txt")
                ready = lab.wait_ready(file_path)
                if not ready:
                    continue
                process_info = get_process_for_file_event(file_path, "file_modified")
                matched = analyzer_negative.register_event(file_path, "file_modified", process_info=process_info)
                total_ops_registered += 1
                if "Actividad Repetitiva Automatizada" in matched:
                    any_matched = True
                lab.signal_go(file_path)
        proc_p1.wait(timeout=15)
        proc_p2.wait(timeout=15)
    finally:
        for p in (proc_p1, proc_p2):
            if p.poll() is None:
                p.kill()

    check(
        f"Negativa: se registraron {2 * ops_per_process} operaciones repartidas entre 2 procesos reales",
        total_ops_registered == 2 * ops_per_process,
        str(total_ops_registered),
    )
    check(
        "Negativa: el total de operaciones (repartidas en 2 PID distintos) alcanzaría el umbral si se contara por endpoint",
        total_ops_registered >= THRESHOLD,
    )
    check(
        "Negativa: HR-11 NO dispara -- ningún PID individual llegó al umbral (no se confunde con HR-01/04)",
        not any_matched,
    )

finally:
    shutil.rmtree(LAB_DIR, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_hr11_actividad_repetitiva.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
