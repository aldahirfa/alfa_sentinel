import argparse
import platform
import socket

import config

import paths as agent_paths

from process_monitor import get_running_processes

from file_monitor import start_file_monitor

from client import (
    enroll_agent,
    authenticate_agent,
    send_heartbeat,
    get_rule_policy
)

from honeyfile_deployer import apply_honeyfile_policy

from honeyfile_sync import HoneyfileSyncThread, SYNC_INTERVAL_SECONDS

from isolation_sync import IsolationSyncThread, SYNC_INTERVAL_SECONDS as ISOLATION_SYNC_INTERVAL_SECONDS

from cpu_monitor import CpuMonitor

from credential import (
    save_credential,
    load_credential
)

from config import AGENT_VERSION


def parse_args():
    """--enroll y --server existen porque el modal de "Registrar Nuevo
    Agente" en Endpoints genera un comando como
        python agent/main.py --enroll <TOKEN> --server http://host:8000
    y antes este script no leía sys.argv en absoluto -- ese comando no
    hacía nada distinto de correr sin argumentos, usando el token viejo
    hardcodeado en config.py. Si se pasan, pisan config.ENROLLMENT_TOKEN
    y las URLs derivadas de config.SERVER_URL antes de intentar el
    enrollment."""

    parser = argparse.ArgumentParser(description="Agente ALFA-Sentinel")
    parser.add_argument("--enroll", dest="token", default=None, help="Token de enrollment de un solo uso")
    parser.add_argument("--server", dest="server_url", default=None, help="URL base del servidor (ej. http://127.0.0.1:8000)")
    return parser.parse_args()


def apply_cli_overrides(args):

    if args.server_url:
        config.SERVER_URL = args.server_url
        config.ENROLLMENT_URL = f"{config.SERVER_URL}/enrollment"
        config.AUTHENTICATION_URL = f"{config.SERVER_URL}/agent/test"
        config.HEARTBEAT_URL = f"{config.SERVER_URL}/agent/heartbeat"
        config.EVENTS_URL = f"{config.SERVER_URL}/agent/events"
        config.ALERTS_URL = f"{config.SERVER_URL}/agent/alerts"
        config.RULE_POLICY_URL = f"{config.SERVER_URL}/agent/rule-policy"
        # HONEYFILE_POLICY_URL/HONEYFILE_POLICY_REPORT_URL no se
        # pisaban acá -- gap preexistente, no relacionado con esto: si
        # se usaba --server apuntando a otro host, la sincronización de
        # honeyfiles seguía yendo al SERVER_URL original de config.py.
        # Se corrige de paso, mismo criterio que las URLs de arriba.
        config.HONEYFILE_POLICY_URL = f"{config.SERVER_URL}/agent/honeyfile-policy"
        config.HONEYFILE_POLICY_REPORT_URL = f"{config.SERVER_URL}/agent/honeyfile-policy/report"
        # ISOLATION_STATUS_URL/ISOLATION_STATUS_REPORT_URL (2026-08-17,
        # ver PENDIENTES.md) -- mismo gap que ya se había corregido para
        # las URLs de honeyfiles arriba: si se pisan acá desde el
        # arranque, no hace falta acordarse de nuevo cada vez que se
        # agregue una URL nueva.
        config.ISOLATION_STATUS_URL = f"{config.SERVER_URL}/agent/isolation-status"
        config.ISOLATION_STATUS_REPORT_URL = f"{config.SERVER_URL}/agent/isolation-status/report"
        print(f"Servidor (--server): {config.SERVER_URL}")

    if args.token:
        config.ENROLLMENT_TOKEN = args.token
        print("Token de enrollment (--enroll): tomado de la línea de comandos.")


def get_system_info():

    # "architecture" (platform.machine()) se dejó de mandar: la nueva
    # tabla 'endpoints' no tiene una columna para eso (ver
    # database/schema.sql). Si en algún momento se vuelve a necesitar,
    # el dato se sigue pudiendo leer localmente con platform.machine(),
    # pero hoy no tiene destino en la base.
    return {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "agent_version": AGENT_VERSION
    }


if __name__ == "__main__":

    print("Agente iniciado")

    cli_args = parse_args()
    apply_cli_overrides(cli_args)

    system_info = get_system_info()

    print("Información del equipo:")
    print(system_info)

    existing_credential = load_credential()

    if existing_credential:

        print("El agente ya está registrado.")
        print("Credencial encontrada localmente.")

        # Autenticación. Antes, si esto fallaba (401 por credencial
        # revocada/de otra base, o error de red), el script imprimía
        # el error y seguía igual hasta "Monitor activo" -- mandando
        # eventos/alertas que el servidor iba a rechazar uno por uno,
        # sin que nada de eso apareciera nunca en la base. Ahora se
        # frena acá si la autenticación no salió bien.

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

        # Heartbeat

        print("Enviando heartbeat...")

        heartbeat_response = send_heartbeat(existing_credential)

        if heartbeat_response is not None:

            print("Respuesta del heartbeat:")
            print(heartbeat_response.json())

        # Procesos

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

        # Carpetas globales del endpoint (2026-08-17, ver PENDIENTES.md,
        # "Honeyfiles + monitorización completa del endpoint..."):
        # Documents/Desktop/Downloads/Pictures/Videos/Music (reales en
        # producción, de prueba dedicadas en desarrollo) -- se resuelven
        # y se crean ANTES de pedir la política de honeyfiles (sección
        # 14: "3. obtener política; 4. crear ALFA_ARCHIVOS..."),
        # porque ALFA_ARCHIVOS vive anidado dentro de una de estas.

        print()
        print("Resolviendo carpetas del endpoint a monitorizar...")

        monitored_roots = agent_paths.get_monitored_roots()

        for root in monitored_roots:
            print(f"  {root}")

        # Honeyfiles por plantilla: pide al servidor qué debería crear
        # o ya tiene creado (GET /agent/honeyfile-policy), escribe lo
        # que falte y lo reporta. Se hace antes de levantar el monitor
        # para poder decirle qué carpetas vigilar además de las de arriba.

        print()
        print("Sincronizando honeyfiles...")

        watched_honeyfile_paths = apply_honeyfile_policy(existing_credential)

        # Reglas heurísticas: pide al servidor peso/umbral/ventana
        # reales de cada regla activa (GET /agent/rule-policy), mismo
        # patrón que la política de honeyfiles arriba. Si el pedido
        # falla, sigue con los valores por defecto -- no se frena el
        # agente por un problema de red (ver FileActivityAnalyzer.from_policy).

        print()
        print("Sincronizando reglas heurísticas...")

        rule_policy_response = get_rule_policy(existing_credential)

        if rule_policy_response is not None and rule_policy_response.status_code == 200:
            rule_policy = rule_policy_response.json().get("rules", [])
            print(f"{len(rule_policy)} regla(s) activa(s) recibida(s) del servidor (política efectiva de este endpoint).")
        else:
            # None, NO lista vacía -- distingue "no se pudo pedir" (folback
            # completo a los valores por defecto) de "el servidor
            # contestó que acá no hay ninguna regla activa" (ver
            # FileActivityAnalyzer.from_policy).
            rule_policy = None
            print("No se pudo obtener la política de reglas. Se usan los valores por defecto.")

        # Monitor de archivos

        print()
        print("Iniciando monitor de archivos...")

        observer, analyzer, honeyfile_monitor, file_event_handler, watched_roots, watched_extra_dirs = start_file_monitor(
            monitored_roots, existing_credential, watched_honeyfile_paths, rule_policy
        )

        # Diagnóstico de arranque (2026-08-18, ver PENDIENTES.md, "Revisión
        # y corrección integral de ALFA-Sentinel", problema A): antes solo
        # se imprimía "N regla(s) activa(s) recibida(s) del servidor" (la
        # respuesta CRUDA de GET /agent/rule-policy, línea de arriba) y
        # nunca se decía cuántas de esas quedaron REALMENTE cargadas en
        # 'analyzer.rules' -- el diccionario que usa FileActivityAnalyzer
        # para evaluar cada evento. Eso generaba una confusión real: el
        # servidor puede reportar 12 reglas activas (incluye "Correlacion
        # Multiples Indicadores", HR-12) pero el agente solo evalúa 11 de
        # esas -- la 12ª es una bonificación de score que calcula el
        # SERVIDOR sobre reglas YA vinculadas a una alerta (ver
        # heuristic_engine.RULE_NAMES y report_alert() en server/main.py),
        # nunca algo que el agente pueda "detectar" en un evento de
        # archivo. No es una regla perdida ni un bug -- es una regla que
        # nunca debió evaluar el agente. Este log lo deja explícito para
        # que no se confunda con "Reglas activas: ninguna" (ver
        # file_monitor.py, que es el conteo de coincidencias de UN evento
        # puntual, no de cuántas reglas hay cargadas).
        loaded_rule_names = sorted(analyzer.rules.keys())
        print(f"{len(loaded_rule_names)} regla(s) cargada(s) en el motor heurístico y disponibles para evaluación:")
        for name in loaded_rule_names:
            cfg = analyzer.rules[name]
            print(f"  - {name} (umbral {cfg['threshold']}, ventana {cfg['window_seconds']}s)")

        if rule_policy is not None:
            server_only = sorted({r["name"] for r in rule_policy} - set(loaded_rule_names))
            if server_only:
                print(
                    f"({len(server_only)} regla(s) más las calcula el SERVIDOR a partir de las reglas que "
                    f"el agente sí reporta, no el agente localmente: {', '.join(server_only)}.)"
                )

        print("Monitor activo.")
        print("Modifica archivos dentro de agent/test_endpoint/<Carpeta> (o agent/honeyfiles) para probarlo.")

        # Monitor de CPU por proceso (HR-06, 2026-08-16 -- ver
        # PENDIENTES.md). Corre en su propio hilo, independiente del
        # observer de archivos -- se arranca solo si la política
        # EFECTIVA de este agente incluye la regla activa (si el
        # servidor no la mandó -- desactivada global o por override de
        # agent_rule para este endpoint puntual -- no tiene sentido
        # gastar ciclos muestreando CPU para una regla que el servidor
        # va a ignorar de todas formas).
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

        # Sincronización periódica de honeyfiles (2026-08-17, ver
        # PENDIENTES.md, "Honeyfiles: despliegue automático, rutas,
        # integridad, reconciliación y ejecución en tiempo real").
        # Independiente del observer/CPU/heartbeat/motor heurístico
        # (sección 7) -- si el admin asigna un honeyfile nuevo, o si
        # uno existente se borra o se modifica, este agente lo detecta
        # sin que haga falta reiniciarlo (sección 6, obligatoria).
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

        # Aislamiento real (2026-08-17, ver PENDIENTES.md, "Corrección
        # definitiva del motor heurístico..."). Independiente del resto
        # (mismo criterio que HoneyfileSyncThread) -- si el servidor
        # determina que corresponde aislar este endpoint, este hilo lo
        # recoge y lo ejecuta sin que el resto del agente tenga que
        # saber nada al respecto.
        print()
        print(f"Iniciando sincronización de aislamiento (cada {int(ISOLATION_SYNC_INTERVAL_SECONDS)}s)...")

        isolation_sync = IsolationSyncThread(existing_credential).start()

        input("Presiona ENTER para detener el monitor...")

        isolation_sync.stop()

        honeyfile_sync.stop()

        observer.stop()
        observer.join()

        if cpu_monitor is not None:
            cpu_monitor.stop()

    else:

        print("No existe una credencial.")
        print("Realizando enrollment...")

        response = enroll_agent(system_info)

        if response is not None:

            print("Respuesta del servidor:")
            print(response.json())

            if response.status_code == 200:

                data = response.json()

                credential = data["credential"]

                save_credential(credential)

                print("Agente registrado correctamente.")
                print("Credencial almacenada localmente.")

            else:

                print("El servidor rechazó el enrollment.")
