import psutil


def get_running_processes():

    processes = []

    for process in psutil.process_iter(
        ["pid", "name", "exe", "username"]
    ):

        try:

            info = process.info

            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "path": info["exe"],
                "username": info["username"]
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):

            continue

    return processes


if __name__ == "__main__":

    processes = get_running_processes()

    for process in processes[:20]:

        print(
            f"PID: {process['pid']} | "
            f"Nombre: {process['name']} | "
            f"Ruta: {process['path']} | "
            f"Usuario: {process['username']}"
        )
