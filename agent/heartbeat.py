import threading
import traceback

from client import send_heartbeat
from system_info import get_system_info


HEARTBEAT_INTERVAL_SECONDS = 30


class HeartbeatThread:
    """Mantiene viva la presencia del agente y refresca su inventario.

    El primer heartbeat se envía inmediatamente al arrancar el hilo; los
    siguientes se envían cada HEARTBEAT_INTERVAL_SECONDS. El hilo no mata
    al agente si hay un fallo temporal de red: el siguiente ciclo vuelve a
    intentarlo.
    """

    def __init__(self, credential, interval_seconds=HEARTBEAT_INTERVAL_SECONDS):
        self.credential = credential
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop_event.is_set():
            # Corregido 2026-10-06: sin este try, un solo error inesperado
            # mataba el hilo en silencio y el resto del agente seguía
            # funcionando -- la consola mostraba "Última conexión: hace 1 h"
            # con eventos de hace minutos (pasó en DESKTOP-5A3JTJG). Los
            # demás hilos (honeyfiles, aislamiento, CPU) ya lo tenían.
            try:
                self._send_once()
            except Exception:
                print("⚠ Error enviando el heartbeat (se reintenta en el próximo ciclo):")
                traceback.print_exc()

            if self._stop_event.wait(self.interval_seconds):
                break

    def _send_once(self):
        system_info = get_system_info()
        response = send_heartbeat(self.credential, system_info)

        if response is not None and response.status_code == 200:
            data = response.json()
            print(
                "Heartbeat enviado: "
                f"agent_id={data.get('agent_id')} | "
                f"IP={system_info.get('ip_address') or 'no disponible'} | "
                f"SO={system_info.get('os')} {system_info.get('os_version') or ''}".rstrip()
            )

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return self

        self._thread = threading.Thread(
            target=self._run,
            name="alfa-sentinel-heartbeat",
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
