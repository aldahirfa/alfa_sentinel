from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from heuristic_engine import FileActivityAnalyzer

from honeyfile_monitor import HoneyfileMonitor

from client import send_event, send_alert

from adapters import get_process_for_file_event, open_files_index, enrich_pid

from isolation_executor import execute_isolation

import os
import queue
import threading
import time

# Deduplicación de "eventos técnicos" (2026-08-18, ver PENDIENTES.md,
# "Revisión y corrección integral de ALFA-Sentinel", problema B):
# investigado ANTES de tocar código, tal como pidió la especificación --
# esto es un comportamiento real y documentado de aplicaciones de
# escritorio (Office en particular), no un defecto de watchdog ni del
# agente: guardar un archivo UNA vez puede generar más de un evento de
# filesystem real (reescritura del mismo archivo dos veces seguidas,
# o el patrón "escribir temporal -> borrar original -> renombrar").
#
# La telemetría cruda ('events' en la base) NO se toca por esto -- cada
# evento real se sigue reportando tal cual vía send_event() más abajo,
# ANTES de este chequeo (sección B: "no eliminar eventos reales del
# registro solo para que la consola se vea mejor"). Lo que sí se evita es
# que DOS notificaciones técnicas casi simultáneas del mismo
# (ruta, tipo de evento) -- casi siempre la misma acción real del
# usuario, no dos acciones distintas -- lleguen dos veces al motor
# heurístico y cuenten como dos operaciones separadas hacia un umbral
# (Escritura Intensiva, Actividad Repetitiva Automatizada, etc.).
#
# Se implementa ACÁ, no dentro de FileActivityAnalyzer.register_event()
# (agent/heuristic_engine.py) -- a propósito: esa clase es una función
# determinista de la secuencia de eventos que recibe, y así la prueba
# tests/heuristic/test_file_rules_regression.py, que verifica
# explícitamente que HR-04 cuenta OPERACIONES totales (no archivos
# únicos) llamando register_event() varias veces seguidas sobre el MISMO
# archivo sin ninguna pausa real -- deduplicar por tiempo transcurrido
# ahí adentro habría roto esa prueba y el contrato que ya prueba
# (sección "NO rompas la lógica existente"). Acá, en cambio, SÍ hay
# tiempo real entre eventos de watchdog (a diferencia de un test
# sintético en bucle), así que acá es donde corresponde decidir si dos
# eventos consecutivos son, en la práctica, la misma acción técnica.
#
# 2.0s es conservador: separa "ruido técnico del mismo guardado"
# (típicamente milisegundos) de una repetición real y deliberada sobre
# el mismo archivo (que sí debe seguir contando aparte).
DEDUP_WINDOW_SECONDS = 2.0

# Corrección 2026-10-05 -- por qué las reglas "no detectaban nada":
# antes, por CADA evento, el hilo de watchdog buscaba el proceso
# responsable recorriendo todos los procesos (psutil.open_files(),
# medido en Windows: ~18 s por evento) y además hacía un POST al
# servidor, y recién después evaluaba las reglas con time() de ESE
# momento. Con 18 s por evento, 20 borrados nunca caían dentro de los
# 15 s de HR-09, aunque hubieran ocurrido en 1 segundo.
#
# Ahora:
#  1. Las reglas que dependen solo de la ruta (HR-01/02/03/04/07/08/09/10)
#     se evalúan en el acto, con el momento real del evento.
#  2. La atribución de proceso (HR-05/HR-11) y la telemetría van a un
#     hilo aparte que procesa los eventos por lotes: un solo recorrido
#     de procesos para todo el lote, y las reglas de proceso se evalúan
#     con el momento real de cada evento.
#  3. Las alertas salen por un tercer hilo, para no quedar detrás de la
#     telemetría ni de la atribución.
#
# Un evento con más de ATTRIBUTION_MAX_AGE_SECONDS en la cola ya no se
# intenta atribuir con el recorrido de psutil: el proceso casi seguro
# ya cerró el archivo y el resultado sería engañoso.
ATTRIBUTION_MAX_AGE_SECONDS = 30.0

# Ver FileActivityHandler._isolate_now: no repetir el aislamiento local por
# cada archivo de una misma ráfaga.
LOCAL_ISOLATION_COOLDOWN_SECONDS = 60.0


class FileActivityHandler(FileSystemEventHandler):

    def __init__(self, analyzer, honeyfile_monitor, credential):

        self.analyzer = analyzer
        self.honeyfile_monitor = honeyfile_monitor
        self.credential = credential
        self._last_technical_event = {}  # (file_path, event_type) -> último timestamp real

        self._isolation_lock = threading.Lock()
        self._last_local_isolation = 0.0

        self._event_queue = queue.Queue()  # (file_path, event_type, timestamp, evaluar_proceso)
        self._alert_queue = queue.Queue()  # payloads para send_alert

        threading.Thread(target=self._attribution_loop, name="alfa-atribucion", daemon=True).start()
        threading.Thread(target=self._alert_loop, name="alfa-alertas", daemon=True).start()

    def _is_technical_duplicate(self, file_path, event_type):
        """Ver DEDUP_WINDOW_SECONDS arriba. Actualiza el registro en
        cada llamada (no solo cuando devuelve True), así que una ráfaga
        de eventos técnicos seguidos del mismo guardado cuenta como UNA
        sola operación real, no una cada DEDUP_WINDOW_SECONDS."""
        now = time.time()
        key = (file_path, event_type)
        last = self._last_technical_event.get(key)
        self._last_technical_event[key] = now
        return last is not None and (now - last) <= DEDUP_WINDOW_SECONDS


    # Títulos/descripciones legibles por regla -- el título es fijo por
    # regla (no generado dinámicamente a partir de datos que no
    # tenemos, como proceso o usuario). El score, la severidad y qué
    # reglas participaron (con su peso real) los calcula y registra el
    # SERVIDOR (ver server/main.py::report_alert) a partir de la lista
    # 'matched_rules' que se manda acá -- el agente ya no decide
    # severidad ni risk_score (sección 1 de la especificación del
    # motor heurístico: separar detección de cálculo de riesgo).
    # Claves iguales a las de heuristic_engine.RULE_NAMES/DEFAULT_RULES
    # (coinciden con 'heuristic_rules.name' en la base real, ver
    # comentario en heuristic_engine.py) -- si cambian ahí, cambian acá.
    RULE_TITLES = {
        "Modificacion Masiva Archivos": "Modificación masiva de archivos",
        "Renombrado Extension Anomala": "Renombrado con extensión de ransomware conocida",
        "Acceso Honeyfile": "Honeyfile activado",
        "Escritura Intensiva Archivos": "Escritura intensiva de archivos",
        "Proceso Sospechoso": "Proceso sospechoso detectado",
        "Acceso Recursos Compartidos": "Acceso masivo a recursos compartidos",
        "Creacion Masiva Temporales": "Creación masiva de archivos temporales",
        "Eliminacion Anomala Archivos": "Eliminación anómala de archivos",
        "Actividad Archivos Usuario": "Actividad repetitiva sobre archivos de usuario",
        "Actividad Repetitiva Automatizada": "Actividad automatizada del mismo proceso",
    }

    def register_file_event(self, file_path, event_type, honeyfile_hit=False):
        """'honeyfile_hit' (2026-08-17, ver PENDIENTES.md, "Honeyfiles +
        monitorización completa del endpoint..."): permite forzar que
        ESTE evento cuente como interacción con un honeyfile incluso si
        'file_path' (el nombre reportado, sección 12) no está en
        known_paths -- necesario para renombrados externos (test H5:
        "Proceso externo renombra honeyfile -> HR-03"): si el archivo
        VIEJO era un honeyfile, el evento (que se reporta con el
        nombre NUEVO, ver on_moved) sigue siendo una interacción con un
        honeyfile, aunque el nombre nuevo ya no lo sea."""

        # Momento REAL del evento (ver ATTRIBUTION_MAX_AGE_SECONDS arriba):
        # se toma antes de cualquier trabajo lento y es el que usan
        # todas las ventanas de las reglas.
        timestamp = time.time()

        extension = os.path.splitext(file_path)[1].lower()

        print(
            f"Archivo: {file_path}"
        )

        print(
            f"Extensión: {extension}"
        )

        # Comprobar honeyfile ANTES de evaluar reglas: HR-03 es
        # inmediata (sección 12 de la especificación), no depende de
        # ninguna ventana ni se acumula con las demás reglas.
        is_honeyfile = self.honeyfile_monitor.is_honeyfile(file_path) or honeyfile_hit

        # Exclusión de actividad interna del agente (sección 22/34 de
        # la especificación de monitorización completa, 2026-08-17):
        # si ESTE MISMO agente acaba de crear/recrear este honeyfile
        # (agent/honeyfile_deployer.py, durante el despliegue o la
        # reconciliación periódica), el evento de watchdog que llega
        # ahora no es una interacción externa -- no debe activar HR-03.
        # El evento se sigue mandando igual y las demás reglas se siguen
        # evaluando igual -- solo se fuerza is_honeyfile=False para ESTA
        # evaluación puntual.
        if is_honeyfile and self.honeyfile_monitor.is_internal_operation(file_path):

            print(f"(actividad interna del agente sobre este honeyfile -- HR-03 no se evalúa: {file_path})")
            is_honeyfile = False

        elif is_honeyfile:

            print()
            print("⚠ HONEYFILE ACTIVADO")
            print(f"Archivo: {file_path}")
            print()

        # Deduplicación de eventos técnicos (ver DEDUP_WINDOW_SECONDS al
        # inicio del módulo, problema B, 2026-08-18): si ESTE MISMO
        # (file_path, event_type) ya se vio hace menos de
        # DEDUP_WINDOW_SECONDS, se trata como la misma acción técnica de
        # un solo guardado real -- no se vuelve a evaluar contra el motor
        # heurístico una segunda vez (evita inflar artificialmente
        # umbrales como Escritura Intensiva Archivos o Actividad
        # Repetitiva Automatizada). El evento se reporta igual a
        # /agent/events -- la telemetría cruda no se pierde, solo se
        # evita contarlo dos veces hacia un umbral.
        if self._is_technical_duplicate(file_path, event_type):
            print(f"(evento técnico duplicado del mismo guardado -- no se reevalúa el motor heurístico: {file_path})")
            matched_rules = []
            evaluate_process = False
        else:
            matched_rules = self.analyzer.register_event(
                file_path, event_type, is_honeyfile=is_honeyfile, timestamp=timestamp
            )
            evaluate_process = True

        file_count = self.analyzer.get_unique_file_count()

        print(
            f"Archivos únicos afectados en ventana (HR-01): "
            f"{file_count}"
        )

        # Corregido 2026-08-18 (ver PENDIENTES.md, "Revisión y corrección
        # integral de ALFA-Sentinel", problema A): se imprimen dos números
        # separados y sin ambigüedad: cuántas reglas tiene cargadas el
        # motor (constante mientras el agente corre) y cuántas de esas
        # coincidieron con ESTE evento (variable, normalmente 0).
        print(f"Reglas evaluadas: {len(self.analyzer.rules)}")
        print(
            f"Reglas coincidentes con este evento: "
            f"{', '.join(matched_rules) if matched_rules else 'ninguna'}"
        )

        if matched_rules:
            if "Acceso Honeyfile" in matched_rules:
                self._isolate_now()
            self._queue_alert(matched_rules, file_count)

        # Atribución de proceso (HR-05/HR-11) y telemetría: en el hilo de
        # atribución, para no frenar la evaluación de los eventos que
        # siguen llegando.
        self._event_queue.put((file_path, event_type, extension, timestamp, evaluate_process))

    def _isolate_now(self):
        """Aislamiento local inmediato al tocar un honeyfile (2026-10-06).
        Antes se esperaba la orden del servidor (hasta ~15 s, el intervalo
        de isolation_sync.py) y un ransomware rápido puede terminar el
        agente en ese tiempo. El servidor igual ordena el aislamiento por
        su lado (HR-03 vale 100 -> CRÍTICO); al recibir esa orden el agente
        la vuelve a aplicar (es idempotente) y confirma el resultado, y la
        liberación sigue siendo desde la consola."""

        now = time.time()
        with self._isolation_lock:
            if now - self._last_local_isolation < LOCAL_ISOLATION_COOLDOWN_SECONDS:
                return
            self._last_local_isolation = now

        def run():
            print("⚠ HONEYFILE ACTIVADO -- aislando el equipo de inmediato, sin esperar al servidor...")
            ok, detail = execute_isolation("NETWORK")
            print(f"{'✓' if ok else '✗'} Aislamiento local: {detail}")

        threading.Thread(target=run, name="alfa-aislamiento-local", daemon=True).start()

    def _queue_alert(self, matched_rules, file_count):
        """El agente no decide severidad/score/título compuesto: manda
        TODAS las reglas que coincidieron y el servidor calcula peso,
        correlación, score y severidad a partir de heuristic_rules (ver
        server/main.py::report_alert). 'title'/'description' son solo un
        resumen legible para el caso en que el servidor tenga que generar
        una alerta nueva -- si actualiza una existente, conserva su propio
        título."""

        print(
            "¡ACTIVIDAD SOSPECHOSA DETECTADA!"
        )

        primary_rule = matched_rules[0]

        self._alert_queue.put({
            "title": self.RULE_TITLES.get(primary_rule, "Actividad de archivos sospechosa"),
            "description": (
                f"{file_count} archivos únicos modificados en la ventana de HR-01; "
                f"reglas coincidentes: {', '.join(matched_rules)}"
            ),
            "matched_rules": matched_rules
        })

    def _alert_loop(self):
        while True:
            alert = self._alert_queue.get()
            try:
                send_alert(self.credential, alert)
            except Exception as error:
                print(f"⚠ No se pudo enviar la alerta: {error}")

    def _attribution_loop(self):
        while True:
            batch = [self._event_queue.get()]
            while True:
                try:
                    batch.append(self._event_queue.get_nowait())
                except queue.Empty:
                    break
            try:
                self._process_batch(batch)
            except Exception as error:
                print(f"⚠ Error procesando eventos de archivo en segundo plano: {error}")

    def _process_batch(self, batch):
        """Enriquecimiento de eventos (2026-08-16, ver PENDIENTES.md):
        intenta identificar qué proceso tocó cada archivo
        (agent/adapters/) -- best-effort, honesto: si no se puede
        determinar, process_info queda en None y el evento se reporta
        igual, sin inventar process_id/process_name (sección 8 de la
        especificación).

        Primero el mecanismo nativo (ETW/fanotify), que es inmediato. Si
        no alcanza, UN solo recorrido de psutil para todo el lote. Un
        archivo borrado ya no puede estar abierto, así que los borrados
        no disparan ese recorrido."""

        started = time.time()
        index = None

        for file_path, event_type, extension, timestamp, evaluate_process in batch:

            process_info = get_process_for_file_event(file_path, event_type, allow_scan=False)

            if (
                process_info is None
                and event_type != "file_deleted"
                and started - timestamp <= ATTRIBUTION_MAX_AGE_SECONDS
            ):
                if index is None:
                    index = open_files_index()
                pid = index.get(os.path.normcase(os.path.abspath(file_path)))
                process_info = enrich_pid(pid) if pid is not None else None

            if process_info:
                print(
                    f"Proceso atribuido: PID {process_info.get('process_id')} "
                    f"({process_info.get('process_name')}, usuario: {process_info.get('username') or '—'}) "
                    f"-> {file_path}"
                )

            if process_info and evaluate_process:
                matched_rules = self.analyzer.register_process_event(process_info, timestamp)
                if matched_rules:
                    print(f"Reglas coincidentes con este evento: {', '.join(matched_rules)} ({file_path})")
                    self._queue_alert(matched_rules, self.analyzer.get_unique_file_count())

            # Reportar el evento crudo al servidor (tabla 'events').
            # 'executable_path' y 'username' no viajan acá -- 'events' no
            # tiene columnas para eso (quedan como información interna
            # del agente, usadas para evaluar HR-05 y para el log);
            # process_id/process_name sí.
            send_event(
                self.credential,
                {
                    "event_type": event_type,
                    "description": f"{event_type} en {file_path}",
                    "process_id": process_info.get("process_id") if process_info else None,
                    "process_name": process_info.get("process_name") if process_info else None,
                    "metadata": {
                        "file_path": file_path,
                        "extension": extension
                    }
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
            # particular para la regla "Renombrado Extension Anomala": si
            # se mira la extensión del nombre VIEJO, un rename a
            # "informe.docx.locked" nunca se detectaría porque la
            # extensión sospechosa está en el nombre nuevo.
            #
            # Para HR-03 es al revés (2026-08-17, ver PENDIENTES.md,
            # "Honeyfiles + monitorización completa del endpoint..." --
            # test H5, "proceso externo renombra honeyfile -> HR-03"):
            # si el nombre VIEJO era un honeyfile conocido, esto sigue
            # siendo una interacción con un honeyfile aunque el nombre
            # nuevo no esté en known_paths -- se consulta ANTES de
            # reportar, porque is_honeyfile() depende de known_paths,
            # que no cambia solo porque el archivo se renombró.
            source_was_honeyfile = self.honeyfile_monitor.is_honeyfile(event.src_path)

            self.register_file_event(event.dest_path, "file_renamed", honeyfile_hit=source_was_honeyfile)


def watch_extra_directory(observer, event_handler, file_path, watched_roots, watched_extra_dirs):
    """Agrega al Observer, sin reiniciarlo, la carpeta que contiene
    'file_path' -- salvo que ya esté cubierta por el watch recursivo de
    alguna de 'watched_roots' o ya se haya agregado antes (evita
    duplicar el mismo watch dos veces, lo que watchdog permite pero
    solo generaría eventos repetidos).

    'watched_roots' es una lista (2026-08-17, ver PENDIENTES.md,
    "Honeyfiles + monitorización completa del endpoint..." -- antes
    era una sola carpeta raíz, ahora el agente vigila varias raíces
    globales a la vez, ver get_monitored_roots() en agent/paths.py).
    En la práctica, con ALFA_ARCHIVOS anidado dentro de una ruta lógica
    ya vigilada (Documents, Desktop, ...), esta función casi nunca
    encuentra una carpeta sin cubrir -- sigue existiendo para
    plantillas viejas con una ruta libre (formato legado, ver
    agent/paths.py::resolve_logical_path) que caiga fuera de las
    raíces monitorizadas.

    Extraído como función reusable (2026-08-17) porque ya no es algo
    que se resuelve una sola vez al arrancar: agent/honeyfile_sync.py
    la llama en cada ciclo de sincronización cuando aparece un
    honeyfile nuevo en una carpeta todavía no vigilada, sin necesidad
    de reiniciar el agente."""

    directory = os.path.dirname(os.path.abspath(file_path))

    if not directory or directory in watched_extra_dirs:
        return

    if any(directory.startswith(root) for root in watched_roots):
        return

    if os.path.isdir(directory):

        observer.schedule(
            event_handler,
            directory,
            recursive=False
        )

        watched_extra_dirs.add(directory)

        print(f"Vigilando también: {directory}")


def start_file_monitor(monitored_roots, credential, known_honeyfile_paths=None, rule_policy=None):
    """'monitored_roots': lista de carpetas a vigilar de forma
    recursiva -- ya NO es una sola carpeta de trabajo del agente
    (sección 3/26/40 de la especificación de monitorización completa,
    2026-08-17: "el agente debe monitorizar TODO el endpoint... NO
    solamente ALFA_ARCHIVOS"). Normalmente es el resultado de
    agent/paths.py::get_monitored_roots() -- Documents/Desktop/
    Downloads/Pictures/Videos/Music (reales en producción, carpetas de
    prueba dedicadas en desarrollo)."""

    # 'rule_policy' es la lista 'rules' que devuelve GET /agent/rule-policy
    # (ver agent/main.py, agent/client.py::get_rule_policy) -- la
    # política EFECTIVA ya resuelta por el servidor (global + override
    # de agent_rule para este agente). None (no lista vacía) significa
    # "no se pudo ni pedir" -- ver FileActivityAnalyzer.from_policy.
    analyzer = FileActivityAnalyzer.from_policy(rule_policy)

    honeyfile_monitor = HoneyfileMonitor(
        known_paths=known_honeyfile_paths
    )

    event_handler = FileActivityHandler(
        analyzer,
        honeyfile_monitor,
        credential
    )

    observer = Observer()

    watched_roots = [os.path.abspath(root) for root in monitored_roots]

    for root in watched_roots:
        observer.schedule(
            event_handler,
            root,
            recursive=True
        )
        print(f"Vigilando: {root}")

    # Los honeyfiles desplegados por plantilla (agent/honeyfile_deployer.py)
    # pueden, en configuraciones legado, vivir fuera de las carpetas
    # anteriores -- sin esto, watchdog nunca vería actividad ahí. Con
    # ALFA_ARCHIVOS anidado dentro de una ruta lógica ya vigilada, esto
    # en la práctica ya no agrega nada para plantillas nuevas -- ver
    # watch_extra_directory().
    watched_extra_dirs = set()

    for honeyfile_path in (known_honeyfile_paths or []):
        watch_extra_directory(observer, event_handler, honeyfile_path, watched_roots, watched_extra_dirs)

    observer.start()

    # Se devuelven también 'analyzer' (agent/main.py lo usa para leer
    # la configuración YA RESUELTA de reglas que no se evalúan acá, ej.
    # "Consumo CPU Elevado", ver cpu_monitor.py), 'honeyfile_monitor' y
    # 'watched_extra_dirs' (agent/honeyfile_sync.py los necesita para
    # sumar honeyfiles nuevos sin reiniciar el observer, ver ese
    # módulo) y 'watched_roots' (para saber si una carpeta nueva ya
    # está cubierta por algún watch recursivo, sin volver a calcularlo).
    return observer, analyzer, honeyfile_monitor, event_handler, watched_roots, watched_extra_dirs
