import threading

from client import get_isolation_status, report_isolation_status
from isolation_executor import execute_isolation, execute_release


# Sección 28 de la especificación de corrección definitiva
# (2026-08-17, ver PENDIENTES.md): el aislamiento es una acción de
# contención de seguridad, no una conveniencia como la sincronización
# de honeyfiles (45s) -- se consulta con más frecuencia para que una
# orden real no quede pendiente varios minutos sin ejecutarse.
SYNC_INTERVAL_SECONDS = 15.0


class IsolationSyncThread:
    """Hilo en background, independiente del observer de archivos, del
    monitor de CPU, del heartbeat, del motor heurístico y de la
    sincronización de honeyfiles (mismo criterio de independencia que
    honeyfile_sync.py) que pregunta periódicamente si el servidor
    ordenó aislar este endpoint (GET /agent/isolation-status), y si
    hay una orden pendiente, la ejecuta (agent/isolation_executor.py) y
    confirma el resultado real (POST /agent/isolation-status/report).

    Mismo patrón que CpuMonitor/HoneyfileSyncThread: threading.Event
    para poder frenarlo desde afuera, daemon=True para que nunca
    impida que el proceso termine si algo más falla."""

    def __init__(self, credential):
        self.credential = credential
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
        # A diferencia de HoneyfileSyncThread, acá SÍ conviene revisar
        # de inmediato al arrancar (no esperar el primer intervalo
        # completo) -- si el agente se reinició mientras había una
        # orden pendiente, no tiene sentido dejarla sin ejecutar 15s
        # más de lo necesario.
        while not self._stop_event.is_set():
            try:
                self._sync_once()
            except Exception as error:
                # Un fallo puntual (el servidor no respondió esta vez)
                # no debe tumbar el hilo -- se reintenta en el próximo
                # ciclo, mismo criterio que el resto de los hilos del
                # agente.
                print(f"⚠ Error consultando estado de aislamiento: {error}")
            self._stop_event.wait(SYNC_INTERVAL_SECONDS)

    def _sync_once(self):

        response = get_isolation_status(self.credential)

        if response is None or response.status_code != 200:
            return

        pending = response.json().get("pending")

        if pending is None:
            return

        isolation_id = pending["isolation_id"]
        isolation_type = pending["isolation_type"]
        reason = pending.get("reason") or "(sin motivo registrado)"
        # 'action' distingue AISLAR de LIBERAR sobre la MISMA orden
        # pendiente (sección 18 de la especificación de host, 2026-08-17,
        # ver PENDIENTES.md, "Aislamiento de host -- modo development,
        # laboratorio y producción": "UNISOLATE" usa exactamente el
        # mismo mecanismo de polling/ejecución/confirmación que aislar,
        # solo cambia qué hace el ejecutor). Default 'ISOLATE' por
        # compatibilidad si el servidor todavía no manda el campo.
        action = pending.get("action", "ISOLATE")

        if action == "RELEASE":
            print()
            print("⚠ ORDEN DE LIBERACIÓN DE AISLAMIENTO RECIBIDA")
            print(f"  Tipo: {isolation_type}")
            print(f"  Motivo: {reason}")
            print()

            success, result_message = execute_release(isolation_type)
            status = "RELEASED" if success else "RELEASE_FAILED"

            print(f"{'✓' if success else '✗'} Resultado de la liberación: {status}")
            print(f"  {result_message}")
            print()

            report_isolation_status(self.credential, isolation_id, status, result_message)
            return

        print()
        print("⚠ ORDEN DE AISLAMIENTO RECIBIDA")
        print(f"  Tipo: {isolation_type}")
        print(f"  Motivo: {reason}")
        print()

        success, result_message = execute_isolation(isolation_type)

        status = "EXECUTED" if success else "ISOLATION_FAILED"

        print(f"{'✓' if success else '✗'} Resultado del aislamiento: {status}")
        print(f"  {result_message}")
        print()

        report_isolation_status(self.credential, isolation_id, status, result_message)
