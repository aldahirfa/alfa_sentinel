"""Serie H (sección 37 de la especificación, 2026-08-17, ver
PENDIENTES.md, "Honeyfiles + monitorización completa del endpoint +
detección por comportamiento anómalo + correlación de indicadores +
despliegue, reconciliación y HR-03/HR-08"): H1-H8, con
start_file_monitor()/apply_honeyfile_policy() reales contra un
watchdog.Observer real y archivos reales en disco.

Ejecutar: python3 tests/honeyfiles/test_h_honeyfiles.py
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


def wait_until(predicate, timeout=6.0, interval=0.1):
    deadline = time_mod.time() + timeout
    while time_mod.time() < deadline:
        if predicate():
            return True
        time_mod.sleep(interval)
    return predicate()


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import config as agent_config  # noqa: E402
import paths as agent_paths  # noqa: E402
import honeyfile_monitor as honeyfile_monitor_module  # noqa: E402
from honeyfile_deployer import apply_honeyfile_policy  # noqa: E402
from file_monitor import start_file_monitor  # noqa: E402

# Margen de gracia más corto SOLO para que esta prueba corra en
# segundos, no minutos -- mark_internal_operation() ahora lee este
# valor del módulo en cada llamada (no un default fijado una sola vez,
# ver honeyfile_monitor.py), así que este monkeypatch sí tiene efecto.
# 1.2s sigue siendo un margen real (production usa 5s) -- la prueba
# duerme más que esto antes de simular una interacción EXTERNA, para
# no confundir su propio "toque externo" con la marca interna reciente.
honeyfile_monitor_module.INTERNAL_OPERATION_GRACE_SECONDS = 1.2
EXTERNAL_ACTION_DELAY = 2.5  # > INTERNAL_OPERATION_GRACE_SECONDS, con margen

H_HONEYFILES_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_h_honeyfiles_")
agent_paths._DEV_HONEYFILES_DIR = H_HONEYFILES_DIR

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_h_pgdata_")
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


agent_h, token_h = make_agent("endpoint-H-honeyfiles")
conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8074"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8074"
agent_config.SERVER_URL = BASE
agent_config.HONEYFILE_POLICY_URL = f"{BASE}/agent/honeyfile-policy"
agent_config.HONEYFILE_POLICY_REPORT_URL = f"{BASE}/agent/honeyfile-policy/report"
# EVENTS_URL/ALERTS_URL también, no solo las de honeyfiles -- si no,
# FileActivityHandler (que corre en el hilo del Observer) sigue
# apuntando al puerto default de config.py (8000, nada escuchando ahí
# en esta prueba) y send_event()/send_alert() fallan en silencio.
agent_config.EVENTS_URL = f"{BASE}/agent/events"
agent_config.ALERTS_URL = f"{BASE}/agent/alerts"
agent_config.RULE_POLICY_URL = f"{BASE}/agent/rule-policy"

observer_h = None
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

    def honeyfile_hit_count(agent_id):
        """Cuántas veces se vinculó 'Acceso Honeyfile' a una alerta de
        este agente en TODA la historia de la prueba -- no solo la
        alerta más reciente. Se usa en comparaciones ANTES/DESPUÉS de
        cada acción: "¿aumentó?" es una pregunta robusta que no depende
        de si la alerta anterior sigue siendo la más nueva ni de su
        status (a diferencia de mirar solo la última alerta, que un
        evento que no genera ninguna alerta nueva -- como crear una
        carpeta -- deja sin tocar, y seguiría mostrando una alerta
        VIEJA como si fuera el resultado de la acción actual)."""
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

    def latest_alert(agent_id):
        c = db_conn()
        row = c.execute(
            "SELECT id, risk_score, (SELECT name FROM severity_levels WHERE id = alerts.severity_id) "
            "FROM alerts WHERE agent_id = %s ORDER BY created_at DESC LIMIT 1;",
            (agent_id,),
        ).fetchone()
        c.close()
        return row

    def close_current_episode(agent_id):
        """El servidor agrupa ráfagas del mismo agente en UNA alerta
        mientras siga NEW/ACKNOWLEDGED dentro de EPISODE_WINDOW_SECONDS
        (ver server/main.py::report_alert) -- y a propósito NO duplica
        una fila de 'alert_rule' para una regla que ya está vinculada a
        ESE episodio (sección 24/26 del motor heurístico: "no duplicar
        evidencia ya registrada"). Como esta serie de pruebas hace
        varias interacciones reales con honeyfiles en menos de
        EPISODE_WINDOW_SECONDS, hay que cerrar el episodio a mano entre
        escenarios para que cada uno cree su PROPIA fila nueva -- si no,
        H4/H5 verían "Acceso Honeyfile" ya vinculado por H3 y el
        conteo de honeyfile_hit_count() no subiría, aunque el agente sí
        haya detectado la interacción de verdad (se ve en su consola:
        "Reglas activas: ['Acceso Honeyfile']" -- esto NO es un bug del
        producto, es deduplicación real y ya probada del servidor)."""
        c = db_conn()
        c.execute("UPDATE alerts SET status = 'RESOLVED' WHERE agent_id = %s AND status IN ('NEW', 'ACKNOWLEDGED');", (agent_id,))
        c.commit()
        c.close()

    def event_count(agent_id, file_path_like):
        c = db_conn()
        row = c.execute(
            "SELECT COUNT(*) FROM events WHERE agent_id = %s AND file_path LIKE %s;",
            (agent_id, file_path_like),
        ).fetchone()
        c.close()
        return row[0]

    observer_h, analyzer_h, honeyfile_monitor_h, event_handler_h, watched_roots_h, watched_extra_h = start_file_monitor(
        [H_HONEYFILES_DIR], token_h, known_honeyfile_paths=[], rule_policy=None
    )

    def sync_h():
        """Replica lo que hace HoneyfileSyncThread._sync_once(), sin el
        hilo de fondo -- para controlar el momento exacto en la prueba."""
        paths = apply_honeyfile_policy(token_h, honeyfile_monitor=honeyfile_monitor_h)
        for p in paths:
            honeyfile_monitor_h.add_known_path(p)
        return paths

    alfa_h_dir = os.path.join(H_HONEYFILES_DIR, agent_paths.ALFA_ARCHIVOS_FOLDER_NAME)

    # --- H1: agente crea honeyfile -> NO HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    deploy_template("H1_Create.txt", [agent_h])
    paths = sync_h()
    h1_path = next(p for p in paths if "H1_Create" in p)
    wait_until(lambda: event_count(agent_h, "%H1_Create%") >= 1)
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("H1: el archivo se creó de verdad en disco", os.path.isfile(h1_path))
    check("H1: creación propia del agente -- NO dispara 'Acceso Honeyfile'", honeyfile_hit_count(agent_h) == hits_before)

    # --- H2: agente recrea honeyfile en reconciliación -> NO HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    deploy_template("H2_Reconcile.txt", [agent_h])
    paths = sync_h()
    h2_path = next(p for p in paths if "H2_Reconcile" in p)
    wait_until(lambda: os.path.isfile(h2_path))
    os.remove(h2_path)
    sync_h()
    wait_until(lambda: os.path.isfile(h2_path))
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("H2: el honeyfile se recreó en disco", os.path.isfile(h2_path))
    check("H2: recreación propia del agente (reconciliación) -- NO dispara 'Acceso Honeyfile'", honeyfile_hit_count(agent_h) == hits_before)

    # --- H3: proceso externo MODIFICA honeyfile -> HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    deploy_template("H3_ExternalModify.txt", [agent_h])
    paths = sync_h()
    h3_path = next(p for p in paths if "H3_ExternalModify" in p)
    wait_until(lambda: os.path.isfile(h3_path))
    time_mod.sleep(EXTERNAL_ACTION_DELAY)  # deja apagarse la marca interna de la propia creación
    with open(h3_path, "a", encoding="utf-8") as f:
        f.write(" -- tocado por un proceso externo")
    wait_until(lambda: honeyfile_hit_count(agent_h) > hits_before, timeout=10.0)
    check("H3: modificación EXTERNA de un honeyfile -> dispara 'Acceso Honeyfile' (HR-03)", honeyfile_hit_count(agent_h) > hits_before)
    alert_h3 = latest_alert(agent_h)
    check("H3: risk_score=100 / severidad CRÍTICO", alert_h3 is not None and float(alert_h3[1]) == 100.0 and alert_h3[2] == "CRÍTICO", str(alert_h3))

    # --- H4: proceso externo ELIMINA honeyfile -> HR-03 ---
    close_current_episode(agent_h)
    hits_before = honeyfile_hit_count(agent_h)
    deploy_template("H4_ExternalDelete.txt", [agent_h])
    paths = sync_h()
    h4_path = next(p for p in paths if "H4_ExternalDelete" in p)
    wait_until(lambda: os.path.isfile(h4_path))
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    os.remove(h4_path)
    wait_until(lambda: honeyfile_hit_count(agent_h) > hits_before, timeout=10.0)
    check("H4: eliminación EXTERNA de un honeyfile -> dispara 'Acceso Honeyfile' (HR-03)", honeyfile_hit_count(agent_h) > hits_before)

    # --- H5: proceso externo RENOMBRA honeyfile -> HR-03 ---
    close_current_episode(agent_h)
    hits_before = honeyfile_hit_count(agent_h)
    deploy_template("H5_ExternalRename.txt", [agent_h])
    paths = sync_h()
    h5_path = next(p for p in paths if "H5_ExternalRename" in p)
    wait_until(lambda: os.path.isfile(h5_path))
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    os.rename(h5_path, h5_path + ".renamed_by_external_process")
    wait_until(lambda: honeyfile_hit_count(agent_h) > hits_before, timeout=10.0)
    check("H5: renombrado EXTERNO de un honeyfile -> dispara 'Acceso Honeyfile' (HR-03)", honeyfile_hit_count(agent_h) > hits_before)

    # --- H6: crear una subcarpeta dentro de ALFA_ARCHIVOS -> NO HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    os.makedirs(os.path.join(alfa_h_dir, "una_subcarpeta"), exist_ok=True)
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("H6: crear una subcarpeta en ALFA_ARCHIVOS -> NO dispara 'Acceso Honeyfile'", honeyfile_hit_count(agent_h) == hits_before)

    # --- H7: crear OTRO archivo (no honeyfile) dentro de ALFA_ARCHIVOS -> NO HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    intruder_path = os.path.join(alfa_h_dir, "intruso.txt")
    with open(intruder_path, "w", encoding="utf-8") as f:
        f.write("un archivo cualquiera, no un honeyfile registrado")
    wait_until(lambda: event_count(agent_h, "%intruso.txt%") >= 1)
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("H7: archivo NUEVO ajeno en ALFA_ARCHIVOS -> se registra el evento", event_count(agent_h, "%intruso.txt%") >= 1)
    check("H7: archivo NUEVO ajeno en ALFA_ARCHIVOS -> NO se etiqueta como honeyfile (no dispara HR-03)", honeyfile_hit_count(agent_h) == hits_before)

    # --- H8: modificar ese mismo archivo ajeno -> NO HR-03 ---
    hits_before = honeyfile_hit_count(agent_h)
    with open(intruder_path, "a", encoding="utf-8") as f:
        f.write(" -- modificado también")
    wait_until(lambda: event_count(agent_h, "%intruso.txt%") >= 2)
    time_mod.sleep(EXTERNAL_ACTION_DELAY)
    check("H8: modificar el archivo ajeno -> se registra el evento", event_count(agent_h, "%intruso.txt%") >= 2)
    check("H8: modificar el archivo ajeno -> sigue sin disparar 'Acceso Honeyfile'", honeyfile_hit_count(agent_h) == hits_before)

finally:
    if observer_h is not None:
        try:
            observer_h.stop()
            observer_h.join(timeout=5)
        except Exception:
            pass
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    pg.cleanup()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)
    shutil.rmtree(H_HONEYFILES_DIR, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_h_honeyfiles.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
    print("\n--- últimas líneas del log de uvicorn ---")
    for line in server_log_lines[-60:]:
        print(line, end="")
sys.exit(0 if passed == total else 1)
