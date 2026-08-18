"""HR-06 (Consumo CPU Elevado) con procesos REALES (sección 21 de la
especificación de atribución de procesos, 2026-08-16): "Crear un
proceso controlado que consuma CPU. Prueba negativa: CPU >= threshold
durante menos que window_seconds -> NO HR-06. Prueba positiva: CPU >=
threshold durante window_seconds o más -> HR-06."

Usa agent/cpu_monitor.py::CpuMonitor real (no una reimplementación) --
muestreando un proceso real que quema CPU de verdad
(lab_scripts/cpu_burner.py), no valores sintéticos. Los umbrales/
ventana de prueba son deliberadamente cortos (no los 80%/10s de
producción) para que la prueba corra en segundos, no minutos -- eso no
duplica la configuración real: se pasan como parámetros al mismo
CpuMonitor de producción, no se reimplementa la lógica de evaluación
con otro umbral hardcodeado en otro lado.

Ejecutar: python3 tests/heuristic/test_hr06_cpu_elevado.py
"""
import os
import sys
import time

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cpu_monitor as cpu_monitor_module  # noqa: E402
from cpu_monitor import CpuMonitor  # noqa: E402
import lab_processes as lab  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


captured_alerts = []


def fake_send_alert(credential, payload):
    captured_alerts.append(payload)


cpu_monitor_module.send_alert = fake_send_alert

# Umbral bajo (10%) para no depender de saturar un núcleo entero en un
# sandbox posiblemente compartido -- lo que importa es la LÓGICA de
# sostenido-vs-instantáneo, no el número exacto.
THRESHOLD = 10.0
# Muestreo rápido para que la prueba no tarde minutos.
cpu_monitor_module.SAMPLE_INTERVAL_SECONDS = 0.5


# ---------------- Prueba positiva ----------------
# CPU >= threshold durante window_seconds o más -> HR-06 sí dispara.
# Ventana de 3s (no más chica) a propósito: la primerísima muestra de
# psutil.cpu_percent() para un proceso siempre devuelve 0.0 (es el
# "priming", ver CpuMonitor.start()) -- con una ventana muy ajustada
# respecto al intervalo de muestreo, esa muestra inicial en 0.0
# alcanza a romper la condición de "sostenido" (todas las muestras >=
# umbral) el tiempo suficiente para que 'covers_window' nunca llegue a
# cumplirse antes de que el proceso termine. 3s de ventana con 0.5s de
# intervalo da margen real una vez que esa muestra inicial se poda.
WINDOW_POSITIVE = 3.0
captured_alerts.clear()

burner = lab.spawn_cpu_burner(duration_seconds=10.0)
time.sleep(0.3)  # dar tiempo a que el proceso aparezca en psutil.process_iter() antes de primear
monitor = CpuMonitor(credential="fake", threshold=THRESHOLD, window_seconds=WINDOW_POSITIVE)
monitor.start()

deadline = time.time() + 12.0
fired = False
while time.time() < deadline:
    if captured_alerts:
        fired = True
        break
    time.sleep(0.25)

monitor.stop()
if burner.poll() is None:
    burner.kill()
burner.wait(timeout=5)

check(
    f"Positiva: CPU sostenida >= {THRESHOLD}% durante >= {WINDOW_POSITIVE}s -> HR-06 dispara",
    fired,
    f"alertas capturadas={len(captured_alerts)}",
)
if captured_alerts:
    check("Positiva: la alerta reporta 'Consumo CPU Elevado' en matched_rules", captured_alerts[0]["matched_rules"] == ["Consumo CPU Elevado"], str(captured_alerts[0]))

# ---------------- Prueba negativa ----------------
# CPU >= threshold durante MENOS que window_seconds (el proceso
# termina antes de completar la ventana) -> HR-06 NO dispara.
WINDOW_NEGATIVE = 6.0
captured_alerts.clear()

# El "priming" de psutil.cpu_percent() descarta la primera lectura, y
# el proceso solo vive ~1s -- muy por debajo de la ventana de 6s, así
# que nunca se junta evidencia suficiente para cubrir la ventana
# completa (ver CpuMonitor._evaluate: 'covers_window').
short_burner = lab.spawn_cpu_burner(duration_seconds=1.0)
monitor_neg = CpuMonitor(credential="fake", threshold=THRESHOLD, window_seconds=WINDOW_NEGATIVE)
monitor_neg.start()

short_burner.wait(timeout=5)
time.sleep(1.5)  # dejar correr algunas muestras más después de que el proceso ya terminó
monitor_neg.stop()

check(
    f"Negativa: CPU alta durante menos que la ventana ({WINDOW_NEGATIVE}s) -> HR-06 NO dispara",
    len(captured_alerts) == 0,
    f"alertas capturadas={len(captured_alerts)}",
)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_hr06_cpu_elevado.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
