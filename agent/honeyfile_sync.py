import threading

from honeyfile_deployer import apply_honeyfile_policy
from file_monitor import watch_extra_directory


# Entre 30 y 60s (sección 7 de la especificación, 2026-08-17, ver
# PENDIENTES.md, "Honeyfiles: despliegue automático, rutas, integridad,
# reconciliación y ejecución en tiempo real"): "polling simple, sin
# WebSockets/SSE/brokers", ni tan frecuente que genere carga
# innecesaria en el servidor, ni tan espaciado que una asignación nueva
# tarde varios minutos en materializarse en un agente ya corriendo.
SYNC_INTERVAL_SECONDS = 45.0


class HoneyfileSyncThread:
    """Hilo en background, independiente del observer de archivos, del
    monitor de CPU, del heartbeat y del motor heurístico (sección 7:
    "no bloqueante, independiente de los demás mecanismos") que vuelve
    a pedir la política de honeyfiles del servidor cada
    SYNC_INTERVAL_SECONDS y aplica lo que haga falta: crear
    asignaciones nuevas (sin esperar a que el agente se reinicie,
    sección 6, obligatoria), y reconciliar las que ya existían (recrear
    si desaparecieron, registrar el hash si cambiaron -- ver
    agent/honeyfile_deployer.py::apply_honeyfile_policy, que hace el
    trabajo real; este hilo solo lo repite a intervalos y conecta el
    resultado con lo que ya está vigilando el agente en memoria).

    Mismo patrón que cpu_monitor.py::CpuMonitor: threading.Event para
    poder frenarlo desde afuera sin usar señales ni threading.Timer
    encadenados, daemon=True para que nunca impida que el proceso
    termine si algo más falla."""

    def __init__(self, credential, honeyfile_monitor, observer, event_handler, watched_roots, watched_extra_dirs):
        self.credential = credential
        self.honeyfile_monitor = honeyfile_monitor
        self.observer = observer
        self.event_handler = event_handler
        self.watched_roots = watched_roots
        self.watched_extra_dirs = watched_extra_dirs
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=SYNC_INTERVAL_SECONDS)

    def _run(self):
        # Espera un ciclo completo antes de la primera sincronización:
        # apply_honeyfile_policy() ya se corrió una vez al arrancar el
        # agente (ver agent/main.py) -- repetirlo de inmediato acá solo
        # duplicaría esa misma llamada sin haber pasado tiempo real.
        while not self._stop_event.wait(SYNC_INTERVAL_SECONDS):
            try:
                self._sync_once()
            except Exception as error:
                # Un fallo puntual (el servidor no respondió esta vez,
                # un honeyfile no se pudo escribir por permisos, etc.)
                # no debe tumbar el hilo -- se registra y se reintenta
                # en el próximo ciclo, mismo criterio que CpuMonitor.
                print(f"⚠ Error sincronizando honeyfiles: {error}")

    def _sync_once(self):

        # Se pasa 'self.honeyfile_monitor' para que cualquier escritura
        # real (creación o reconciliación caso B) quede marcada como
        # actividad interna ANTES de tocar el disco (sección 22/34,
        # 2026-08-17, ver PENDIENTES.md, "Honeyfiles + monitorización
        # completa del endpoint...") -- sin esto, el ciclo periódico de
        # este mismo hilo dispararía HR-03 sobre sus propios honeyfiles.
        watched_paths = apply_honeyfile_policy(self.credential, honeyfile_monitor=self.honeyfile_monitor)

        for file_path in watched_paths:

            # add_known_path() es idempotente (es un set) -- no importa
            # si esta ruta ya se conocía de un ciclo anterior o del
            # arranque del agente, sección 23 ("todas las operaciones
            # de sincronización deben ser idempotentes").
            self.honeyfile_monitor.add_known_path(file_path)

            watch_extra_directory(
                self.observer,
                self.event_handler,
                file_path,
                self.watched_roots,
                self.watched_extra_dirs
            )
