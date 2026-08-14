from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from heuristic_engine import FileActivityAnalyzer

from honeyfile_monitor import HoneyfileMonitor

from client import send_event, send_alert

import os

class FileActivityHandler(FileSystemEventHandler):

    def __init__(self, analyzer, honeyfile_monitor, credential):

        self.analyzer = analyzer
        self.honeyfile_monitor = honeyfile_monitor
        self.credential = credential


    # Títulos/descripciones legibles por regla -- el score y el nivel
    # de riesgo son reales (calculados por FileActivityAnalyzer), pero
    # el texto que acompaña a cada uno es fijo por regla, no generado
    # dinámicamente a partir de datos que no tenemos (proceso, usuario).
    RULE_TITLES = {
        "ransomware_extension_rename": "Archivo renombrado a extensión de ransomware conocida",
        "honeyfile_access": "Honeyfile activado",
        "mass_deletion": "Borrado masivo de archivos",
        "mass_file_activity": "Actividad de archivos sospechosa",
    }

    def register_file_event(self, file_path, event_type):

        extension = os.path.splitext(file_path)[1].lower()

        print(
            f"Archivo: {file_path}"
        )

        print(
            f"Extensión: {extension}"
        )

        # Reportar el evento crudo al servidor (tabla 'events'). Antes
        # esto capturaba el event_id de la respuesta para vincular la
        # alerta a los eventos que la dispararon (tabla 'alert_events'),
        # pero esa tabla no existe en la nueva estructura (alfa_sentinel)
        # -- ver PENDIENTES.md. Se sigue mandando el evento igual, solo
        # que ya no se hace nada con el id de vuelta.
        send_event(
            self.credential,
            {
                "event_type": event_type,
                "description": f"{event_type} en {file_path}",
                "metadata": {
                    "file_path": file_path,
                    "extension": extension
                }
            }
        )

        file_count = self.analyzer.register_event(file_path, event_type)

        # Comprobar honeyfile

        is_honeyfile = self.honeyfile_monitor.is_honeyfile(file_path)

        if is_honeyfile:

            print()
            print("⚠ HONEYFILE ACTIVADO")
            print(f"Archivo: {file_path}")
            print()

            self.analyzer.register_honeyfile_detection()

        # Evaluar riesgo

        score = self.analyzer.calculate_score()

        risk_level = self.analyzer.get_risk_level()

        print(
            f"Archivos únicos afectados en ventana: "
            f"{file_count}"
        )

        print(
            f"Puntuación de riesgo: {score}"
        )

        print(
            f"Nivel de riesgo: {risk_level}"
        )

        if self.analyzer.is_suspicious():

            print(
                "¡ACTIVIDAD SOSPECHOSA DETECTADA!"
            )

            # Puede haber más de una regla disparada a la vez (ej.
            # borrado masivo + honeyfile). El score ya suma todas;
            # get_primary_rule() devuelve la de mayor peso para
            # reportarla como 'rule_name' -- el servidor todavía solo
            # acepta una regla por alerta (ver report_alert en
            # server/main.py). "details"/"event_ids" siguen sin
            # mandarse -- ver PENDIENTES.md.
            primary_rule = self.analyzer.get_primary_rule() or "mass_file_activity"

            send_alert(
                self.credential,
                {
                    "severity": risk_level,
                    "title": self.RULE_TITLES.get(primary_rule, "Actividad de archivos sospechosa"),
                    "description": (
                        f"{file_count} archivos únicos modificados "
                        f"en los últimos {self.analyzer.window_seconds}s"
                    ),
                    "risk_score": score,
                    "rule_name": primary_rule
                }
            )


    def on_created(self, event):

        if not event.is_directory:

            print(
                f"[CREATED] {event.src_path}"
            )

            self.register_file_event(event.src_path, "file_created")

    def on_modified(self, event):

        if not event.is_directory:

            print(
                f"[MODIFIED] {event.src_path}"
            )

            self.register_file_event(event.src_path, "file_modified")

    def on_deleted(self, event):

        if not event.is_directory:

            print(
                f"[DELETED] {event.src_path}"
            )

            self.register_file_event(event.src_path, "file_deleted")

    def on_moved(self, event):

        if not event.is_directory:

            print(
                f"[MOVED] {event.src_path} -> "
                f"{event.dest_path}"
            )

            # Se reporta 'dest_path' (el nombre/ruta nuevo), no
            # 'src_path' (el viejo, que ya no existe). Esto importa en
            # particular para la regla ransomware_extension_rename: si
            # se mira la extensión del nombre VIEJO, un rename a
            # "informe.docx.locked" nunca se detectaría porque la
            # extensión sospechosa está en el nombre nuevo.
            self.register_file_event(event.dest_path, "file_renamed")


def start_file_monitor(path, credential, known_honeyfile_paths=None, rule_policy=None):

    # 'rule_policy' es la lista 'rules' que devuelve GET /agent/rule-policy
    # (ver agent/main.py, agent/client.py::get_rule_policy) -- None o
    # lista vacía si no se pudo pedir, en cuyo caso from_policy() cae
    # en los valores por defecto de siempre.
    analyzer = FileActivityAnalyzer.from_policy(rule_policy)

    honeyfile_monitor = HoneyfileMonitor(
        "honeyfiles",
        known_paths=known_honeyfile_paths
    )

    event_handler = FileActivityHandler(
        analyzer,
        honeyfile_monitor,
        credential
    )

    observer = Observer()

    watched_root = os.path.abspath(path)

    observer.schedule(
        event_handler,
        path,
        recursive=True
    )

    # Los honeyfiles desplegados por plantilla (agent/honeyfile_deployer.py)
    # pueden vivir fuera de 'path' (ej. el Desktop del usuario, no la
    # carpeta desde donde corre el agente) -- sin esto, watchdog nunca
    # ve actividad ahí, porque el watch recursivo de 'path' no llega.
    extra_dirs = set()

    for honeyfile_path in (known_honeyfile_paths or []):

        directory = os.path.dirname(os.path.abspath(honeyfile_path))

        if directory and not directory.startswith(watched_root):
            extra_dirs.add(directory)

    for directory in extra_dirs:

        if os.path.isdir(directory):

            observer.schedule(
                event_handler,
                directory,
                recursive=False
            )

            print(f"Vigilando también: {directory}")

    observer.start()

    return observer
