import platform
import socket

from process_monitor import get_running_processes

from file_monitor import start_file_monitor

from client import (
    enroll_agent,
    authenticate_agent,
    send_heartbeat
)

from credential import (
    save_credential,
    load_credential
)


def get_system_info():

    return {
        "hostname": socket.gethostname(),
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine()
    }


if __name__ == "__main__":

    print("Agente iniciado")

    system_info = get_system_info()

    print("Información del equipo:")
    print(system_info)

    existing_credential = load_credential()

    if existing_credential:

        print("El agente ya está registrado.")
        print("Credencial encontrada localmente.")

        # Autenticación

        response = authenticate_agent(existing_credential)

        if response is not None:

            print("Respuesta de autenticación:")
            print(response.json())

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

        # Monitor de archivos

        print()
        print("Iniciando monitor de archivos...")

        observer = start_file_monitor(".", existing_credential)

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
