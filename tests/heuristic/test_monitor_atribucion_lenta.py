"""Regresión 2026-10-05: las reglas no se activaban en Windows porque el
agente buscaba el proceso responsable de CADA evento recorriendo todos
los procesos (psutil.open_files(), ~18 s por evento medido en una laptop
real) ANTES de evaluar las reglas. 20 borrados nunca caían dentro de los
15 s de HR-09.

Esta prueba usa el monitor real (watchdog + FileActivityHandler) sobre
una carpeta temporal, con la atribución simulada a 18 s por recorrido y
sin servidor (send_event/send_alert reemplazados), y comprueba que:
  - HR-09 se detecta en segundos al borrar 25 archivos;
  - HR-01 se detecta al modificar 25 archivos;
  - HR-11 se sigue detectando con el recorrido lento (un solo recorrido
    por lote, evaluado con el momento real de cada evento).

Corre igual en Windows y Linux."""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))

import file_monitor  # noqa: E402
from heuristic_engine import DEFAULT_RULES  # noqa: E402

SCAN_SECONDS = 18.0
alerts = []
events = []
scans = []

file_monitor.send_alert = lambda credential, data: alerts.append((time.time(), data["matched_rules"]))
file_monitor.send_event = lambda credential, data: events.append(data)
file_monitor.get_process_for_file_event = lambda path, evt, allow_scan=True: None


def slow_index():
    """Simula el recorrido lento de Windows: devuelve como 'abiertos' los
    archivos de la carpeta HR11 (como si un solo proceso los tuviera)."""
    scans.append(time.time())
    time.sleep(SCAN_SECONDS)
    return {os.path.normcase(os.path.abspath(os.path.join(hr11_dir, n))): os.getpid()
            for n in os.listdir(hr11_dir)}


file_monitor.open_files_index = slow_index


def rules_seen(since):
    return {r for t, matched in alerts if t >= since for r in matched}


def wait_for(rule, since, limit):
    end = time.time() + limit
    while time.time() < end:
        if rule in rules_seen(since):
            return time.time() - since
        time.sleep(0.2)
    return None


root = tempfile.mkdtemp(prefix="alfa_lab_")
prep = tempfile.mkdtemp(prefix="alfa_prep_")
hr09_dir = os.path.join(root, "HR09")
hr01_dir = os.path.join(root, "HR01")
hr11_dir = os.path.join(root, "HR11")
for d in (hr09_dir, hr01_dir, hr11_dir):
    os.makedirs(d)

rules = [{"name": n, "threshold": c["threshold"], "window_seconds": c["window_seconds"]}
         for n, c in DEFAULT_RULES.items()]
observer, analyzer, *_ = file_monitor.start_file_monitor([root], "cred-prueba", rule_policy=rules)
time.sleep(1)
results = []

try:
    # HR-09: 25 archivos que llegan movidos (no cuentan como modificados) y se borran.
    for i in range(25):
        src = os.path.join(prep, f"doc_{i:03d}.txt")
        with open(src, "w") as f:
            f.write("x")
        os.replace(src, os.path.join(hr09_dir, f"doc_{i:03d}.txt"))
    time.sleep(4)
    t0 = time.time()
    for i in range(25):
        os.remove(os.path.join(hr09_dir, f"doc_{i:03d}.txt"))
    took = wait_for("Eliminacion Anomala Archivos", t0, 10)
    results.append(("HR-09 detectada con atribución de 18 s por recorrido", took is not None, took))

    time.sleep(16)  # deja vencer la ventana de HR-09

    # HR-01: 25 archivos distintos modificados.
    for i in range(25):
        src = os.path.join(prep, f"mod_{i:03d}.txt")
        with open(src, "w") as f:
            f.write("x")
        os.replace(src, os.path.join(hr01_dir, f"mod_{i:03d}.txt"))
    time.sleep(3)
    t0 = time.time()
    for i in range(25):
        with open(os.path.join(hr01_dir, f"mod_{i:03d}.txt"), "a") as f:
            f.write("y")
    took = wait_for("Modificacion Masiva Archivos", t0, 10)
    results.append(("HR-01 detectada con atribución de 18 s por recorrido", took is not None, took))

    # HR-11: 45 archivos creados por "el mismo proceso" (el índice simulado lo dice).
    time.sleep(2)
    t0 = time.time()
    for i in range(45):
        with open(os.path.join(hr11_dir, f"auto_{i:03d}.dat"), "x"):
            pass
    took = wait_for("Actividad Repetitiva Automatizada", t0, 3 * SCAN_SECONDS + 10)
    results.append(("HR-11 detectada aunque el recorrido tarde 18 s (lotes)", took is not None, took))
    results.append(("recorridos de psutil << eventos (uno por lote, no por evento)",
                    len(scans) < 10, len(scans)))
finally:
    observer.stop()
    observer.join()
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(prep, ignore_errors=True)

ok = 0
for name, passed, value in results:
    ok += passed
    extra = f" ({value:.1f} s)" if isinstance(value, float) else (f" ({value})" if value is not None else "")
    print(f"{'PASS' if passed else 'FAIL'} - {name}{extra}")
print(f"\n{ok}/{len(results)} pruebas OK (test_monitor_atribucion_lenta.py), "
      f"{len(events)} eventos de telemetría, {len(scans)} recorridos")
sys.exit(0 if ok == len(results) else 1)
