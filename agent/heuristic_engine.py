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


# Carpetas donde suele vivir software instalado "legítimamente" -- para
# HR-05 (sección 7 de la especificación de implementación final:
# "ejecución desde directorios temporales; ejecución desde ubicaciones
# de usuario; rutas no habituales"). Es una aproximación honesta, no
# una lista blanca exhaustiva de todo lo legítimo que puede existir en
# un equipo real -- un proceso legítimo instalado en una ruta rara
# puede generar un falso positivo, y uno malicioso copiado a
# Program Files no se detectaría por esta señal sola. Por eso HR-05 es
# una heurística de peso bajo (10, ver database/schema.sql), no una
# afirmación categórica.
STANDARD_PROGRAM_MARKERS = {
    "program files", "program files (x86)", "windows", "system32", "syswow64",
    "usr", "bin", "sbin", "opt", "lib", "lib64",
}


def _is_suspicious_executable_path(executable_path):
    """HR-05: ¿el EJECUTABLE del proceso responsable corre desde una
    ubicación atípica? Reutiliza los mismos marcadores de "temporal" y
    "carpeta de usuario" que ya se usan para HR-08/HR-10 sobre el
    archivo tocado, pero acá se aplican sobre la ruta del proceso, no
    sobre la del archivo -- son preguntas distintas ("¿qué tocaron?"
    vs. "¿desde dónde corre quien lo tocó?")."""

    if not executable_path:
        return False
    if _is_temp_path(executable_path) or _is_user_path(executable_path):
        return True
    parts = {p.lower() for p in executable_path.replace("\\", "/").split("/") if p}
    return not bool(parts & STANDARD_PROGRAM_MARKERS)


# Nombres de regla que el AGENTE puede evaluar con los datos que
# recopila hoy (ruta + tipo de evento, y desde el 2026-08-16 también
# atribución de proceso vía agent/adapters/ y muestreo de CPU vía
# agent/cpu_monitor.py -- ver PENDIENTES.md, "Implementación
# final del motor heurístico y configuración por endpoint"). Deben
# coincidir EXACTO (case-sensitive) con el valor real de
# 'heuristic_rules.name' en tu base -- no con lo que trae
# database/schema.sql por defecto necesariamente, sino con lo que la
# base tenga cargado de verdad.
#
# "Correlacion Multiples Indicadores" (HR-12) no está acá: la calcula
# el servidor, no el agente (sección 20 de la especificación).
RULE_NAMES = {
    "Modificacion Masiva Archivos",
    "Renombrado Extension Anomala",
    "Acceso Honeyfile",
    "Escritura Intensiva Archivos",
    "Proceso Sospechoso",
    "Consumo CPU Elevado",
    "Acceso Recursos Compartidos",
    "Creacion Masiva Temporales",
    "Eliminacion Anomala Archivos",
    "Actividad Archivos Usuario",
    "Actividad Repetitiva Automatizada",
}

# Valores por defecto -- exactamente los que siembra database/schema.sql
# para cada regla. Se usan si el servidor no contestó GET
# /agent/rule-policy (problema de red no debe dejar al agente sin
# detectar nada, solo sin la última configuración editada desde
# /configuracion).
DEFAULT_RULES = {
    "Modificacion Masiva Archivos":     {"threshold": 20, "window_seconds": 10},
    "Renombrado Extension Anomala":     {"threshold": 5,  "window_seconds": 15},
    "Acceso Honeyfile":                 {"threshold": 1,  "window_seconds": None},
    "Escritura Intensiva Archivos":     {"threshold": 50, "window_seconds": 10},
    "Proceso Sospechoso":               {"threshold": 1,  "window_seconds": 30},
    "Consumo CPU Elevado":              {"threshold": 80, "window_seconds": 10},
    "Acceso Recursos Compartidos":      {"threshold": 20, "window_seconds": 15},
    "Creacion Masiva Temporales":       {"threshold": 30, "window_seconds": 15},
    "Eliminacion Anomala Archivos":     {"threshold": 20, "window_seconds": 15},
    "Actividad Archivos Usuario":       {"threshold": 30, "window_seconds": 20},
    "Actividad Repetitiva Automatizada": {"threshold": 40, "window_seconds": 15},
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
        self._suspicious_process_events = deque()  # timestamps -- HR-05
        self._process_activity = {}       # pid -> deque(timestamps) -- HR-11, UNA ventana por proceso

    @classmethod
    def from_policy(cls, policy_rules):
        """policy_rules: lista de dicts {name, weight, threshold,
        window_seconds} que devuelve GET /agent/rule-policy -- YA es
        la política EFECTIVA (heuristic_rules + override de agent_rule
        para este agente, sección 5/6 de la especificación de
        implementación final), y ya viene filtrada a solo las reglas
        cuyo is_active efectivo es TRUE. Cualquier nombre que el
        agente no sepa evaluar (ej. "Correlacion Multiples
        Indicadores", que calcula el servidor) se ignora sin romper
        nada.

        'policy_rules' es None -- a propósito, DISTINTO de una lista
        vacía -- cuando no se pudo ni siquiera contactar al servidor
        (problema de red): ahí sí se cae por completo a DEFAULT_RULES
        para no dejar al agente sin detectar nada (sección 6: "valores
        de respaldo para continuidad operativa"). Si el servidor SÍ
        contestó pero la lista viene vacía o sin alguna regla puntual,
        eso es una respuesta real ("esta regla está desactivada para
        este endpoint") y se respeta tal cual -- no se completa con el
        valor por defecto de esa regla, porque eso sería el agente
        manteniendo su propia configuración en paralelo a la de la
        base (sección 6: "no mantener una segunda configuración manual
        para cada regla")."""

        if policy_rules is None:
            return cls(rules=dict(DEFAULT_RULES))

        rules = {}

        for row in policy_rules:
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

    def register_event(self, file_path, event_type, is_honeyfile=False, process_info=None):
        """Registra un evento de archivo y devuelve la lista de
        nombres de regla que están activas justo después de
        incorporarlo (puede ser más de una a la vez, ej. borrado
        masivo + actividad de usuario). No multiplica el peso por
        cantidad de eventos -- el llamador (file_monitor.py) decide
        qué hacer con la lista, y el peso real lo aplica el servidor.

        'process_info' (2026-08-16): {"process_id", "process_name",
        "executable_path"} si agent/adapters/ pudo atribuir el proceso
        responsable de este evento, o None si no se pudo determinar
        (ver PENDIENTES.md -- limitación honesta, no se inventa).
        Habilita HR-05 (Proceso Sospechoso) y HR-11 (Actividad
        Repetitiva Automatizada); si es None, ambas reglas
        simplemente no evalúan nada para este evento puntual -- no
        se cuenta como "no sospechoso", no hay dato."""

        now = time()
        matched = []

        # HR-03: inmediata, sin ventana ni acumulación -- cualquier
        # interacción con un honeyfile es suficiente (sección 12 de la
        # especificación).
        if is_honeyfile and "Acceso Honeyfile" in self.rules:
            matched.append("Acceso Honeyfile")

        extension = os.path.splitext(file_path)[1].lower()

        if event_type == "file_modified":
            if "Modificacion Masiva Archivos" in self.rules:
                cfg = self.rules["Modificacion Masiva Archivos"]
                self._modified_events.append((now, file_path))
                self._prune(self._modified_events, cfg["window_seconds"], now, key=True)
                unique_files = {p for _, p in self._modified_events}
                if len(unique_files) >= cfg["threshold"]:
                    matched.append("Modificacion Masiva Archivos")

            if "Escritura Intensiva Archivos" in self.rules:
                cfg = self.rules["Escritura Intensiva Archivos"]
                self._write_events.append(now)
                self._prune(self._write_events, cfg["window_seconds"], now)
                if len(self._write_events) >= cfg["threshold"]:
                    matched.append("Escritura Intensiva Archivos")

        if event_type == "file_renamed" and "Renombrado Extension Anomala" in self.rules:
            if extension in RANSOMWARE_EXTENSIONS:
                cfg = self.rules["Renombrado Extension Anomala"]
                self._rename_events.append(now)
                self._prune(self._rename_events, cfg["window_seconds"], now)
                if len(self._rename_events) >= cfg["threshold"]:
                    matched.append("Renombrado Extension Anomala")

        if event_type == "file_deleted" and "Eliminacion Anomala Archivos" in self.rules:
            cfg = self.rules["Eliminacion Anomala Archivos"]
            self._deletion_events.append(now)
            self._prune(self._deletion_events, cfg["window_seconds"], now)
            if len(self._deletion_events) >= cfg["threshold"]:
                matched.append("Eliminacion Anomala Archivos")

        if event_type == "file_created" and "Creacion Masiva Temporales" in self.rules and _is_temp_path(file_path):
            cfg = self.rules["Creacion Masiva Temporales"]
            self._temp_events.append(now)
            self._prune(self._temp_events, cfg["window_seconds"], now)
            if len(self._temp_events) >= cfg["threshold"]:
                matched.append("Creacion Masiva Temporales")

        if "Acceso Recursos Compartidos" in self.rules and _is_shared_path(file_path):
            cfg = self.rules["Acceso Recursos Compartidos"]
            self._shared_events.append(now)
            self._prune(self._shared_events, cfg["window_seconds"], now)
            if len(self._shared_events) >= cfg["threshold"]:
                matched.append("Acceso Recursos Compartidos")

        if "Actividad Archivos Usuario" in self.rules and _is_user_path(file_path):
            cfg = self.rules["Actividad Archivos Usuario"]
            self._user_events.append(now)
            self._prune(self._user_events, cfg["window_seconds"], now)
            if len(self._user_events) >= cfg["threshold"]:
                matched.append("Actividad Archivos Usuario")

        # HR-05: requiere haber podido atribuir el proceso responsable
        # de este evento (process_info no es None) -- sin eso no hay
        # ruta de ejecutable que evaluar.
        if process_info and "Proceso Sospechoso" in self.rules:
            if _is_suspicious_executable_path(process_info.get("executable_path")):
                cfg = self.rules["Proceso Sospechoso"]
                self._suspicious_process_events.append(now)
                self._prune(self._suspicious_process_events, cfg["window_seconds"], now)
                if len(self._suspicious_process_events) >= cfg["threshold"]:
                    matched.append("Proceso Sospechoso")

        # HR-11: EL MISMO proceso (por process_id) con muchas
        # operaciones de archivo dentro de la ventana -- a diferencia
        # de HR-01/HR-04, que cuentan actividad del endpoint completo
        # sin distinguir quién la generó. También requiere process_info.
        if process_info and "Actividad Repetitiva Automatizada" in self.rules:
            pid = process_info.get("process_id")
            if pid is not None:
                cfg = self.rules["Actividad Repetitiva Automatizada"]
                pid_events = self._process_activity.setdefault(pid, deque())
                pid_events.append(now)
                self._prune(pid_events, cfg["window_seconds"], now)
                if len(pid_events) >= cfg["threshold"]:
                    matched.append("Actividad Repetitiva Automatizada")
                # Nota: 'self._process_activity' acumula una entrada
                # por cada PID distinto que alguna vez tocó un archivo
                # -- no se podan los PIDs que dejaron de aparecer
                # (solo se podan sus timestamps viejos si vuelven a
                # aparecer). Con la arquitectura actual del agente
                # (proceso de una sola pasada, ver agent/main.py --
                # arranca, monitorea, se detiene con ENTER, no es un
                # daemon de días/semanas) esto no llega a ser un
                # problema real de memoria. Si el agente pasara a
                # correr como servicio de larga duración, acá haría
                # falta un barrido periódico de PIDs inactivos.

        return matched

    def get_unique_file_count(self):
        """Solo para logging (impresión en consola del agente) --
        cuántos archivos únicos modificados hay en la ventana de
        HR-01 ahora mismo."""

        cfg = self.rules.get("Modificacion Masiva Archivos")
        if not cfg:
            return 0
        now = time()
        self._prune(self._modified_events, cfg["window_seconds"], now, key=True)
        return len({p for _, p in self._modified_events})
