import base64
import hashlib
import os

from client import get_honeyfile_policy, report_honeyfile_policy
from file_ownership import adopt_parent_owner, open_for_read_no_follow, open_new_file_for_write
from paths import resolve_logical_path


def _write_and_hash(full_path, content):
    """Escribe el contenido real en disco (creando el directorio si
    hace falta) y devuelve el SHA-256 calculado sobre lo que
    efectivamente quedó escrito -- nunca se inventa un hash, siempre
    se lee de vuelta el archivo real (ver especificación, sección 20:
    "el hash tiene que corresponder al archivo REAL que el agente
    escribió, nunca a un valor generado o supuesto")."""

    # La carpeta ya la creó resolve_logical_path() (con el dueño
    # correcto, ver agent/file_ownership.py).

    # 'content' son los bytes del archivo real que generó el servidor
    # (PDF, DOCX, XLSX, JPG...; ver server/honeyfile_content.py). Si llega
    # texto (un servidor anterior sin 'content_b64'), se guarda como texto
    # con los saltos de línea del SO, como antes.
    if isinstance(content, bytes):
        data = content
    else:
        data = (content or "").replace("\n", os.linesep).encode("utf-8")

    # Archivo NUEVO sin seguir enlaces: el agente corre con privilegios y
    # escribe en una carpeta del usuario; si alguien plantó un enlace
    # simbólico en esta ruta, falla en vez de escribir a través de él.
    with open_new_file_for_write(full_path) as f:
        f.write(data)

    # Queda a nombre del dueño de la carpeta (el usuario), como cualquier
    # archivo suyo -- ver agent/file_ownership.py.
    adopt_parent_owner(full_path, newly_created=True)

    return _hash_of(full_path)


def _item_content(item):
    """Bytes del archivo real si el servidor los mandó; si no, el texto."""

    if "content_b64" not in item:
        return item.get("content")  # servidor anterior: solo texto
    if not item["content_b64"]:
        # Honeyfile ya creado que llegó sin su archivo (no se pudo pedir
        # la política completa). Nunca se escribe texto en su lugar: se
        # informa el fallo y el servidor lo vuelve a mandar como pendiente.
        raise OSError("el servidor no envió el archivo; se reintentará en el próximo ciclo")
    return base64.b64decode(item["content_b64"], validate=True)


def _honeyfile_path(directory, file_name):
    """Ruta del honeyfile dentro de su carpeta. El nombre viene del
    servidor: si trajera una ruta ('..', separadores) el agente, que corre
    con privilegios, escribiría fuera de ALFA_ARCHIVOS."""

    name = file_name or ""
    if not name or name in (".", "..") or "/" in name or "\\" in name or name != os.path.basename(name):
        raise OSError(f"Nombre de honeyfile inválido: {file_name!r}")
    return os.path.join(directory, name)


def _any_existing_missing(policy):
    for item in policy.get("existing", []):
        try:
            directory = resolve_logical_path(item["file_path"])
            if not os.path.lexists(_honeyfile_path(directory, item["file_name"])):
                return True
        except OSError:
            continue
    return False


def _hash_of(full_path):
    with open_for_read_no_follow(full_path) as f:
        return hashlib.sha256(f.read()).hexdigest()


def apply_honeyfile_policy(credential, honeyfile_monitor=None):
    """Pide al servidor la política de honeyfiles de este agente
    (GET /agent/honeyfile-policy) y hace dos cosas con la respuesta,
    en cada ciclo (al arrancar y en cada sincronización periódica
    posterior -- ver agent/honeyfile_sync.py, 2026-08-17, PENDIENTES.md,
    "Honeyfiles: despliegue automático, rutas, integridad,
    reconciliación y ejecución en tiempo real"):

    'honeyfile_monitor' (2026-08-17, ver PENDIENTES.md, "Honeyfiles +
    monitorización completa del endpoint..."): si se pasa, cada
    escritura real que este módulo hace se marca como "operación
    interna" ANTES de escribir (sección 22/34 -- ver
    HoneyfileMonitor.mark_internal_operation) para que watchdog no la
    confunda con una interacción externa y dispare HR-03 por la propia
    creación/reconciliación del agente. Es None cuando todavía no
    existe (la primerísima sincronización al arrancar, antes de que
    start_file_monitor() construya el HoneyfileMonitor real) -- en ese
    momento el observer de watchdog ni siquiera arrancó todavía, así
    que no hay riesgo de un falso HR-03 y no marcar nada es seguro.

    1. 'pending' -- asignaciones que todavía no se crearon nunca
       (manuales desde el Wizard, resueltas ahora desde una plantilla
       con auto_deploy=TRUE, o reintentos de un FAILED anterior).
       Se crean por primera vez (caso D de la sección 22).

    2. 'existing' -- asignaciones ya creadas en un ciclo anterior. Se
       RECONCILIAN, no se recrean a ciegas (sección 22):
         A. existe en disco y el hash coincide con 'expected_hash'
            -> no-op, no se reporta nada.
         B. no existe en disco (se borró) -> se recrea con el mismo
            contenido de la plantilla, se reporta 'CREATED' de nuevo.
         C. existe pero el hash real ya no coincide -> se registra el
            hash nuevo (status 'MODIFIED'), NUNCA se restaura el
            contenido (fuera de alcance, ver sección 28).

    Devuelve la lista de rutas absolutas -- creadas o ya existentes --
    que file_monitor.py / honeyfile_sync.py tienen que vigilar."""

    response = get_honeyfile_policy(credential)

    if response is None or response.status_code != 200:
        print("No se pudo obtener la política de honeyfiles del servidor.")
        return []

    policy = response.json()

    # Los honeyfiles ya creados llegan sin su archivo (solo el hash
    # esperado). Si alguno desapareció del disco hay que recrearlo: recién
    # ahí se pide la política completa, con el archivo de cada uno.
    if _any_existing_missing(policy):
        full_response = get_honeyfile_policy(credential, full=True)
        if full_response is not None and full_response.status_code == 200:
            policy = full_response.json()

    watched_paths = []
    report_results = []

    # --- Pendientes: nunca creados (o reintento de un FAILED) ---
    for item in policy.get("pending", []):

        full_path = None

        try:
            # resolve_logical_path() ahora también CREA la carpeta
            # ALFA_ARCHIVOS si falta (sección 17) -- puede fallar con
            # el mismo tipo de error real que escribir el archivo (ej.
            # sin permiso sobre la carpeta padre), así que queda DENTRO
            # del try: un fallo acá también debe reportarse FAILED
            # para este ítem puntual, no tumbar toda la sincronización.
            directory = resolve_logical_path(item["file_path"])
            full_path = _honeyfile_path(directory, item["file_name"])

            if not os.path.exists(full_path):
                if honeyfile_monitor is not None:
                    honeyfile_monitor.mark_internal_operation(full_path)
                file_hash = _write_and_hash(full_path, _item_content(item))
                print(f"Honeyfile creado: {full_path}")
            else:
                # Ya existe en disco (p. ej. un ciclo anterior lo creó
                # pero el reporte al servidor no llegó a confirmarse) --
                # no se sobreescribe, se adopta tal cual está.
                file_hash = _hash_of(full_path)
                print(f"Honeyfile ya existía, no se sobreescribe: {full_path}")

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

    # --- Existentes: reconciliación (casos A/B/C, sección 22) ---
    for item in policy.get("existing", []):

        try:
            # Igual que arriba: resolve_logical_path() puede fallar de
            # verdad (crea ALFA_ARCHIVOS si falta) -- sin poder resolver
            # la carpeta no hay forma de reconciliar este ítem puntual.
            directory = resolve_logical_path(item["file_path"])
        except OSError as error:
            print(f"No se pudo resolver/crear la carpeta para reconciliar el ítem {item['assignment_id']}: {error}")
            report_results.append({
                "assignment_id": item["assignment_id"],
                "status": "FAILED",
                "error": str(error)
            })
            continue

        try:
            full_path = _honeyfile_path(directory, item["file_name"])
        except OSError as error:
            print(f"No se pudo reconciliar el ítem {item['assignment_id']}: {error}")
            continue
        expected_hash = item.get("expected_hash")

        if not os.path.exists(full_path):
            # Caso B: asignado, pero desapareció del disco -> recrear.
            try:
                if honeyfile_monitor is not None:
                    honeyfile_monitor.mark_internal_operation(full_path)
                file_hash = _write_and_hash(full_path, _item_content(item))
                print(f"Honeyfile recreado (había desaparecido): {full_path}")
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
                print(f"No se pudo recrear el honeyfile en {full_path}: {error}")
                report_results.append({
                    "assignment_id": item["assignment_id"],
                    "status": "FAILED",
                    "error": str(error)
                })
            continue

        watched_paths.append(full_path)

        # Honeyfile que una versión anterior dejó a nombre de root: se le
        # asigna el dueño de la carpeta. Se marca como operación propia
        # porque cambiar el dueño genera un evento de atributos que
        # watchdog informa como modificación (evita una falsa HR-03).
        if honeyfile_monitor is not None:
            honeyfile_monitor.mark_internal_operation(full_path)
        adopt_parent_owner(full_path, newly_created=False)

        try:
            real_hash = _hash_of(full_path)
        except OSError as error:
            # No se pudo ni leer para verificar -- se sigue vigilando
            # igual, pero no se reporta nada (no se inventa un hash).
            print(f"No se pudo verificar el hash de {full_path}: {error}")
            continue

        if expected_hash and real_hash != expected_hash:
            # Caso C: el contenido real ya no coincide con lo esperado.
            # Se registra el hash nuevo -- nunca se restaura el
            # contenido, esa detección la completa HR-03 si watchdog
            # observó la modificación en vivo (sección 28, fuera de
            # alcance recuperar/restaurar).
            print(f"Honeyfile modificado detectado en reconciliación: {full_path}")
            report_results.append({
                "assignment_id": item["assignment_id"],
                "status": "MODIFIED",
                "file_hash": real_hash
            })
        # Caso A (el hash coincide): no-op, nada que reportar.

    if report_results:
        report_honeyfile_policy(credential, report_results)

    return watched_paths
