"""HR-06 -- casos límite con muestras SINTÉTICAS (sin hilos ni psutil
real) -- complemento rápido y determinístico de
test_hr06_cpu_elevado.py (que sí usa un proceso de laboratorio real
quemando CPU, más lento por naturaleza). Corre
CpuMonitor._evaluate() directamente: CPU debajo/al/encima del umbral,
sostenida vs instantánea, cobertura de ventana, límite de re-alerta.

Ejecutar: python3 tests/heuristic/test_hr06_unit_synthetic.py
"""
import os
import sys

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))

from collections import deque
from cpu_monitor import CpuMonitor

results = []


def check(name, condition):
    results.append((name, condition))
    print(("PASS" if condition else "FAIL"), "-", name)


class FakeCredential:
    pass


sent_alerts = []


def fake_send_alert(credential, payload):
    sent_alerts.append(payload)


import cpu_monitor as cm
cm.send_alert = fake_send_alert  # patch del módulo, no del objeto


# Caso 1: CPU por debajo del umbral todo el tiempo -> no dispara
sent_alerts.clear()
mon = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
now = 1000.0
samples = deque([(now - 9, 50), (now - 6, 55), (now - 3, 60), (now, 65)])
mon._evaluate(1, {"name": "proc.exe"}, samples, now)
check("HR-06 CPU debajo del umbral no dispara", len(sent_alerts) == 0)

# Caso 2: CPU exactamente en el umbral, sostenida toda la ventana -> dispara
sent_alerts.clear()
mon2 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
samples2 = deque([(now - 9, 80), (now - 6, 80), (now - 3, 80), (now, 80)])
mon2._evaluate(2, {"name": "proc.exe"}, samples2, now)
check("HR-06 CPU exactamente en el umbral, sostenida -> dispara", len(sent_alerts) == 1)

# Caso 3: CPU por encima del umbral, sostenida -> dispara
sent_alerts.clear()
mon3 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
samples3 = deque([(now - 9, 95), (now - 6, 92), (now - 3, 90), (now, 93)])
mon3._evaluate(3, {"name": "proc.exe"}, samples3, now)
check("HR-06 CPU encima del umbral, sostenida -> dispara", len(sent_alerts) == 1)

# Caso 4: CPU alta solo instantáneamente (un pico, resto por debajo) -> NO dispara
sent_alerts.clear()
mon4 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
samples4 = deque([(now - 9, 30), (now - 6, 95), (now - 3, 40), (now, 35)])
mon4._evaluate(4, {"name": "proc.exe"}, samples4, now)
check("HR-06 pico instantáneo (no sostenido) no dispara", len(sent_alerts) == 0)

# Caso 5: ventana no cubierta (proceso recién apareció, 1 sola muestra alta) -> NO dispara
sent_alerts.clear()
mon5 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
samples5 = deque([(now, 99)])
mon5._evaluate(5, {"name": "proc.exe"}, samples5, now)
check("HR-06 ventana no cubierta (1 muestra) no dispara", len(sent_alerts) == 0)

# Caso 6: mismo episodio sostenido -- segunda evaluación inmediata del
# mismo PID, todavía sostenido, NO debe volver a alertar (sección 14 de
# la especificación de corrección definitiva, 2026-08-17: "una
# condición sostenida = un episodio", no una alerta por cada muestra).
sent_alerts.clear()
mon6 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
samples6 = deque([(now - 9, 90), (now - 6, 90), (now - 3, 90), (now, 90)])
mon6._evaluate(6, {"name": "proc.exe"}, samples6, now)
mon6._evaluate(6, {"name": "proc.exe"}, samples6, now + 1)  # 1s después, sigue sostenido
check("HR-06 no reenvía alerta mientras el mismo episodio sigue sostenido", len(sent_alerts) == 1)

# Caso 7: recuperación real + nueva superación -> NUEVO episodio, nueva
# alerta (sección 15: "recuperación: CPU < threshold... si vuelve a
# cumplirse: nuevo episodio"). Simula: sostenido (dispara) -> una
# lectura por debajo del umbral (recupera) -> vuelve a estar sostenido
# (dispara de nuevo, episodio distinto).
sent_alerts.clear()
mon7 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
episode_1 = deque([(now - 9, 90), (now - 6, 90), (now - 3, 90), (now, 90)])
mon7._evaluate(7, {"name": "proc.exe"}, episode_1, now)
recovery = deque([(now - 6, 90), (now - 3, 90), (now, 30)])  # última lectura recupera
mon7._evaluate(7, {"name": "proc.exe"}, recovery, now + 1)
episode_2 = deque([(now - 6, 90), (now - 3, 90), (now + 2, 90)])  # vuelve a sostenerse, ventana cubierta de nuevo
mon7._evaluate(7, {"name": "proc.exe"}, episode_2, now + 2)
check("HR-06 recuperación real + nueva superación -> episodio nuevo, alerta nueva", len(sent_alerts) == 2)

# Caso 8 (CPU-01 de la sección 35 de la especificación de corrección
# definitiva, 2026-08-17): PID 0 (System Idle Process en Windows) NUNCA
# debe evaluarse -- ni siquiera debe llegar a tener muestras guardadas.
# Se fabrica un psutil.process_iter() falso con PID 0 (CPU muy alta, a
# propósito, para confirmar que se excluye por PID y no porque su CPU
# fuera baja) más un proceso real normal, y se corre _sample_once()
# completo (no _evaluate() directo, para ejercitar el filtro real).


class FakeProcess:
    def __init__(self, pid, name, cpu):
        self.pid = pid
        self.info = {"pid": pid, "name": name, "exe": None}
        self._cpu = cpu

    def cpu_percent(self, interval=None):
        return self._cpu


sent_alerts.clear()
mon8 = CpuMonitor(FakeCredential(), threshold=80, window_seconds=10)
cm.psutil.process_iter = lambda *a, **kw: iter([
    FakeProcess(0, "System Idle Process", 99.9),
    FakeProcess(1234, "notepad.exe", 10.0),
])
mon8._sample_once()
check("HR-06 PID 0 (System Idle Process) nunca se muestrea", 0 not in mon8._samples)
check("HR-06 un proceso real normal sí se muestrea", 1234 in mon8._samples)
check("HR-06 PID 0 nunca dispara alerta aunque reporte CPU muy alta", len(sent_alerts) == 0)

ok = all(c for _, c in results)
print()
print(f"{sum(1 for _, c in results if c)}/{len(results)} pruebas OK (test_hr06_unit_synthetic.py)")
sys.exit(0 if ok else 1)
