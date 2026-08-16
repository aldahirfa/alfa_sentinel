from collections import deque
from time import time
import os


# ============================================================
# Motor heurístico -- reescrito 2026-08-16 según la especificación
# definitiva del motor de reglas heurísticas (ver PENDIENTES.md).
#
# Cambio de arquitectura clave respecto a la versión anterior: este
# módulo ya NO calcula risk_score ni severidad. Esa responsabilidad
# pasó al servidor (server/main.py::report_alert), que es quien
# conoce el peso real de cada regla (heuristic_rules.weight, editable
# desde /configuracion) y quien calcula la bonificación de
# correlación entre reglas (HR-12). El agente se limita a DETECTAR:
# a partir de los eventos de archivo que observa, decide qué reglas
# están activas ahora mismo y se lo reporta al servidor (sección 1 de
# la especificación: "separar detección de cálculo de riesgo").
# ============================================================


# Extensiones que ransomware conocido usa para marcar archivos ya
# cifrados. Lista estática y no exhaustiva -- el agente no inspecciona
# contenido ni procesos, así que esto reacciona solo a la extensión
# final del archivo después de un rename (HR-02).
RANSOMWARE_EXTENSIONS = {
    ".locked", ".encrypted", ".enc", ".crypt", ".crypted",
    ".cerber", ".wcry", ".wncry", ".locky", ".zzz", ".micro", ".r5a"
}

# Carpetas de usuario relevantes para HR-10 (sección 19 de la
# especificación) -- coincidencia por segmento de ruta, sin distinguir
# mayúsculas/minúsculas (ni Windows ni el usuario son consistentes con
# eso).
USER_FOLDER_MARKERS = {"documents", "desktop", "downloads", "pictures", "music", "videos"}

# Heurística de "archivo temporal" para HR-08: extensión .tmp/.temp o
# un segmento de ruta típico de carpetas temporales. Es una
# aproximación honesta basada en lo único que el agente ve (ruta +
# extensión) -- no hay forma de saber con certeza que un archivo es
# "temporal" sin más contexto del sistema operativo.
TEMP_PATH_MARKERS = {"temp", "tmp"}
TEMP_EXTENSIONS = {".tmp", ".temp"}


def _is_shared_path(file_path):
    """Heurística de "ruta compartida" para HR-07: rutas UNC de
    Windows (\\\\servidor\\recurso) o su equivalente POSIX
    (//servidor/recurso). Limitación conocida: el agente no puede
    distinguir una unidad de red mapeada con letra de unidad (ej.
    Z:\\) de una unidad local -- eso requeriría consultar al SO qué
    unidades son de red, algo que no se implementa acá. Se documenta,
    no se simula."""
    return file_path.startswith("\\\\") or file_path.startswith("//")


def _is_temp_path(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension in TEMP_EXTENSIONS:
        return True
    parts = {p.lower() for p in file_path.replace("\\", "/").split("/") if p}
    return bool(parts & TEMP_PATH_MARKERS)


def _is_user_path(file_path):
    parts = {p.lower() for p in file_path.replace("\\", "/").split("/") if p}
    return bool(parts & USER_FOLDER_MARKERS)


# Nombres de regla que el AGENTE puede evaluar con los datos que
# recopila hoy (ruta + tipo de evento). Deben coincidir con
# 'heuristic_rules.name' en database/schema.sql.
#
# HR-05 (proceso_sospechoso), HR-06 (consumo_cpu_elevado) y HR-11
# (actividad_repetitiva_automatizada) NO están acá: requieren datos que el
# agente no recopila (atribución de proceso a evento de archivo, CPU
# por proceso) -- se siembran is_active=FALSE en la base y no se
# simulan (sección 40 de la especificación). HR-12
# (correlacion_multiples_indicadores) tampoco: la calcula el servidor, no el
# agente.
RULE_NAMES = {
    "modificacion_masiva_archivos",
    "renombrado_extension_anomala",
    "acceso_honeyfile",
    "escritura_intensiva_archivos",
    "acceso_recursos_compartidos",
    "creacion_masiva_temporales",
    "eliminacion_anomala_archivos",
    "actividad_archivos_usuario",
}

# Valores por defecto -- exactamente los que siembra database/schema.sql
# para cada regla. Se usan si el servidor no contestó GET
# /agent/rule-policy (problema de red no debe dejar al agente sin
# detectar nada, solo sin la última configuración editada desde
# /configuracion).
DEFAULT_RULES = {
    "modificacion_masiva_archivos":     {"threshold": 20, "window_seconds": 10},
    "renombrado_extension_anomala":     {"threshold": 5,  "window_seconds": 15},
    "acceso_honeyfile":                 {"threshold": 1,  "window_seconds": None},
    "escritura_intensiva_archivos":     {"threshold": 50, "window_seconds": 10},
    "acceso_recursos_compartidos":      {"threshold": 20, "window_seconds": 15},
    "creacion_masiva_temporales":       {"threshold": 30, "window_seconds": 15},
    "eliminacion_anomala_archivos":     {"threshold": 20, "window_seconds": 15},
    "actividad_archivos_usuario":       {"threshold": 30, "window_seconds": 20},
}


class FileActivityAnalyzer:
    """Detecta qué reglas heurísticas están activas AHORA MISMO, con
    ventanas deslizantes reales (sección 33 de la especificación:
    "evaluar si existen al menos N eventos dentro de los últimos W
    segundos", no bloques fijos de tiempo). No calcula score ni
    severidad -- ver comentario de módulo arriba."""

    def __init__(self, rules=None):
        self.rules = rules if rules is not None else dict(DEFAULT_RULES)

        self._deletion_events = deque()   # timestamps (HR-09)
        self._write_events = deque()      # timestamps (HR-04)
        self._temp_events = deque()       # timestamps (HR-08)
        self._shared_events = deque()     # timestamps (HR-07)
        self._user_events = deque()       # timestamps (HR-10)
        self._modified_events = deque()   # (ts, file_path) -- HR-01, cuenta únicos
        self._rename_events = deque()     # timestamps -- HR-02, solo renombrados con extensión sospechosa

    @classmethod
    def from_policy(cls, policy_rules):
        """policy_rules: lista de dicts {name, weight, threshold,
        window_seconds} que devuelve GET /agent/rule-policy. Cualquier
        nombre que el agente no sepa evaluar (ej.
        correlacion_multiples_indicadores, o una regla diferida is_active=
        FALSE que ni siquiera llega acá) se ignora sin romper nada."""

        rules = dict(DEFAULT_RULES)

        for row in (policy_rules or []):
            if row["name"] not in RULE_NAMES:
                continue
            rules[row["name"]] = {
                "threshold": float(row["threshold"]),
                "window_seconds": row.get("window_seconds") or DEFAULT_RULES[row["name"]]["window_seconds"],
            }

        return cls(rules=rules)

    def _prune(self, dq, window_seconds, current_time, key=None):
        if not window_seconds:
            return
        while dq:
            ts = dq[0][0] if key else dq[0]
            if current_time - ts <= window_seconds:
                break
            dq.popleft()

    def register_event(self, file_path, event_type, is_honeyfile=False):
        """Registra un evento de archivo y devuelve la lista de
        nombres de regla que están activas justo después de
        incorporarlo (puede ser más de una a la vez, ej. borrado
        masivo + actividad de usuario). No multiplica el peso por
        cantidad de eventos -- el llamador (file_monitor.py) decide
        qué hacer con la lista, y el peso real lo aplica el servidor."""

        now = time()
        matched = []

        # HR-03: inmediata, sin ventana ni acumulación -- cualquier
        # interacción con un honeyfile es suficiente (sección 12 de la
        # especificación).
        if is_honeyfile and "acceso_honeyfile" in self.rules:
            matched.append("acceso_honeyfile")

        extension = os.path.splitext(file_path)[1].lower()

        if event_type == "file_modified":
            if "modificacion_masiva_archivos" in self.rules:
                cfg = self.rules["modificacion_masiva_archivos"]
                self._modified_events.append((now, file_path))
                self._prune(self._modified_events, cfg["window_seconds"], now, key=True)
                unique_files = {p for _, p in self._modified_events}
                if len(unique_files) >= cfg["threshold"]:
                    matched.append("modificacion_masiva_archivos")

            if "escritura_intensiva_archivos" in self.rules:
                cfg = self.rules["escritura_intensiva_archivos"]
                self._write_events.append(now)
                self._prune(self._write_events, cfg["window_seconds"], now)
                if len(self._write_events) >= cfg["threshold"]:
                    matched.append("escritura_intensiva_archivos")

        if event_type == "file_renamed" and "renombrado_extension_anomala" in self.rules:
            if extension in RANSOMWARE_EXTENSIONS:
                cfg = self.rules["renombrado_extension_anomala"]
                self._rename_events.append(now)
                self._prune(self._rename_events, cfg["window_seconds"], now)
                if len(self._rename_events) >= cfg["threshold"]:
                    matched.append("renombrado_extension_anomala")

        if event_type == "file_deleted" and "eliminacion_anomala_archivos" in self.rules:
            cfg = self.rules["eliminacion_anomala_archivos"]
            self._deletion_events.append(now)
            self._prune(self._deletion_events, cfg["window_seconds"], now)
            if len(self._deletion_events) >= cfg["threshold"]:
                matched.append("eliminacion_anomala_archivos")

        if event_type == "file_created" and "creacion_masiva_temporales" in self.rules and _is_temp_path(file_path):
            cfg = self.rules["creacion_masiva_temporales"]
            self._temp_events.append(now)
            self._prune(self._temp_events, cfg["window_seconds"], now)
            if len(self._temp_events) >= cfg["threshold"]:
                matched.append("creacion_masiva_temporales")

        if "acceso_recursos_compartidos" in self.rules and _is_shared_path(file_path):
            cfg = self.rules["acceso_recursos_compartidos"]
            self._shared_events.append(now)
            self._prune(self._shared_events, cfg["window_seconds"], now)
            if len(self._shared_events) >= cfg["threshold"]:
                matched.append("acceso_recursos_compartidos")

        if "actividad_archivos_usuario" in self.rules and _is_user_path(file_path):
            cfg = self.rules["actividad_archivos_usuario"]
            self._user_events.append(now)
            self._prune(self._user_events, cfg["window_seconds"], now)
            if len(self._user_events) >= cfg["threshold"]:
                matched.append("actividad_archivos_usuario")

        return matched

    def get_unique_file_count(self):
        """Solo para logging (impresión en consola del agente) --
        cuántos archivos únicos modificados hay en la ventana de
        HR-01 ahora mismo."""

        cfg = self.rules.get("modificacion_masiva_archivos")
        if not cfg:
            return 0
        now = time()
        self._prune(self._modified_events, cfg["window_seconds"], now, key=True)
        return len({p for _, p in self._modified_events})
