import hashlib
import os

from client import get_honeyfile_policy, report_honeyfile_policy


def _resolve_directory(raw_path):
    """Convierte el path guardado en la plantilla (puede traer
    %USERPROFILE%, $HOME o ~ para no atarse a un solo SO -- ver
    server/main.py, honeyfile_templates.file_path) a una ruta real en
    esta máquina."""

    home = os.path.expanduser("~")

    resolved = raw_path.replace("%USERPROFILE%", home).replace("$HOME", home)

    if resolved.startswith("~"):
        resolved = home + resolved[1:]

    return os.path.normpath(resolved)


def apply_honeyfile_policy(credential):
    """Pide al servidor qué honeyfiles debería tener este agente
    (GET /agent/honeyfile-policy), crea en disco los que todavía
    faltan, reporta el resultado (POST /agent/honeyfile-policy/report)
    y devuelve la lista de rutas absolutas -- ya existentes o recién
    creadas -- que file_monitor.py tiene que vigilar como honeyfiles.

    Se llama en cada ejecución del agente, no solo al enrolarse: el
    agente es un script de una sola pasada sin bucle en segundo plano
    (ver PENDIENTES.md), así que "la próxima vez que corra" es el
    único momento en que puede enterarse de una plantilla nueva o una
    asignación manual hecha después de que ya existía."""

    response = get_honeyfile_policy(credential)

    if response is None or response.status_code != 200:
        print("No se pudo obtener la política de honeyfiles del servidor.")
        return []

    policy = response.json()

    watched_paths = []

    for item in policy.get("existing", []):
        watched_paths.append(item["file_path"])

    report_results = []

    for item in policy.get("pending", []):

        directory = _resolve_directory(item["file_path"])
        full_path = os.path.join(directory, item["file_name"])

        try:

            if not os.path.exists(full_path):

                os.makedirs(directory, exist_ok=True)

                # Contenido de texto plano guardado con la extensión
                # elegida -- no es un .xlsx/.docx/.pdf válido de
                # verdad (ver database/schema.sql, tabla
                # honeyfile_templates). Alcanza para que watchdog y la
                # detección de "Acceso Honeyfile" reaccionen, que es lo
                # único que este proyecto necesita de él.
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(item.get("content") or "")

                print(f"Honeyfile creado: {full_path}")

            else:
                print(f"Honeyfile ya existía, no se sobreescribe: {full_path}")

            with open(full_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            watched_paths.append(full_path)

            report_results.append({
                "assignment_id": item["assignment_id"],
                "status": "CREATED",
                "file_path": full_path,
                "file_name": item["file_name"],
                "file_type": item["file_type"],
                "file_hash": file_hash
            })

        except OSError as error:

            print(f"No se pudo crear el honeyfile en {full_path}: {error}")

            report_results.append({
                "assignment_id": item["assignment_id"],
                "status": "FAILED",
                "error": str(error)
            })

    if report_results:
        report_honeyfile_policy(credential, report_results)

    return watched_paths
