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

# PID reservado del "System Idle Process" en Windows -- sección 12 de
# la especificación de corrección definitiva (2026-08-17, ver
# PENDIENTES.md): NO es un proceso real de un usuario/atacante, es la
# contabilidad del propio SO para el tiempo de CPU ocioso. psutil lo
# expone igual que cualquier otro proceso en process_iter(), así que
# hay que excluirlo a propósito -- si no, un equipo mayormente ocioso
# podría (según cómo Windows reporte ese PID puntual) generar
# "Consumo CPU elevado -- System Idle Process", que no tiene ningún
# sentido como indicio de ransomware. Se excluye de la evaluación
# completa: nunca entra a matched_rules, nunca genera una alerta.
IDLE_PROCESS_PID = 0


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
    módulo no toca ni conoce.

    QUÉ REPRESENTA EL UMBRAL (sección 13 de la especificación de
    corrección definitiva, 2026-08-17 -- auditado, no cambiado sin
    verificar primero el comportamiento real): 'threshold' se compara
    directo contra psutil.Process.cpu_percent(), que en psutil NO se
    normaliza contra la capacidad total del equipo -- está expresado en
    la misma convención que el 'top' de Unix: 100% representa UN núcleo
    lógico completo. Un proceso multi-hilo que efectivamente usa varios
    núcleos puede reportar más de 100% (hasta N*100% en una máquina de
    N núcleos lógicos) -- esto es un comportamiento normal y documentado
    de psutil, no un bug. Por lo tanto 'threshold=80' significa
    literalmente "al menos el 80% de la capacidad de UN núcleo lógico,
    sostenido durante toda la ventana" -- no "80% de la máquina
    completa". Se documenta acá (y en la descripción de la regla en
    database/schema.sql) para que quien lea una alerta de HR-06 sepa
    exactamente qué está midiendo el número; el valor del umbral en sí
    NO se tocó, tal como pidió la especificación ("no cambiar la
    lógica sin verificar primero")."""

    def __init__(self, credential, threshold, window_seconds):
        self.credential = credential
        self.threshold = threshold
        self.window_seconds = window_seconds or 10
        self._samples = {}          # pid -> deque[(ts, cpu_percent)]
        self._episode_active = {}   # pid -> bool (ver _evaluate)
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        # "Prime": la primera llamada a cpu_percent(interval=None) de
        # un proceso siempre devuelve 0.0 -- psutil recién puede medir
        # un delta real a partir de la SEGUNDA llamada. Se descarta a
        # propósito para no contar un falso "0% sostenido" como dato.
        for process in psutil.process_iter():
            if process.pid == IDLE_PROCESS_PID:
                continue
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
        seen_pids = set()

        for process in psutil.process_iter(["pid", "name", "exe"]):

            pid = process.pid

            # Sección 12: nunca evaluar HR-06 para el proceso ocioso
            # del SO -- ni siquiera se le toma la muestra.
            if pid == IDLE_PROCESS_PID:
                continue

            try:
                cpu = process.cpu_percent(interval=None)
                info = process.info
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

            seen_pids.add(pid)

            samples = self._samples.setdefault(pid, deque())
            samples.append((now, cpu))

            while samples and now - samples[0][0] > self.window_seconds:
                samples.popleft()

            self._evaluate(pid, info, samples, now)

        # Higiene de memoria: un agente corre indefinidamente, así que
        # sin esto self._samples/_episode_active crecerían para
        # siempre con cada PID que alguna vez existió. Se podan los que
        # no aparecieron en esta muestra (proceso terminado) -- no hay
        # nada que "cerrar" para ellos, simplemente dejan de existir.
        for stale_pid in set(self._samples) - seen_pids:
            del self._samples[stale_pid]
            self._episode_active.pop(stale_pid, None)

    def _evaluate(self, pid, info, samples, now):
        """Condición SOSTENIDA con episodio real (secciones 12/14/15 de
        la especificación de corrección definitiva, 2026-08-17 -- ver
        PENDIENTES.md):

        - ACTIVACIÓN: hace falta que (a) haya muestras cubriendo la
          ventana completa (un proceso recién aparecido, con una sola
          muestra alta, todavía no tiene "ventana completa" -- no
          dispara) y (b) TODAS las muestras dentro de la ventana estén
          en o por encima del umbral. Recién ahí se manda UNA alerta,
          y el episodio para ese PID queda marcado 'activo'.
        - MIENTRAS el episodio siga activo, NO se manda una alerta
          nueva por cada muestra adicional que siga sosteniendo la
          condición -- "CPU > threshold durante 60s" tiene que ser UN
          episodio, no una alerta cada ventana de muestreo (sección 14).
        - RECUPERACIÓN: apenas la muestra MÁS RECIENTE cae por debajo
          del umbral, el episodio se da por terminado (sección 15:
          "activación: CPU >= threshold; recuperación: CPU <
          threshold" -- sin hysteresis, tal como quedó definido; no se
          exige que la recuperación esté "sostenida" para contar,
          alcanza con una lectura real por debajo del umbral).
        - Si vuelve a cumplirse la condición después de una
          recuperación real, es un episodio NUEVO -- se manda una
          alerta nueva (que el servidor decidirá si cae en el mismo
          episodio de alertas o abre uno nuevo, según
          EPISODE_WINDOW_SECONDS deslizante de report_alert)."""

        if not samples:
            return

        latest_cpu = samples[-1][1]

        # Recuperación: se evalúa PRIMERO y de forma independiente de
        # "sustained" de abajo -- una sola lectura reciente por debajo
        # del umbral alcanza para cerrar el episodio, sin importar qué
        # haya en el resto de la ventana todavía.
        if latest_cpu < self.threshold:
            self._episode_active[pid] = False
            return

        covers_window = (samples[-1][0] - samples[0][0]) >= self.window_seconds * 0.8
        sustained = all(cpu >= self.threshold for _, cpu in samples)

        if not (covers_window and sustained):
            return

        if self._episode_active.get(pid, False):
            # Ya se avisó por este mismo episodio sostenido -- no
            # volver a mandar la misma alerta en cada muestra.
            return

        self._episode_active[pid] = True

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
                    f"(base: 100% = un núcleo lógico completo, ver documentación de HR-06) "
                    f"durante al menos {self.window_seconds}s (promedio de la ventana: {avg_cpu:.1f}%)."
                ),
                "matched_rules": [RULE_NAME],
            }
        )
