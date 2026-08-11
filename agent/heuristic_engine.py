from collections import deque
from time import time


class FileActivityAnalyzer:

    def __init__(
        self,
        window_seconds=10,
        threshold=20,
        mass_activity_score=30,
        honeyfile_score=60,
        honeyfile_window_seconds=60
    ):

        self.window_seconds = window_seconds
        self.threshold = threshold

        self.mass_activity_score = mass_activity_score
        self.honeyfile_score = honeyfile_score

        # Ventana propia para el honeyfile: más larga que la de
        # actividad masiva a propósito -- tocar un señuelo es una
        # señal más fuerte, tiene sentido que la sospecha dure un
        # poco más. Pero, igual que con los archivos, NO para siempre.
        self.honeyfile_window_seconds = honeyfile_window_seconds

        self.events = deque()

        self.honeyfile_events = deque()

    def register_event(self, file_path, event_id=None):

        current_time = time()

        self.events.append(
            (current_time, file_path, event_id)
        )

        self._remove_old_events(current_time)

        return self.get_unique_file_count()

    def get_window_event_ids(self):
        """IDs (asignados por el servidor) de los eventos que están
        actualmente en la ventana -- son los que justifican una alerta
        si se dispara ahora mismo. Si send_event falló para alguno
        (sin conexión, error del servidor), su event_id queda en None
        y no lo mandamos -- no podemos vincular una alerta a un evento
        que el servidor nunca llegó a guardar."""

        return [
            event_id
            for _, _, event_id in self.events
            if event_id is not None
        ]

    def register_honeyfile_detection(self):

        self.honeyfile_events.append(time())

    def _has_recent_honeyfile_activity(self):

        current_time = time()

        while self.honeyfile_events:

            oldest_event_time = self.honeyfile_events[0]

            if current_time - oldest_event_time <= self.honeyfile_window_seconds:
                break

            self.honeyfile_events.popleft()

        return len(self.honeyfile_events) > 0

    def _remove_old_events(self, current_time):

        while self.events:

            oldest_event_time = self.events[0][0]

            if current_time - oldest_event_time <= self.window_seconds:
                break

            self.events.popleft()

    def get_unique_file_count(self):

        unique_files = set()

        for _, file_path, _ in self.events:

            unique_files.add(file_path)

        return len(unique_files)

    def calculate_score(self):

        score = 0

        file_count = self.get_unique_file_count()

        if file_count >= self.threshold:

            score += self.mass_activity_score

        if self._has_recent_honeyfile_activity():

            score += self.honeyfile_score

        return score

    def get_risk_level(self):

        score = self.calculate_score()

        if score >= 80:

            return "CRITICAL"

        elif score >= 60:

            return "HIGH"

        elif score >= 30:

            return "SUSPICIOUS"

        else:

            return "NORMAL"


    def is_suspicious(self):

        return self.get_risk_level() in [
            "SUSPICIOUS",
            "HIGH",
            "CRITICAL"
        ]
