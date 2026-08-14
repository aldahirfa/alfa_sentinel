import argparse
import platform
import socket

import config

from process_monitor import get_running_processes

from file_monitor import start_file_monitor

from client import (
    enroll_agent,
    authenticate_agent,
    send_heartbeat,
    get_rule_policy
)

from honeyfile_deployer import apply_honeyfile_policy

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

        # Honeyfiles por plantilla: pide al servidor qué debería crear
        # o ya tiene creado (GET /agent/honeyfile-policy), escribe lo
        # que falte y lo reporta. Se hace antes de levantar el monitor
        # para poder decirle qué carpetas vigilar además de ".".

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
            print(f"{len(rule_policy)} regla(s) activa(s) recibida(s) del servidor.")
        else:
            rule_policy = []
            print("No se pudo obtener la política de reglas. Se usan los valores por defecto.")

        # Monitor de archivos

        print()
        print("Iniciando monitor de archivos...")

        observer = start_file_monitor(".", existing_credential, watched_honeyfile_paths, rule_policy)

        print("Monitor activo.")
        print("Modifica archivos dentro de test_files o honeyfiles para probarlo.")

        input("Presiona ENTER para detener el monitor...")

        observer.stop()
        observer.join()

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
