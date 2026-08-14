from collections import deque
from time import time
import os


# Extensiones que ransomware conocido usa para marcar archivos ya
# cifrados (WannaCry, Locky, Cerber, variantes genéricas de
# "Cryptolocker-style"). Es una lista estática y no exhaustiva -- no
# hay forma de detectar esto por firma/comportamiento del binario
# (el agente no inspecciona contenido ni procesos, ver PENDIENTES.md),
# así que esto reacciona solo a la extensión final del archivo
# después de un rename. Se puede seguir sumando extensiones acá sin
# tocar el resto del motor.
RANSOMWARE_EXTENSIONS = {
    ".locked", ".encrypted", ".enc", ".crypt", ".crypted",
    ".cerber", ".wcry", ".wncry", ".locky", ".zzz", ".micro", ".r5a"
}


# Nombres de regla reconocidos -- tienen que coincidir con
# 'heuristic_rules.name' en la base (ver database/schema.sql). Se usan
# tanto acá (RULE_NAMES) como en server/main.py::get_rule_policy.
RULE_NAMES = {
    "mass_file_activity",
    "honeyfile_access",
    "ransomware_extension_rename",
    "mass_deletion"
}


class FileActivityAnalyzer:

    def __init__(
        self,
        window_seconds=10,
        threshold=20,
        mass_activity_score=30,
        honeyfile_score=60,
        honeyfile_window_seconds=60,
        ransomware_extension_score=70,
        ransomware_extension_threshold=1,
        ransomware_extension_window_seconds=30,
        mass_deletion_score=40,
        mass_deletion_threshold=15,
        mass_deletion_window_seconds=10,
        enabled_rules=None
    ):

        self.window_seconds = window_seconds
        self.threshold = threshold

        # Qué reglas evalúa este analizador -- por defecto, las 4
        # (mismo comportamiento que siempre tuvo el motor). Cuando se
        # construye vía from_policy() con lo que devolvió el servidor,
        # una regla que el servidor marcó is_active=FALSE no aparece
        # en la política y por lo tanto no entra acá -- el agente deja
        # de evaluarla del todo, no la evalúa igual con un valor
        # cualquiera.
        self.enabled_rules = enabled_rules if enabled_rules is not None else set(RULE_NAMES)

        self.mass_activity_score = mass_activity_score
        self.honeyfile_score = honeyfile_score

        # Ventana propia para el honeyfile: más larga que la de
        # actividad masiva a propósito -- tocar un señuelo es una
        # señal más fuerte, tiene sentido que la sospecha dure un
        # poco más. Pero, igual que con los archivos, NO para siempre.
        self.honeyfile_window_seconds = honeyfile_window_seconds

        # Renombrar UN SOLO archivo a una extensión de ransomware
        # conocida ya es fuerte -- threshold=1 a propósito, no hace
        # falta esperar "varios" para sospechar.
        self.ransomware_extension_score = ransomware_extension_score
        self.ransomware_extension_threshold = ransomware_extension_threshold
        self.ransomware_extension_window_seconds = ransomware_extension_window_seconds

        # Distinta de "actividad masiva" genérica (mass_file_activity
        # mezcla creados/modificados/eliminados/renombrados): una
        # ráfaga de solo BORRADOS es una señal más específica de
        # "está destruyendo los originales", vale la pena separarla.
        self.mass_deletion_score = mass_deletion_score
        self.mass_deletion_threshold = mass_deletion_threshold
        self.mass_deletion_window_seconds = mass_deletion_window_seconds

        self.events = deque()

        self.honeyfile_events = deque()

        self.rename_events = deque()

        self.deletion_events = deque()

    def register_event(self, file_path, event_type=None):
        # Ya no guarda event_id: existía solo para armar 'event_ids'
        # y poblar 'alert_events', tabla que no está en la nueva
        # estructura (alfa_sentinel). Ver PENDIENTES.md.
        #
        # 'event_type' es opcional para no romper llamadas viejas,
        # pero sin él solo se evalúa mass_file_activity/honeyfile --
        # las reglas de borrado masivo y rename sospechoso necesitan
        # saber qué tipo de evento fue.

        current_time = time()

        self.events.append(
            (current_time, file_path)
        )

        self._remove_old_events(current_time)

        if event_type == "file_deleted":
            self.deletion_events.append(current_time)
            self._remove_old_deletions(current_time)

        elif event_type == "file_renamed":
            extension = os.path.splitext(file_path)[1].lower()
            if extension in RANSOMWARE_EXTENSIONS:
                self.rename_events.append((current_time, extension))
            self._remove_old_renames(current_time)

        return self.get_unique_file_count()

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

    def _remove_old_deletions(self, current_time):

        while self.deletion_events:

            if current_time - self.deletion_events[0] <= self.mass_deletion_window_seconds:
                break

            self.deletion_events.popleft()

    def _remove_old_renames(self, current_time):

        while self.rename_events:

            if current_time - self.rename_events[0][0] <= self.ransomware_extension_window_seconds:
                break

            self.rename_events.popleft()

    def get_unique_file_count(self):

        unique_files = set()

        for _, file_path in self.events:

            unique_files.add(file_path)

        return len(unique_files)

    def get_deletion_count(self):

        self._remove_old_deletions(time())

        return len(self.deletion_events)

    def get_ransomware_rename_count(self):

        self._remove_old_renames(time())

        return len(self.rename_events)

    def _triggered_rules(self):
        """Devuelve la lista de nombres de regla que están disparadas
        ahora mismo, en orden de peso descendente -- se usa tanto para
        sumar el score total como para decidir qué regla "principal"
        reportar (el servidor guarda una sola regla por alerta hoy,
        ver server/main.py::report_alert)."""

        triggered = []

        if (
            "ransomware_extension_rename" in self.enabled_rules
            and self.get_ransomware_rename_count() >= self.ransomware_extension_threshold
        ):
            triggered.append(("ransomware_extension_rename", self.ransomware_extension_score))

        if "honeyfile_access" in self.enabled_rules and self._has_recent_honeyfile_activity():
            triggered.append(("honeyfile_access", self.honeyfile_score))

        if (
            "mass_deletion" in self.enabled_rules
            and self.get_deletion_count() >= self.mass_deletion_threshold
        ):
            triggered.append(("mass_deletion", self.mass_deletion_score))

        if (
            "mass_file_activity" in self.enabled_rules
            and self.get_unique_file_count() >= self.threshold
        ):
            triggered.append(("mass_file_activity", self.mass_activity_score))

        triggered.sort(key=lambda item: item[1], reverse=True)

        return triggered

    @classmethod
    def from_policy(cls, policy_rules):
        """Construye el analizador a partir de lo que devolvió
        GET /agent/rule-policy (server/main.py) -- lista de dicts
        {name, weight, threshold, window_seconds}, una por regla
        activa. Si 'policy_rules' viene vacía o None (servidor
        inalcanzable, error de red -- ver agent/main.py), se usan los
        valores por defecto de __init__() con las 4 reglas activas: un
        problema de red no debería dejar al agente sin detectar nada,
        solo sin la última configuración."""

        by_name = {rule["name"]: rule for rule in (policy_rules or [])}

        kwargs = {}

        if "mass_file_activity" in by_name:
            rule = by_name["mass_file_activity"]
            kwargs["threshold"] = int(rule["threshold"])
            kwargs["window_seconds"] = rule["window_seconds"]
            kwargs["mass_activity_score"] = rule["weight"]

        if "honeyfile_access" in by_name:
            rule = by_name["honeyfile_access"]
            kwargs["honeyfile_score"] = rule["weight"]
            kwargs["honeyfile_window_seconds"] = rule["window_seconds"]

        if "ransomware_extension_rename" in by_name:
            rule = by_name["ransomware_extension_rename"]
            kwargs["ransomware_extension_score"] = rule["weight"]
            kwargs["ransomware_extension_threshold"] = int(rule["threshold"])
            kwargs["ransomware_extension_window_seconds"] = rule["window_seconds"]

        if "mass_deletion" in by_name:
            rule = by_name["mass_deletion"]
            kwargs["mass_deletion_score"] = rule["weight"]
            kwargs["mass_deletion_threshold"] = int(rule["threshold"])
            kwargs["mass_deletion_window_seconds"] = rule["window_seconds"]

        kwargs["enabled_rules"] = set(RULE_NAMES) if not policy_rules else set(by_name.keys())

        return cls(**kwargs)

    def calculate_score(self):

        score = sum(weight for _, weight in self._triggered_rules())

        # Cap a 100: 'severity_levels.max_score' llega hasta 100, y
        # con 3-4 reglas simultáneas la suma cruda podría superarlo.
        # El score sigue siendo la suma real, solo se acota para no
        # mandar un número fuera de la escala que usa el resto del
        # sistema.
        return min(score, 100)

    def get_primary_rule(self):
        """La regla de mayor peso entre las disparadas ahora mismo, o
        None si ninguna lo está. 'Mayor peso' es una simplificación
        honesta: si dos reglas distintas disparan a la vez, la alerta
        igual solo puede llevar una 'rule_name' hoy (ver
        report_alert en server/main.py) -- no se inventa una forma de
        reportar varias a la vez."""

        triggered = self._triggered_rules()

        return triggered[0][0] if triggered else None

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
