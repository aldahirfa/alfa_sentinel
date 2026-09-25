import argparse
import os
import signal
import sys
import threading
import time

import config
import paths as agent_paths
import transport

from process_monitor import get_running_processes
from file_monitor import start_file_monitor
from client import enroll_agent, authenticate_agent, get_rule_policy
from honeyfile_deployer import apply_honeyfile_policy
from honeyfile_sync import HoneyfileSyncThread, SYNC_INTERVAL_SECONDS
from isolation_sync import IsolationSyncThread, SYNC_INTERVAL_SECONDS as ISOLATION_SYNC_INTERVAL_SECONDS
from cpu_monitor import CpuMonitor
from heartbeat import HeartbeatThread, HEARTBEAT_INTERVAL_SECONDS
from credential import save_credential, load_credential
from system_info import get_system_info


def parse_args():
    parser = argparse.ArgumentParser(description="Agente ALFA-Sentinel")
    parser.add_argument("--enroll", dest="token", default=None, help="Token de enrollment de un solo uso")
    parser.add_argument("--server", dest="server_url", default=None, help="URL base del servidor (ej. https://192.168.81.1:8000)")
    parser.add_argument("--ca", dest="ca_file", default=None, help="Ruta a ca.crt de ALFA-Sentinel (por defecto agent/certs/ca.crt)")
    parser.add_argument("--service", action="store_true", help="Modo servicio: sin consola, registro en logs/agente.log, se detiene con la señal del sistema")
    return parser.parse_args()


LOG_MAX_BYTES = 10 * 1024 * 1024


def redirect_output_to_log():
    """Como servicio no hay consola: todo lo que el agente imprime va a
    logs/agente.log (se rota al superar 10 MB, se conserva uno anterior)."""

    log_dir = os.path.join(config.AGENT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "agente.log")
    if os.path.exists(log_file) and os.path.getsize(log_file) > LOG_MAX_BYTES:
        os.replace(log_file, log_file + ".1")
    stream = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    print(f"\n===== Agente iniciado como servicio: {time.strftime('%Y-%m-%d %H:%M:%S')} =====")


def wait_until_stopped():
    """Como servicio: espera hasta que el sistema pida detenerlo
    (systemctl stop, fin de la tarea en Windows, apagado del equipo)."""

    stop = threading.Event()
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None), getattr(signal, "SIGBREAK", None)):
        if sig is not None:
            signal.signal(sig, lambda *_: stop.set())
    while not stop.wait(1):
        pass


def apply_cli_overrides(args):
    if args.server_url:
        config.SERVER_URL = args.server_url.rstrip("/")
        config.ENROLLMENT_URL = f"{config.SERVER_URL}/enrollment"
        config.AUTHENTICATION_URL = f"{config.SERVER_URL}/agent/test"
        config.HEARTBEAT_URL = f"{config.SERVER_URL}/agent/heartbeat"
        config.EVENTS_URL = f"{config.SERVER_URL}/agent/events"
        config.ALERTS_URL = f"{config.SERVER_URL}/agent/alerts"
        config.RULE_POLICY_URL = f"{config.SERVER_URL}/agent/rule-policy"
        config.HONEYFILE_POLICY_URL = f"{config.SERVER_URL}/agent/honeyfile-policy"
        config.HONEYFILE_POLICY_REPORT_URL = f"{config.SERVER_URL}/agent/honeyfile-policy/report"
        config.ISOLATION_STATUS_URL = f"{config.SERVER_URL}/agent/isolation-status"
        config.ISOLATION_STATUS_REPORT_URL = f"{config.SERVER_URL}/agent/isolation-status/report"
        print(f"Servidor (--server): {config.SERVER_URL}")

    if args.ca_file:
        config.CA_CERT_FILE = args.ca_file
        print(f"CA de confianza (--ca): {transport.ca_file_path()}")

    if args.token:
        config.ENROLLMENT_TOKEN = args.token
        print("Token de enrollment (--enroll): tomado de la línea de comandos.")


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.service:
        redirect_output_to_log()
    print("Agente iniciado")
    apply_cli_overrides(cli_args)

    # Antes de mandar nada (ni el token de enrollment ni la credencial):
    # confirmar que el canal hacia el servidor es HTTPS con la CA propia.
    try:
        transport_mode = transport.validate_server_url()
    except transport.InsecureServerURLError as error:
        print(f"⚠ {error}")
        raise SystemExit(1)
    if transport_mode == "https":
        print(f"Canal seguro: HTTPS con CA propia ({transport.ca_file_path()})")
    else:
        print("⚠ Canal SIN cifrar hacia 127.0.0.1 (solo pruebas locales).")

    system_info = get_system_info()

    print("Información del equipo:")
    print(system_info)

    existing_credential = load_credential()

    if existing_credential:
        print("El agente ya está registrado.")
        print("Credencial encontrada localmente.")

        response = authenticate_agent(existing_credential)

        if response is None:
            print("No se pudo contactar al servidor para autenticar. Deteniendo.")
            raise SystemExit(1)

        print("Respuesta de autenticación:")
        print(response.json())

        if response.status_code != 200:
            print(
                "El servidor rechazó la credencial guardada (¿se recreó la base de datos, "
                "o se revocó el agente?). Borra agent_credential.json y volvé a correr con "
                "--enroll <token> --server <url> para registrar el agente de nuevo."
            )
            raise SystemExit(1)

        print()
        print(f"Iniciando heartbeat periódico (cada {HEARTBEAT_INTERVAL_SECONDS}s)...")
        heartbeat_sync = HeartbeatThread(existing_credential).start()

        print()
        print("Procesos en ejecución:")

        processes = get_running_processes()
        for process in processes:
            print(
                f"PID: {process['pid']} | "
                f"Nombre: {process['name']} | "
                f"Ruta: {process['path']} | "
                f"Usuario: {process['username']}"
            )

        print()
        print("Resolviendo carpetas del endpoint a monitorizar...")

        monitored_roots = agent_paths.get_monitored_roots()
        for root in monitored_roots:
            print(f"  {root}")

        print()
        print("Sincronizando honeyfiles...")
        watched_honeyfile_paths = apply_honeyfile_policy(existing_credential)

        print()
        print("Sincronizando reglas heurísticas...")

        rule_policy_response = get_rule_policy(existing_credential)

        if rule_policy_response is not None and rule_policy_response.status_code == 200:
            rule_policy = rule_policy_response.json().get("rules", [])
            print(f"{len(rule_policy)} regla(s) activa(s) recibida(s) del servidor (política efectiva de este endpoint).")
        else:
            rule_policy = None
            print("No se pudo obtener la política de reglas. Se usan los valores por defecto.")

        print()
        print("Iniciando monitor de archivos...")

        observer, analyzer, honeyfile_monitor, file_event_handler, watched_roots, watched_extra_dirs = start_file_monitor(
            monitored_roots, existing_credential, watched_honeyfile_paths, rule_policy
        )

        loaded_rule_names = sorted(analyzer.rules.keys())
        print(f"{len(loaded_rule_names)} regla(s) cargada(s) en el motor heurístico y disponibles para evaluación:")
        for name in loaded_rule_names:
            cfg = analyzer.rules[name]
            window = cfg.get("window_seconds")
            window_label = f"{window}s" if window is not None else "no aplica"
            print(f"  - {name} (umbral {cfg['threshold']}, ventana {window_label})")

        if rule_policy is not None:
            server_only = sorted({r["name"] for r in rule_policy} - set(loaded_rule_names))
            if server_only:
                print(
                    f"({len(server_only)} regla(s) más las calcula el SERVIDOR a partir de las reglas que "
                    f"el agente sí reporta, no el agente localmente: {', '.join(server_only)}.)"
                )

        print("Monitor activo.")
        if agent_paths.get_env_mode() == "production":
            print("El agente está vigilando las carpetas reales del usuario y las zonas ALFA_ARCHIVOS desplegadas.")
        else:
            print("Modifica archivos dentro de agent/test_endpoint/<Carpeta> (o agent/honeyfiles) para probarlo.")

        cpu_rule_cfg = analyzer.rules.get("Consumo CPU Elevado")
        cpu_monitor = None

        if cpu_rule_cfg:
            print()
            print(
                f"Iniciando monitor de CPU (umbral {cpu_rule_cfg['threshold']}%, "
                f"ventana {cpu_rule_cfg['window_seconds']}s)..."
            )
            cpu_monitor = CpuMonitor(
                existing_credential,
                cpu_rule_cfg["threshold"],
                cpu_rule_cfg["window_seconds"]
            ).start()
        else:
            print()
            print("Consumo CPU Elevado (HR-06) no está activa para este endpoint -- monitor de CPU no iniciado.")

        print()
        print(f"Iniciando sincronización periódica de honeyfiles (cada {int(SYNC_INTERVAL_SECONDS)}s)...")

        honeyfile_sync = HoneyfileSyncThread(
            existing_credential,
            honeyfile_monitor,
            observer,
            file_event_handler,
            watched_roots,
            watched_extra_dirs
        ).start()

        print()
        print(f"Iniciando sincronización de aislamiento (cada {int(ISOLATION_SYNC_INTERVAL_SECONDS)}s)...")
        isolation_sync = IsolationSyncThread(existing_credential).start()

        try:
            if cli_args.service:
                wait_until_stopped()
            else:
                input("Presiona ENTER para detener el monitor...")
        finally:
            isolation_sync.stop()
            honeyfile_sync.stop()
            heartbeat_sync.stop()
            observer.stop()
            observer.join()

            if cpu_monitor is not None:
                cpu_monitor.stop()

    else:
        print("No existe una credencial.")
        print("Realizando enrollment...")

        response = enroll_agent(system_info)

        # Código de salida para el instalador: 0 = registrado, 1 = no.
        if response is None:
            print("No se pudo contactar al servidor para registrar el agente.")
            raise SystemExit(1)

        if response.status_code == 200:
            credential = response.json()["credential"]
            save_credential(credential)
            print("Agente registrado correctamente.")
            print("Credencial almacenada localmente.")
        else:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text
            print(f"El servidor rechazó el registro: {detail}")
            raise SystemExit(1)
