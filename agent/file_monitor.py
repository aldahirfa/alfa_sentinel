from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from heuristic_engine import FileActivityAnalyzer

from honeyfile_monitor import HoneyfileMonitor

from client import send_event, send_alert

from adapters import get_process_for_file_event

import os
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


class FileActivityHandler(FileSystemEventHandler):

    def __init__(self, analyzer, honeyfile_monitor, credential):

        self.analyzer = analyzer
        self.honeyfile_monitor = honeyfile_monitor
        self.credential = credential
        self._last_technical_event = {}  # (file_path, event_type) -> último timestamp real

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

        extension = os.path.splitext(file_path)[1].lower()

        print(
            f"Archivo: {file_path}"
        )

        print(
            f"Extensión: {extension}"
        )

        # Enriquecimiento de eventos (2026-08-16, ver PENDIENTES.md):
        # intenta identificar qué proceso tiene este archivo abierto
        # AHORA MISMO (agent/adapters/) -- best-effort, honesto: si no
        # se puede determinar (el proceso ya cerró el archivo, o no
        # hay permisos para inspeccionarlo), process_info queda en
        # None y el evento se reporta igual, sin inventar
        # process_id/process_name (sección 8 de la especificación).
        process_info = get_process_for_file_event(file_path, event_type)

        if process_info:
            print(
                f"Proceso atribuido: PID {process_info.get('process_id')} "
                f"({process_info.get('process_name')}, usuario: {process_info.get('username') or '—'})"
            )

        # Reportar el evento crudo al servidor (tabla 'events'). Antes
        # esto capturaba el event_id de la respuesta para vincular la
        # alerta a los eventos que la dispararon (tabla 'alert_events'),
        # pero esa tabla no existe en la nueva estructura (alfa_sentinel)
        # -- ver PENDIENTES.md. Se sigue mandando el evento igual, solo
        # que ya no se hace nada con el id de vuelta. 'executable_path'
        # y 'username' (agregado 2026-08-16 a la salida de los
        # adaptadores) no viajan acá -- 'events' no tiene columnas para
        # eso (sección 10 de la especificación de atribución: "no
        # cambiar la estructura de la BD solamente para satisfacer esta
        # tarea"; quedan como información interna del agente, usadas
        # solo para evaluar HR-05 y para el log en consola);
        # process_id/process_name sí, esas columnas ya existían.
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
        # El evento se sigue mandando igual (línea de abajo) y las
        # demás reglas se siguen evaluando igual -- solo se fuerza
        # is_honeyfile=False para ESTA evaluación puntual.
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
        # Repetitiva Automatizada). El evento YA se reportó tal cual a
        # /agent/events arriba -- la telemetría cruda no se pierde, solo
        # se evita contarlo dos veces hacia un umbral.
        if self._is_technical_duplicate(file_path, event_type):
            print(f"(evento técnico duplicado del mismo guardado -- no se reevalúa el motor heurístico: {file_path})")
            matched_rules = []
        else:
            matched_rules = self.analyzer.register_event(
                file_path, event_type, is_honeyfile=is_honeyfile, process_info=process_info
            )

        file_count = self.analyzer.get_unique_file_count()

        print(
            f"Archivos únicos afectados en ventana (HR-01): "
            f"{file_count}"
        )

        # Corregido 2026-08-18 (ver PENDIENTES.md, "Revisión y corrección
        # integral de ALFA-Sentinel", problema A): la línea anterior decía
        # solo "Reglas activas: ninguna" cuando NINGUNA regla cruzó su
        # umbral con ESTE evento puntual -- lo normal en la inmensa
        # mayoría de los eventos individuales (la mayoría de las reglas
        # requieren varios eventos dentro de una ventana, ej. 20 archivos
        # en 10s). Esa frase se confundía con "no hay reglas cargadas",
        # que es un problema completamente distinto (y que, de existir,
        # ya se reportaría al arrancar el agente -- ver agent/main.py).
        # Ahora se imprimen dos números separados y sin ambigüedad: cuántas
        # reglas tiene cargadas el motor (constante mientras el agente
        # corre) y cuántas de esas coincidieron con ESTE evento (variable,
        # normalmente 0).
        print(f"Reglas evaluadas: {len(self.analyzer.rules)}")
        print(
            f"Reglas coincidentes con este evento: "
            f"{', '.join(matched_rules) if matched_rules else 'ninguna'}"
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
