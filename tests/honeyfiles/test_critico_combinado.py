"""Prueba crítica combinada (sección 39 de la especificación, 2026-08-17,
ver PENDIENTES.md, "Honeyfiles + monitorización completa del endpoint +
detección por comportamiento anómalo + correlación de indicadores +
despliegue, reconciliación y HR-03/HR-08"):

Un proceso sospechoso (1) modifica archivos en Videos, (2) modifica
archivos en Documents, (3) elimina archivos, (4) realiza actividad
repetitiva, y (5) finalmente toca un honeyfile. Se espera:

- ANTES de tocar el honeyfile: evidencia de comportamiento anómalo con
  varias reglas coincidiendo y un score CALCULADO (no 100) en la MISMA
  alerta/episodio abierto.
- AL tocar el honeyfile: HR-03 se suma a ESE MISMO episodio -> el score
  llega a 100/CRÍTICO. La evidencia previa (HR-01/04/09/11 + HR-12) NO
  se duplica ni se pierde -- sigue vinculada a la misma alerta, como
  contexto (sección 33: "su política especial sigue siendo 100, la
  evidencia anterior se conserva como contexto/reglas participantes").

Ejecutar: python3 tests/honeyfiles/test_critico_combinado.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time as time_mod

import pgserver
import httpx
import psycopg

for _proxy_var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    os.environ.pop(_proxy_var, None)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


def wait_until(predicate, timeout=8.0, interval=0.1):
    deadline = time_mod.time() + timeout
    while time_mod.time() < deadline:
        if predicate():
            return True
        time_mod.sleep(interval)
    return predicate()


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))
sys.path.insert(0, os.path.join(REPO, "tests", "heuristic"))

import config as agent_config  # noqa: E402
import paths as agent_paths  # noqa: E402
import honeyfile_monitor as honeyfile_monitor_module  # noqa: E402
from honeyfile_deployer import apply_honeyfile_policy  # noqa: E402
from file_monitor import start_file_monitor  # noqa: E402
from lab_processes import spawn_multi_writer, wait_ready, signal_go  # noqa: E402
from client import get_isolation_status, report_isolation_status  # noqa: E402
from isolation_executor import execute_isolation  # noqa: E402

# Igual criterio que test_h_honeyfiles.py: margen corto para que la
# prueba corra en segundos, y mark_internal_operation() lee este valor
# del módulo en cada llamada (no un default fijado una sola vez).
honeyfile_monitor_module.INTERNAL_OPERATION_GRACE_SECONDS = 1.2
EXTERNAL_ACTION_DELAY = 2.5  # > INTERNAL_OPERATION_GRACE_SECONDS, con margen

CRIT_HONEYFILES_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_critico_honeyfiles_")
agent_paths._DEV_HONEYFILES_DIR = CRIT_HONEYFILES_DIR

CRIT_ROOT = tempfile.mkdtemp(prefix="alfa_sentinel_test_critico_endpoint_")
CRIT_VIDEOS = os.path.join(CRIT_ROOT, "Videos")
CRIT_DOCUMENTS = os.path.join(CRIT_ROOT, "Documents")
CRIT_PICTURES = os.path.join(CRIT_ROOT, "Pictures")
CRIT_MUSIC = os.path.join(CRIT_ROOT, "Music")
for _d in (CRIT_VIDEOS, CRIT_DOCUMENTS, CRIT_PICTURES, CRIT_MUSIC):
    os.makedirs(_d, exist_ok=True)

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_critico_pgdata_")
shutil.rmtree(PGDATA_DIR, ignore_errors=True)
pg = pgserver.get_server(PGDATA_DIR)

admin_conn = psycopg.connect(pg.get_uri(), autocommit=True)
admin_conn.execute("DROP DATABASE IF EXISTS alfa_test;")
admin_conn.execute("CREATE DATABASE alfa_test;")
admin_conn.close()

DATABASE_URL = pg.get_uri().replace("/postgres?", "/alfa_test?")

with open(os.path.join(REPO, "database", "schema.sql")) as f:
    schema_sql = f.read()

conn = psycopg.connect(DATABASE_URL, autocommit=True)
conn.execute(schema_sql)

sys.path.insert(0, os.path.join(REPO, "server"))
from security import hash_password  # noqa: E402

conn.execute("INSERT INTO roles (name, description) VALUES ('admin', 'Acceso total al sistema') ON CONFLICT DO NOTHING;")
conn.execute(
    """INSERT INTO users (username, password_hash, full_name, email)
       VALUES ('tester', %s, 'Tester', 'tester@example.com') ON CONFLICT DO NOTHING;""",
    (hash_password("Password123"),),
)
user_id = conn.execute("SELECT id FROM users WHERE username = 'tester';").fetchone()[0]
role_id = conn.execute("SELECT id FROM roles WHERE name = 'admin';").fetchone()[0]
conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (user_id, role_id))


def make_agent(hostname, os_name="Windows"):
    ep = conn.execute(
        "INSERT INTO endpoints (hostname, os, os_version) VALUES (%s, %s, '11') RETURNING id;",
        (hostname, os_name),
    ).fetchone()
    ag = conn.execute(
        "INSERT INTO agents (endpoint_id, agent_version) VALUES (%s, '1.0') RETURNING id;", (ep[0],)
    ).fetchone()
    agent_id = ag[0]
    token = f"token-{hostname}"
    conn.execute(
        "INSERT INTO agent_credentials (agent_id, credential_hash) VALUES (%s, %s);",
        (agent_id, hashlib.sha256(token.encode()).hexdigest()),
    )
    return agent_id, token


agent_c, token_c = make_agent("endpoint-critico-combinado")

TEST_THRESHOLD = 5
rule_ids = {}
for name in (
    "Modificacion Masiva Archivos", "Escritura Intensiva Archivos",
    "Eliminacion Anomala Archivos", "Actividad Repetitiva Automatizada",
):
    row = conn.execute("SELECT id FROM heuristic_rules WHERE name = %s;", (name,)).fetchone()
    rule_ids[name] = row[0]

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8076"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8076"
agent_config.SERVER_URL = BASE
agent_config.HONEYFILE_POLICY_URL = f"{BASE}/agent/honeyfile-policy"
agent_config.HONEYFILE_POLICY_REPORT_URL = f"{BASE}/agent/honeyfile-policy/report"
agent_config.EVENTS_URL = f"{BASE}/agent/events"
agent_config.ALERTS_URL = f"{BASE}/agent/alerts"
agent_config.RULE_POLICY_URL = f"{BASE}/agent/rule-policy"
agent_config.ISOLATION_STATUS_URL = f"{BASE}/agent/isolation-status"
agent_config.ISOLATION_STATUS_REPORT_URL = f"{BASE}/agent/isolation-status/report"

observer_c = None
server_log_lines = []

try:
    def _drain():
        for line in proc.stdout:
            server_log_lines.append(line)
    threading.Thread(target=_drain, daemon=True).start()

    ok = False
    for _ in range(60):
        try:
            if httpx.get(BASE + "/docs", timeout=1, trust_env=False).status_code == 200:
                ok = True
                break
        except Exception:
            pass
        time_mod.sleep(0.5)
    check("uvicorn levantó correctamente", ok)

    client = httpx.Client(base_url=BASE, trust_env=False)
    r = client.post("/login", json={"username": "tester", "password": "Password123"})
    check("Login admin OK", r.status_code == 200, f"status={r.status_code}")

    # Override por endpoint -- mismo criterio que test_g_monitorizacion_global.py,
    # baja el threshold para que la prueba corra en segundos.
    for rule_name, rule_id in rule_ids.items():
        r = client.patch(f"/api/agents/{agent_c}/rules/{rule_id}", json={"threshold": TEST_THRESHOLD})
        assert r.status_code == 200, r.text

    def deploy_template(file_name, agent_ids, target_path="DOCUMENTS", file_type="txt"):
        body = {
            "file_name": file_name, "file_type": file_type, "target_path": target_path,
            "platform": "all", "auto_deploy": False,
            "content": f"Contenido de prueba -- {file_name}", "agent_ids": agent_ids,
        }
        r = client.post("/api/honeyfiles/deploy", json=body)
        assert r.status_code == 200, r.text
        return r.json()["template_id"]

    def db_conn():
        return psycopg.connect(DATABASE_URL)

    def alert_rule_names_ever(agent_id):
        c = db_conn()
        rows = c.execute(
            """
            SELECT DISTINCT heuristic_rules.name
            FROM alert_rule
            JOIN alerts ON alerts.id = alert_rule.alert_id
            JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
            WHERE alerts.agent_id = %s;
            """,
            (agent_id,),
        ).fetchall()
        c.close()
        return {row[0] for row in rows}

    def honeyfile_hit_count(agent_id):
        c = db_conn()
        row = c.execute(
            """
            SELECT COUNT(*)
            FROM alert_rule
            JOIN alerts ON alerts.id = alert_rule.alert_id
            JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
            WHERE alerts.agent_id = %s AND heuristic_rules.name = 'Acceso Honeyfile';
            """,
            (agent_id,),
        ).fetchone()
        c.close()
        return row[0]

    def current_open_alert(agent_id):
        """La alerta NEW/ACKNOWLEDGED más reciente de este agente --
        el mismo criterio de episodio que usa report_alert() en el
        servidor (server/main.py, EPISODE_WINDOW_SECONDS)."""
        c = db_conn()
        row = c.execute(
            """
            SELECT alerts.id, alerts.risk_score,
                   (SELECT name FROM severity_levels WHERE id = alerts.severity_id),
                   alerts.incident_id
            FROM alerts
            WHERE agent_id = %s AND status IN ('NEW', 'ACKNOWLEDGED')
            ORDER BY created_at DESC LIMIT 1;
            """,
            (agent_id,),
        ).fetchone()
        c.close()
        return row

    def linked_rule_names(alert_id):
        c = db_conn()
        rows = c.execute(
            """
            SELECT heuristic_rules.name FROM alert_rule
            JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
            WHERE alert_rule.alert_id = %s;
            """,
            (alert_id,),
        ).fetchall()
        c.close()
        return {row[0] for row in rows}

    def event_count(agent_id, file_path_like):
        c = db_conn()
        row = c.execute(
            "SELECT COUNT(*) FROM events WHERE agent_id = %s AND file_path LIKE %s;",
            (agent_id, file_path_like),
        ).fetchone()
        c.close()
        return row[0]

    def event_attributed(agent_id, file_path, pid):
        c = db_conn()
        row = c.execute(
            "SELECT 1 FROM events WHERE agent_id = %s AND file_path = %s AND process_id = %s LIMIT 1;",
            (agent_id, file_path, pid),
        ).fetchone()
        c.close()
        return row is not None

    def host_isolation_requested(incident_id):
        c = db_conn()
        row = c.execute(
            "SELECT id, reason FROM host_isolations WHERE incident_id = %s AND status = 'REQUESTED';",
            (incident_id,),
        ).fetchone()
        c.close()
        return row

    def host_isolation_row(isolation_id):
        c = db_conn()
        row = c.execute(
            "SELECT status, result, executed_at FROM host_isolations WHERE id = %s;",
            (isolation_id,),
        ).fetchone()
        c.close()
        return row

    # Política EFECTIVA real (con los overrides de threshold ya
    # aplicados) -- si se pasara rule_policy=None, el analizador caería
    # a DEFAULT_RULES y el override no tendría efecto real (mismo
    # detalle ya resuelto en test_g_monitorizacion_global.py).
    rp = client.get("/agent/rule-policy", headers={"X-Agent-Credential": token_c})
    assert rp.status_code == 200, rp.text
    rule_policy_c = rp.json()["rules"]

    # UN solo Observer real vigilando TANTO las carpetas globales del
    # endpoint (Videos/Documents/Pictures/Music) COMO la carpeta donde
    # vive ALFA_ARCHIVOS -- exactamente lo que exige la sección 40: "no
    # limitar el monitoreo a ALFA_ARCHIVOS, no abandonar el monitoreo
    # global".
    observer_c, analyzer_c, honeyfile_monitor_c, event_handler_c, watched_roots_c, watched_extra_c = start_file_monitor(
        [CRIT_VIDEOS, CRIT_DOCUMENTS, CRIT_PICTURES, CRIT_MUSIC, CRIT_HONEYFILES_DIR],
        token_c, known_honeyfile_paths=[], rule_policy=rule_policy_c,
    )

    def sync_c():
        paths = apply_honeyfile_policy(token_c, honeyfile_monitor=honeyfile_monitor_c)
        for p in paths:
            honeyfile_monitor_c.add_known_path(p)
        return paths

    # --- Despliegue del honeyfile (no cuenta como parte del ataque --
    # se deja asentar antes de empezar el comportamiento anómalo) ---
    deploy_template("Critico_Honeyfile.txt", [agent_c])
    paths = sync_c()
    crit_honeyfile_path = next(p for p in paths if "Critico_Honeyfile" in p)
    wait_until(lambda: os.path.isfile(crit_honeyfile_path))
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("Honeyfile desplegado antes del ataque (creación propia -- no cuenta como interacción)", honeyfile_hit_count(agent_c) == 0)

    # --- Paso 1: modificar archivos en Videos -> HR-01 ---
    for i in range(TEST_THRESHOLD + 2):
        with open(os.path.join(CRIT_VIDEOS, f"video_{i}.mp4"), "w") as f:
            f.write("x")
    wait_until(lambda: "Modificacion Masiva Archivos" in alert_rule_names_ever(agent_c))
    check("Paso 1: modificar archivos en Videos -> dispara HR-01 (Modificación Masiva)", "Modificacion Masiva Archivos" in alert_rule_names_ever(agent_c))

    # --- Paso 2: escritura intensiva en Documents -> HR-04 ---
    doc_path = os.path.join(CRIT_DOCUMENTS, "documento_repetido.docx")
    for i in range(TEST_THRESHOLD + 2):
        with open(doc_path, "a") as f:
            f.write(f"línea {i}\n")
    wait_until(lambda: "Escritura Intensiva Archivos" in alert_rule_names_ever(agent_c))
    check("Paso 2: escritura intensiva en Documents -> dispara HR-04 (Escritura Intensiva)", "Escritura Intensiva Archivos" in alert_rule_names_ever(agent_c))

    # --- Paso 3: eliminación masiva en Pictures -> HR-09 ---
    pic_paths = []
    for i in range(TEST_THRESHOLD + 2):
        p = os.path.join(CRIT_PICTURES, f"foto_{i}.jpg")
        with open(p, "w") as f:
            f.write("x")
        pic_paths.append(p)
    wait_until(lambda: event_count(agent_c, "%foto_%.jpg%") >= TEST_THRESHOLD + 2)
    for p in pic_paths:
        os.remove(p)
    wait_until(lambda: "Eliminacion Anomala Archivos" in alert_rule_names_ever(agent_c))
    check("Paso 3: eliminación masiva en Pictures -> dispara HR-09 (Eliminación Anómala)", "Eliminacion Anomala Archivos" in alert_rule_names_ever(agent_c))

    # --- Paso 4: actividad repetitiva del MISMO proceso en Music -> HR-11 ---
    lab_proc = spawn_multi_writer(CRIT_MUSIC, TEST_THRESHOLD + 2)
    try:
        for i in range(TEST_THRESHOLD + 2):
            file_path = os.path.join(CRIT_MUSIC, f"op_{i}.txt")
            wait_ready(file_path, timeout=10.0)
            # Mismo motivo que en test_g_monitorizacion_global.py::G5:
            # no soltar el handshake hasta que el evento YA llegó
            # atribuido al PID real -- si no, el hijo puede cerrar el
            # archivo antes de que watchdog (ocupado también con el
            # ruido propio de los marcadores .ready/.go) alcance a
            # consultar psutil mientras seguía abierto.
            wait_until(lambda fp=file_path: event_attributed(agent_c, fp, lab_proc.pid), timeout=10.0, interval=0.05)
            signal_go(file_path)
        lab_proc.wait(timeout=30)
    finally:
        if lab_proc.poll() is None:
            lab_proc.kill()
    check(
        f"Paso 4: un único proceso real con {TEST_THRESHOLD + 2} operaciones en Music -> dispara HR-11 (Actividad Repetitiva)",
        wait_until(lambda: "Actividad Repetitiva Automatizada" in alert_rule_names_ever(agent_c), timeout=8.0),
    )

    # --- Evidencia ANTES de tocar el honeyfile: mismo episodio, score
    # calculado (no 100), sin HR-03 todavía ---
    alert_before = current_open_alert(agent_c)
    check("Antes del honeyfile: existe una alerta abierta con evidencia acumulada", alert_before is not None, str(alert_before))
    alert_id_before = alert_before[0] if alert_before else None
    names_before = linked_rule_names(alert_id_before) if alert_id_before else set()
    check(
        "Antes del honeyfile: 4 reglas de comportamiento anómalo coinciden en el MISMO episodio",
        {"Modificacion Masiva Archivos", "Escritura Intensiva Archivos", "Eliminacion Anomala Archivos", "Actividad Repetitiva Automatizada"} <= names_before,
        str(names_before),
    )
    check("Antes del honeyfile: score calculado, NO 100 (sección 39: 'antes... score calculado no 100')", alert_before is not None and float(alert_before[1]) < 100.0, str(alert_before))
    # Nota: la severidad YA puede ser CRÍTICO acá -- la banda CRÍTICO
    # (75-100, ver schema.sql) no es exclusiva del honeyfile, y 4-5
    # reglas de comportamiento anómalo coincidiendo a la vez más la
    # bonificación de correlación HR-12 es evidencia genuinamente
    # fuerte por sí sola. Lo que la sección 39 exige distinguir es
    # "score calculado (no 100)" ANTES vs "100 exacto" DESPUÉS -- no
    # que la severidad deba quedarse por debajo de CRÍTICO.
    check("Antes del honeyfile: 'Acceso Honeyfile' (HR-03) NO participó todavía", "Acceso Honeyfile" not in names_before, str(names_before))

    # --- Paso 5: el mismo atacante finalmente toca el honeyfile -> HR-03 ---
    hits_before = honeyfile_hit_count(agent_c)
    with open(crit_honeyfile_path, "a", encoding="utf-8") as f:
        f.write(" -- finalmente tocado por el atacante")
    wait_until(lambda: honeyfile_hit_count(agent_c) > hits_before, timeout=10.0)
    check("Paso 5: tocar el honeyfile -> dispara 'Acceso Honeyfile' (HR-03)", honeyfile_hit_count(agent_c) > hits_before)

    # --- Evidencia DESPUÉS: MISMO episodio (no uno nuevo), score=100/CRÍTICO,
    # evidencia previa preservada como contexto, no duplicada ---
    alert_after = current_open_alert(agent_c)
    check("Después del honeyfile: sigue siendo la MISMA alerta/episodio (continuidad, no duplicado)", alert_after is not None and alert_id_before is not None and alert_after[0] == alert_id_before, f"{alert_before} -> {alert_after}")
    check("Después del honeyfile: risk_score = 100", alert_after is not None and float(alert_after[1]) == 100.0, str(alert_after))
    check("Después del honeyfile: severidad = CRÍTICO", alert_after is not None and alert_after[2] == "CRÍTICO", str(alert_after))

    names_after = linked_rule_names(alert_id_before) if alert_id_before else set()
    check(
        "Después del honeyfile: la evidencia PREVIA (HR-01/04/09/11) sigue vinculada -- se conserva como contexto",
        names_before <= names_after, f"antes={names_before} despues={names_after}",
    )
    check("Después del honeyfile: 'Acceso Honeyfile' ahora SÍ participa, sumado a la evidencia previa (no la reemplaza)", "Acceso Honeyfile" in names_after, str(names_after))

    # No duplicar evidencia: cada regla (salvo la fila sintética de
    # correlación) debe aparecer una sola vez vinculada a esta alerta,
    # incluso habiendo pasado por dos llamadas a report_alert() con la
    # misma regla matcheada más de una vez a lo largo de la prueba.
    c = db_conn()
    rule_row_count = c.execute(
        """
        SELECT heuristic_rules.name, COUNT(*) FROM alert_rule
        JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
        WHERE alert_rule.alert_id = %s
        GROUP BY heuristic_rules.name;
        """,
        (alert_id_before,),
    ).fetchall()
    c.close()
    duplicated = [row for row in rule_row_count if row[1] > 1]
    check("Sin duplicar evidencia: cada regla aparece UNA sola vez en la misma alerta", not duplicated, str(rule_row_count))

    # --- Secciones 26-30: incidente + aislamiento EJECUTADO de verdad
    # (corrección definitiva, 2026-08-17, ver PENDIENTES.md: "el
    # sistema debe EJECUTAR el aislamiento automáticamente... no
    # solamente recomendar") ---
    check("Se creó un incidente automáticamente (honeyfile + evidencia fuerte)", alert_after is not None and alert_after[3] is not None, str(alert_after))
    if alert_after is not None and alert_after[3] is not None:
        incident_id_after = alert_after[3]
        req = host_isolation_requested(incident_id_after)
        check("Orden de aislamiento REQUESTED -- Condición A: honeyfile + indicador fuerte de archivos", req is not None, str(req))

        if req is not None:
            isolation_id = req[0]

            # Ejerce el mismo ciclo que agent/isolation_sync.py::_sync_once()
            # -- sin el hilo de fondo, para controlar el momento exacto
            # en la prueba (mismo criterio que sync_c() para honeyfiles
            # más arriba). agent_paths._DEV_HONEYFILES_DIR ya está
            # monkeypatcheado y ALFA_SENTINEL_ENV no está en
            # 'production' -- execute_isolation() toma la rama
            # SIMULADA (no toca ningún firewall real de esta máquina),
            # pero el resultado se reporta y se persiste igual que en
            # producción, así que el estado final es genuino, no un
            # dato de prueba fabricado a mano.
            status_resp = get_isolation_status(token_c)
            check("GET /agent/isolation-status devuelve la orden pendiente", status_resp is not None and status_resp.status_code == 200, str(status_resp))
            pending = status_resp.json().get("pending") if status_resp is not None else None
            check("La orden pendiente reportada es la misma que se insertó", pending is not None and pending["isolation_id"] == isolation_id, str(pending))

            success, result_message = execute_isolation(pending["isolation_type"]) if pending else (False, "sin orden pendiente")
            check("execute_isolation() se completa (simulado en development, nunca toca el firewall real)", success, result_message)

            report_resp = report_isolation_status(token_c, isolation_id, "EXECUTED" if success else "ISOLATION_FAILED", result_message)
            check("POST /agent/isolation-status/report confirma el resultado", report_resp is not None and report_resp.status_code == 200, str(report_resp))

            final_row = host_isolation_row(isolation_id)
            check("Estado final = EXECUTED (no se quedó en RECOMMENDED/REQUESTED)", final_row is not None and final_row[0] == "EXECUTED", str(final_row))
            check("result queda registrado (visible en la consola vía /api/respuesta)", final_row is not None and bool(final_row[1]), str(final_row))
            check("executed_at queda registrado", final_row is not None and final_row[2] is not None, str(final_row))

            # No debe quedar una segunda orden pendiente para el mismo
            # incidente -- report_alert() no duplica mientras siga
            # REQUESTED o EXECUTED (ver server/main.py).
            check("No queda una orden REQUESTED duplicada tras ejecutar", host_isolation_requested(incident_id_after) is None)

finally:
    if observer_c is not None:
        try:
            observer_c.stop()
            observer_c.join(timeout=5)
        except Exception:
            pass
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    pg.cleanup()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)
    shutil.rmtree(CRIT_HONEYFILES_DIR, ignore_errors=True)
    shutil.rmtree(CRIT_ROOT, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_critico_combinado.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
    print("\n--- últimas líneas del log de uvicorn ---")
    for line in server_log_lines[-60:]:
        print(line, end="")
sys.exit(0 if passed == total else 1)
