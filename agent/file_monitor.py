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


    def register_file_event(self, file_path, event_type):

        extension = os.path.splitext(file_path)[1].lower()

        print(
            f"Archivo: {file_path}"
        )

        print(
            f"Extensión: {extension}"
        )

        # Reportar el evento crudo al servidor (tabla 'events') ANTES
        # de registrarlo en el analizador -- necesitamos el event_id
        # que nos devuelve el servidor para poder, más adelante, decir
        # qué eventos concretos dispararon una alerta (tabla
        # 'alert_events'). Si el envío falla (sin conexión, error del
        # servidor), event_id queda en None: el evento sigue contando
        # para el puntaje de riesgo local, pero no se podrá vincular a
        # una alerta porque el servidor nunca llegó a guardarlo.
        event_response = send_event(
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

        event_id = None

        if event_response is not None and event_response.status_code < 400:

            try:
                event_id = event_response.json().get("event_id")
            except Exception:
                event_id = None

        file_count = self.analyzer.register_event(
            file_path,
            event_id
        )

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

            send_alert(
                self.credential,
                {
                    "severity": risk_level,
                    "title": (
                        "Honeyfile activado"
                        if is_honeyfile
                        else "Actividad de archivos sospechosa"
                    ),
                    "description": (
                        f"{file_count} archivos únicos modificados "
                        f"en los últimos {self.analyzer.window_seconds}s"
                    ),
                    "risk_score": score,
                    "rule_name": (
                        "honeyfile_access"
                        if is_honeyfile
                        else "mass_file_activity"
                    ),
                    "details": {
                        "file_count": file_count,
                        "last_file": file_path
                    },
                    "event_ids": self.analyzer.get_window_event_ids()
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

            self.register_file_event(event.src_path, "file_renamed")


def start_file_monitor(path, credential):

    analyzer = FileActivityAnalyzer(
        window_seconds=10,
        threshold=20
    )

    honeyfile_monitor = HoneyfileMonitor(
        "honeyfiles"
    )

    event_handler = FileActivityHandler(
        analyzer,
        honeyfile_monitor,
        credential
    )

    observer = Observer()

    observer.schedule(
        event_handler,
        path,
        recursive=True
    )

    observer.start()

    return observer
