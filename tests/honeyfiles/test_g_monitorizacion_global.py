"""Serie G (sección 38 de la especificación, 2026-08-17, ver
PENDIENTES.md, "Honeyfiles + monitorización completa del endpoint +
detección por comportamiento anómalo + correlación de indicadores +
despliegue, reconciliación y HR-03/HR-08"): G1-G6, con
start_file_monitor() real vigilando carpetas FUERA de ALFA_ARCHIVOS
(Videos/Documents/Pictures/Music) -- confirma que el agente sigue
observando TODO el endpoint, no solo la zona de honeyfiles.

Ejecutar: python3 tests/honeyfiles/test_g_monitorizacion_global.py
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
from file_monitor import start_file_monitor  # noqa: E402
from lab_processes import spawn_multi_writer, wait_ready, signal_go  # noqa: E402

G_ROOT = tempfile.mkdtemp(prefix="alfa_sentinel_test_g_endpoint_")
G_VIDEOS = os.path.join(G_ROOT, "Videos")
G_DOCUMENTS = os.path.join(G_ROOT, "Documents")
G_PICTURES = os.path.join(G_ROOT, "Pictures")
G_MUSIC = os.path.join(G_ROOT, "Music")
for _d in (G_VIDEOS, G_DOCUMENTS, G_PICTURES, G_MUSIC):
    os.makedirs(_d, exist_ok=True)

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_g_pgdata_")
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


agent_g, token_g = make_agent("endpoint-G-monitorizacion-global")

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
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8075"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8075"
agent_config.SERVER_URL = BASE
agent_config.HONEYFILE_POLICY_URL = f"{BASE}/agent/honeyfile-policy"
agent_config.HONEYFILE_POLICY_REPORT_URL = f"{BASE}/agent/honeyfile-policy/report"
agent_config.EVENTS_URL = f"{BASE}/agent/events"
agent_config.ALERTS_URL = f"{BASE}/agent/alerts"
agent_config.RULE_POLICY_URL = f"{BASE}/agent/rule-policy"

observer_g = None
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

    # Override por endpoint (agent_rule, ya existente y probado) --
    # baja el threshold para que la prueba corra en segundos, mismo
    # criterio que test_h_honeyfiles.py (ver ese archivo para el
    # detalle). No inventa ningún mecanismo nuevo.
    for rule_name, rule_id in rule_ids.items():
        r = client.patch(f"/api/agents/{agent_g}/rules/{rule_id}", json={"threshold": TEST_THRESHOLD})
        assert r.status_code == 200, r.text

    def db_conn():
        return psycopg.connect(DATABASE_URL)

    def alert_rule_names_ever(agent_id):
        """Todas las reglas que en algún momento se vincularon a
        cualquier alerta de este agente -- no solo la más reciente
        (ver test_h_honeyfiles.py::close_current_episode para el
        porqué: el servidor deduplica evidencia repetida DENTRO del
        mismo episodio, así que 'la última alerta' puede no ser un
        buen espejo de qué reglas coincidieron en total)."""
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

    def event_count(agent_id, file_path_like):
        c = db_conn()
        row = c.execute(
            "SELECT COUNT(*) FROM events WHERE agent_id = %s AND file_path LIKE %s;",
            (agent_id, file_path_like),
        ).fetchone()
        c.close()
        return row[0]

    def event_attributed(agent_id, file_path, pid):
        """¿Ya llegó al servidor un evento sobre 'file_path' atribuido
        al PID real del proceso de laboratorio? Se usa en G5 para no
        soltar el handshake (signal_go) hasta que el hilo de watchdog
        real ya haya podido consultar psutil MIENTRAS el archivo
        seguía abierto -- ver comentario en el bucle de G5."""
        c = db_conn()
        row = c.execute(
            "SELECT 1 FROM events WHERE agent_id = %s AND file_path = %s AND process_id = %s LIMIT 1;",
            (agent_id, file_path, pid),
        ).fetchone()
        c.close()
        return row is not None

    # Traer la política EFECTIVA real (con el override de threshold de
    # arriba ya aplicado) -- si se pasara rule_policy=None acá,
    # FileActivityAnalyzer.from_policy() caería a DEFAULT_RULES
    # (threshold=20 para HR-01, etc.) y el override por endpoint no
    # tendría ningún efecto en lo que el agente evalúa de verdad.
    rp = client.get("/agent/rule-policy", headers={"X-Agent-Credential": token_g})
    assert rp.status_code == 200, rp.text
    rule_policy_g = rp.json()["rules"]

    observer_g, analyzer_g, honeyfile_monitor_g, event_handler_g, watched_roots_g, watched_extra_g = start_file_monitor(
        [G_VIDEOS, G_DOCUMENTS, G_PICTURES, G_MUSIC], token_g, known_honeyfile_paths=[], rule_policy=rule_policy_g
    )

    # --- G1: crear/modificar archivos en Videos -> eventos registrados ---
    g1_path = os.path.join(G_VIDEOS, "video_de_prueba.mp4")
    with open(g1_path, "w") as f:
        f.write("contenido")
    wait_until(lambda: event_count(agent_g, "%video_de_prueba.mp4%") >= 1)
    check("G1: crear un archivo en Videos (fuera de ALFA_ARCHIVOS) genera un evento real", event_count(agent_g, "%video_de_prueba.mp4%") >= 1)
    with open(g1_path, "a") as f:
        f.write(" más contenido")
    wait_until(lambda: event_count(agent_g, "%video_de_prueba.mp4%") >= 2)
    check("G1: modificarlo genera un segundo evento", event_count(agent_g, "%video_de_prueba.mp4%") >= 2)

    # --- G2: modificar muchos archivos en Videos -> HR-01 ---
    for i in range(TEST_THRESHOLD + 2):
        with open(os.path.join(G_VIDEOS, f"video_{i}.mp4"), "w") as f:
            f.write("x")
    wait_until(lambda: "Modificacion Masiva Archivos" in alert_rule_names_ever(agent_g))
    check(f"G2: {TEST_THRESHOLD + 2} archivos únicos modificados en Videos -> dispara HR-01 (Modificación Masiva)", "Modificacion Masiva Archivos" in alert_rule_names_ever(agent_g))

    # --- G3: escritura intensiva en Documents -> HR-04 ---
    doc_path = os.path.join(G_DOCUMENTS, "documento_repetido.docx")
    for i in range(TEST_THRESHOLD + 2):
        with open(doc_path, "a") as f:
            f.write(f"línea {i}\n")
    wait_until(lambda: "Escritura Intensiva Archivos" in alert_rule_names_ever(agent_g))
    check(f"G3: {TEST_THRESHOLD + 2} escrituras en Documents -> dispara HR-04 (Escritura Intensiva)", "Escritura Intensiva Archivos" in alert_rule_names_ever(agent_g))

    # --- G4: eliminación masiva en Pictures -> HR-09 ---
    pic_paths = []
    for i in range(TEST_THRESHOLD + 2):
        p = os.path.join(G_PICTURES, f"foto_{i}.jpg")
        with open(p, "w") as f:
            f.write("x")
        pic_paths.append(p)
    wait_until(lambda: event_count(agent_g, "%foto_%.jpg%") >= TEST_THRESHOLD + 2)
    for p in pic_paths:
        os.remove(p)
    wait_until(lambda: "Eliminacion Anomala Archivos" in alert_rule_names_ever(agent_g))
    check(f"G4: {TEST_THRESHOLD + 2} eliminaciones en Pictures -> dispara HR-09 (Eliminación Anómala)", "Eliminacion Anomala Archivos" in alert_rule_names_ever(agent_g))

    # --- G5: actividad repetitiva del MISMO proceso (HR-11) en Music, con atribución real ---
    lab_proc = spawn_multi_writer(G_MUSIC, TEST_THRESHOLD + 2)
    try:
        for i in range(TEST_THRESHOLD + 2):
            file_path = os.path.join(G_MUSIC, f"op_{i}.txt")
            wait_ready(file_path, timeout=10.0)
            # A diferencia de tests/heuristic/test_attribution.py (que
            # llama a get_process_for_file_event() DIRECTO, en el mismo
            # hilo, sin cola de por medio), acá la atribución la hace
            # el hilo real de watchdog de forma asíncrona -- y ese
            # mismo hilo también procesa el ruido de los marcadores
            # ".ready"/".go" (creación+borrado de cada uno, 4 eventos
            # extra por archivo) más lo que ya venía de G2-G4. Si se
            # llama a signal_go() de inmediato, el proceso de
            # laboratorio puede cerrar el archivo y pasar al siguiente
            # ANTES de que watchdog llegue a intentar la atribución
            # psutil -- y psutil.open_files() ya no lo vería abierto
            # (fallo honesto, sección 36: "nunca inventar si no está
            # disponible", pero no lo que esta prueba quiere ejercitar).
            # Por eso se espera a que el evento YA llegó atribuido al
            # PID real del proceso antes de soltar el archivo.
            wait_until(lambda fp=file_path: event_attributed(agent_g, fp, lab_proc.pid), timeout=10.0, interval=0.05)
            signal_go(file_path)
            # No llamar a cleanup_markers() acá: multi_writer.py limpia sus
            # propios marcadores ".ready"/".go" apenas sale de su propio
            # bucle de espera (ver lab_scripts/multi_writer.py). Si el
            # proceso padre borra el ".go" en la misma instrucción que lo
            # crea, puede ganarle la carrera al hijo -- que sondea el
            # archivo cada 0.02s -- y el hijo esperaría el resto de su
            # timeout de 30s pensando que nunca llegó la señal. Mismo
            # patrón, sin este bug, ya probado en test_attribution.py.
        lab_proc.wait(timeout=30)
    finally:
        if lab_proc.poll() is None:
            lab_proc.kill()
    check(
        f"G5: un único proceso real con {TEST_THRESHOLD + 2} operaciones en Music -> dispara HR-11 (Actividad Repetitiva)",
        wait_until(lambda: "Actividad Repetitiva Automatizada" in alert_rule_names_ever(agent_g), timeout=8.0),
    )

    # --- G6: varias reglas en varias carpetas -> correlación HR-12 ---
    all_names = alert_rule_names_ever(agent_g)
    check(
        "G6: 4+ reglas distintas coincidieron (Videos+Documents+Pictures+Music) -> evidencia de correlación real",
        len(all_names - {"Correlacion Multiples Indicadores"}) >= 4,
        str(all_names),
    )
    c = db_conn()
    corr_row = c.execute(
        """
        SELECT alert_rule.weight_applied
        FROM alert_rule
        JOIN alerts ON alerts.id = alert_rule.alert_id
        JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
        WHERE alerts.agent_id = %s AND heuristic_rules.name = 'Correlacion Multiples Indicadores'
        ORDER BY alert_rule.matched_at DESC LIMIT 1;
        """,
        (agent_g,),
    ).fetchone()
    c.close()
    check("G6: HR-12 (Correlación) participó con una bonificación real", corr_row is not None, str(corr_row))
    if corr_row is not None:
        check("G6: bonificación de correlación > 0 (varias reglas distintas en el mismo episodio)", float(corr_row[0]) > 0, str(corr_row))

finally:
    if observer_g is not None:
        try:
            observer_g.stop()
            observer_g.join(timeout=5)
        except Exception:
            pass
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    pg.cleanup()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)
    shutil.rmtree(G_ROOT, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_g_monitorizacion_global.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
    print("\n--- últimas líneas del log de uvicorn ---")
    for line in server_log_lines[-60:]:
        print(line, end="")
sys.exit(0 if passed == total else 1)
