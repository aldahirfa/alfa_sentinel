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


    # Títulos/descripciones legibles por regla -- el título es fijo por
    # regla (no generado dinámicamente a partir de datos que no
    # tenemos, como proceso o usuario). El score, la severidad y qué
    # reglas participaron (con su peso real) los calcula y registra el
    # SERVIDOR (ver server/main.py::report_alert) a partir de la lista
    # 'matched_rules' que se manda acá -- el agente ya no decide
    # severidad ni risk_score (sección 1 de la especificación del
    # motor heurístico: separar detección de cálculo de riesgo).
    RULE_TITLES = {
        "modificacion_masiva_archivos": "Modificación masiva de archivos",
        "renombrado_extension_anomala": "Renombrado con extensión de ransomware conocida",
        "acceso_honeyfile": "Honeyfile activado",
        "escritura_intensiva_archivos": "Escritura intensiva de archivos",
        "acceso_recursos_compartidos": "Acceso masivo a recursos compartidos",
        "creacion_masiva_temporales": "Creación masiva de archivos temporales",
        "eliminacion_anomala_archivos": "Eliminación anómala de archivos",
        "actividad_archivos_usuario": "Actividad repetitiva sobre archivos de usuario",
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

        # Comprobar honeyfile ANTES de evaluar reglas: HR-03 es
        # inmediata (sección 12 de la especificación), no depende de
        # ninguna ventana ni se acumula con las demás reglas.
        is_honeyfile = self.honeyfile_monitor.is_honeyfile(file_path)

        if is_honeyfile:

            print()
            print("⚠ HONEYFILE ACTIVADO")
            print(f"Archivo: {file_path}")
            print()

        matched_rules = self.analyzer.register_event(file_path, event_type, is_honeyfile=is_honeyfile)

        file_count = self.analyzer.get_unique_file_count()

        print(
            f"Archivos únicos afectados en ventana (HR-01): "
            f"{file_count}"
        )

        print(
            f"Reglas activas: {matched_rules if matched_rules else 'ninguna'}"
        )

        if matched_rules:

            print(
                "¡ACTIVIDAD SOSPECHOSA DETECTADA!"
            )

            # El agente ya no decide severidad/score/título compuesto:
            # manda TODAS las reglas que coincidieron (matched_rules) y
            # deja que el servidor calcule peso, correlación, score y
            # severidad a partir de heuristic_rules (ver
            # server/main.py::report_alert). 'title'/'description' son
            # solo un resumen legible para el caso en que el servidor
            # tenga que generar una alerta nueva -- si actualiza una
            # existente, conserva su propio título.
            primary_rule = matched_rules[0]

            send_alert(
                self.credential,
                {
                    "title": self.RULE_TITLES.get(primary_rule, "Actividad de archivos sospechosa"),
                    "description": (
                        f"{file_count} archivos únicos modificados en la ventana de HR-01; "
                        f"reglas coincidentes: {', '.join(matched_rules)}"
                    ),
                    "matched_rules": matched_rules
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
            # particular para la regla renombrado_extension_anomala: si
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
