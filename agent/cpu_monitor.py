import threading
from collections import deque
from time import time

import psutil

from client import send_alert


RULE_NAME = "Consumo CPU Elevado"

# Cada cuánto se toma una muestra de CPU por proceso. Sección 13 de la
# especificación de implementación final: "no ejecutar consultas
# excesivamente frecuentes... no hacer polling innecesariamente
# agresivo de todos los procesos". 2 segundos es razonable para una
# ventana típica de 10s (da ~5 muestras por ventana) sin generar carga
# constante.
SAMPLE_INTERVAL_SECONDS = 2.0

# No re-enviar una alerta en cada muestra mientras la condición siga
# sostenida -- se espera al menos una ventana completa entre avisos
# del MISMO proceso.
MIN_SECONDS_BETWEEN_ALERTS = 10.0


class CpuMonitor:
    """Hilo en background que muestrea CPU por proceso a intervalos
    regulares y evalúa HR-06 (Consumo CPU Elevado) -- 2026-08-16, ver
    PENDIENTES.md. Corre en su propio hilo (igual que watchdog.Observer,
    que ya corre en el suyo) porque es la única regla que necesita
    polling activo en vez de reaccionar a un evento -- el resto del
    agente sigue reaccionando a eventos de archivo, esto no le agrega
    ningún bloqueo.

    IMPORTANTE (sección 12 de la especificación): esto es una señal
    SECUNDARIA. Nunca decide CRÍTICO ni aislamiento por sí sola -- eso
    es responsabilidad exclusiva del servidor (heuristic_rules.weight
    de esta regla es bajo, 5, a propósito) y de la condición de
    incidente/aislamiento en server/main.py::report_alert, que este
    módulo no toca ni conoce."""

    def __init__(self, credential, threshold, window_seconds):
        self.credential = credential
        self.threshold = threshold
        self.window_seconds = window_seconds or 10
        self._samples = {}          # pid -> deque[(ts, cpu_percent)]
        self._last_alert_at = {}    # pid -> timestamp del último aviso
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        # "Prime": la primera llamada a cpu_percent(interval=None) de
        # un proceso siempre devuelve 0.0 -- psutil recién puede medir
        # un delta real a partir de la SEGUNDA llamada. Se descarta a
        # propósito para no contar un falso "0% sostenido" como dato.
        for process in psutil.process_iter():
            try:
                process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=SAMPLE_INTERVAL_SECONDS * 3)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._sample_once()
            except Exception as error:
                # Un error de muestreo puntual (proceso que
                # desapareció justo en el medio, etc.) no debe tumbar
                # el hilo entero -- se registra y se sigue en la
                # próxima muestra.
                print(f"⚠ Error muestreando CPU por proceso: {error}")
            self._stop_event.wait(SAMPLE_INTERVAL_SECONDS)

    def _sample_once(self):
        now = time()

        for process in psutil.process_iter(["pid", "name", "exe"]):

            try:
                cpu = process.cpu_percent(interval=None)
                info = process.info
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

            pid = info["pid"]

            samples = self._samples.setdefault(pid, deque())
            samples.append((now, cpu))

            while samples and now - samples[0][0] > self.window_seconds:
                samples.popleft()

            self._evaluate(pid, info, samples, now)

    def _evaluate(self, pid, info, samples, now):
        """Condición SOSTENIDA (sección 12/28 de la especificación):
        no alcanza con una lectura instantánea alta. Se exige que (a)
        haya muestras cubriendo la ventana completa (un proceso recién
        aparecido, con una sola muestra alta, todavía no tiene
        "ventana completa" -- no dispara) y (b) TODAS las muestras
        dentro de la ventana estén en o por encima del umbral (un pico
        que baja en la siguiente muestra rompe la condición, tal como
        pide el caso de prueba "CPU alta solamente durante un
        instante" de la sección 28)."""

        if not samples:
            return

        covers_window = (samples[-1][0] - samples[0][0]) >= self.window_seconds * 0.8
        sustained = all(cpu >= self.threshold for _, cpu in samples)

        if not (covers_window and sustained):
            return

        last_alert = self._last_alert_at.get(pid, 0.0)
        if now - last_alert < MIN_SECONDS_BETWEEN_ALERTS:
            return

        self._last_alert_at[pid] = now

        process_name = info.get("name") or f"PID {pid}"
        avg_cpu = sum(cpu for _, cpu in samples) / len(samples)

        print()
        print(f"⚠ CONSUMO DE CPU SOSTENIDO -- PID {pid} ({process_name}): {avg_cpu:.1f}% promedio")
        print()

        send_alert(
            self.credential,
            {
                "title": f"Consumo de CPU elevado -- {process_name}",
                "description": (
                    f"Proceso PID {pid} ({process_name}) sostuvo un uso de CPU >= {self.threshold}% "
                    f"durante al menos {self.window_seconds}s (promedio de la ventana: {avg_cpu:.1f}%)."
                ),
                "matched_rules": [RULE_NAME],
            }
        )
