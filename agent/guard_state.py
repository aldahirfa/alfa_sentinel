"""Marcas compartidas entre el agente y su guardián (2026-10-06).

El guardián (guardian.ps1 en Windows, guardian.sh en Linux) aísla el
equipo si el proceso del agente muere sin un cierre normal: en una prueba
real, LockBit terminó el agente ANTES de cifrar, y sin el guardián no había
ni alerta ni aislamiento. Para no confundir un cierre normal con un ataque:

- CLEAN_STOP_FILE: el agente escribe su PID al terminar por su cuenta
  (cualquier salida que pase por Python: fin normal, error al conectar,
  excepción). Una terminación forzada (TerminateProcess, SIGKILL) no deja
  la marca. El guardián de Windows la consulta; el de Linux usa además lo
  que informa systemd.
- KILLED_FILE: la escribe el guardián cuando detecta la terminación. Si no
  pudo avisar al servidor en ese momento, el agente lo hace al volver.
"""

import json
import os
import socket
import threading
import time

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado")
CLEAN_STOP_FILE = os.path.join(STATE_DIR, "detencion_limpia")
KILLED_FILE = os.path.join(STATE_DIR, "agente_terminado.json")

# Latido local (2026-10-06): en una prueba con RanSim el agente quedó
# congelado 27 minutos con el proceso vivo; el guardián no reaccionaba
# porque el proceso no había terminado. Un hilo propio deja la hora en
# PULSE_FILE cada PULSE_INTERVAL_SECONDS: si deja de hacerlo, el guardián de
# Windows reinicia el agente; en Linux se avisa a systemd (WatchdogSec en la
# unidad, ver instalar.sh), que hace lo mismo.
PULSE_FILE = os.path.join(STATE_DIR, "latido")
PULSE_INTERVAL_SECONDS = 10

AGENT_KILLED_RULE_NAME = "Agente Detenido Inesperadamente"


def mark_clean_stop():
    """Se registra con atexit en main.py. Nunca lanza: corre mientras el
    proceso termina."""

    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(CLEAN_STOP_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def start_pulse():
    def run():
        while True:
            try:
                os.makedirs(STATE_DIR, exist_ok=True)
                with open(PULSE_FILE, "w", encoding="utf-8") as f:
                    f.write(str(time.time()))
            except OSError:
                pass
            _notify_systemd_watchdog()
            time.sleep(PULSE_INTERVAL_SECONDS)

    threading.Thread(target=run, name="alfa-latido", daemon=True).start()


def _notify_systemd_watchdog():
    """sd_notify("WATCHDOG=1") sin dependencias. Solo existe NOTIFY_SOCKET
    cuando el agente corre como servicio de systemd con WatchdogSec."""

    address = os.environ.get("NOTIFY_SOCKET")
    if not address or not hasattr(socket, "AF_UNIX"):
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(b"WATCHDOG=1")
    except OSError:
        pass


def clear_clean_stop():
    """Al arrancar: una marca de una ejecución anterior no debe valer para
    esta."""

    try:
        os.remove(CLEAN_STOP_FILE)
    except OSError:
        pass


def pending_killed_report():
    """Datos de la terminación que el guardián no pudo reportar, o None."""

    try:
        with open(KILLED_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("reported"):
        return None
    return data


def forget_killed_report():
    try:
        os.remove(KILLED_FILE)
    except OSError:
        pass


def killed_alert_payload(data):
    detected_at = data.get("detected_at") or "hora desconocida"
    isolation = data.get("isolation") or "sin datos del aislamiento"
    return {
        "title": "Agente detenido de forma inesperada",
        "description": (
            f"El guardián del equipo detectó que el agente fue terminado sin un cierre normal "
            f"({detected_at}). Aislamiento local: {isolation}. Reportado por el agente al volver a "
            f"iniciarse porque el guardián no pudo avisar en ese momento."
        ),
        "matched_rules": [AGENT_KILLED_RULE_NAME],
    }
