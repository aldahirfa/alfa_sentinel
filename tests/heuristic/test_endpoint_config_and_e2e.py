"""Prueba consolidada end-to-end (pgserver + uvicorn real) de la
resolución de overrides por endpoint (agent_rule) -- sección 25/29 de
la especificación de configuración por endpoint: 5 escenarios
nombrados (A: sin override, B: override de threshold, C: override de
weight, D: override de window, E: regla desactivada) + una traza de
integración completa agente -> evento -> matched_rules -> servidor ->
config efectiva -> score -> severidad -> alerta -> incidente ->
condición de aislamiento (sección 24 de la especificación de
atribución de procesos: "en el entorno .venv comprobar" esta misma
cadena).

Metodología: pgserver efímero (Postgres embebido, no toca la base real
del usuario) + uvicorn real en subproceso + httpx.Client(trust_env=False)
(evita interferencia de variables de entorno de proxy en el sandbox).
No requiere privilegios especiales -- corre en cualquier entorno con
Python y las dependencias de server/requirements.txt instaladas.

Ejecutar: python3 tests/heuristic/test_endpoint_config_and_e2e.py
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

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_pgdata_")

shutil.rmtree(PGDATA_DIR, ignore_errors=True)
pg = pgserver.get_server(PGDATA_DIR)

# pg.get_uri() ya trae la BD por defecto 'postgres' y el host como
# query param (socket unix, no TCP) -- ej.
# "postgresql://postgres:@/postgres?host=/tmp/...". Se crea una BD
# propia y se arma la URI final reemplazando solo el nombre de la BD.
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

# --- admin user ---
conn.execute(
    "INSERT INTO roles (name, description) VALUES ('admin', 'Acceso total al sistema') ON CONFLICT DO NOTHING;"
)
conn.execute(
    """INSERT INTO users (username, password_hash, full_name, email)
       VALUES ('tester', %s, 'Tester', 'tester@example.com')
       ON CONFLICT DO NOTHING;""",
    (hash_password("Password123"),),
)
row = conn.execute("SELECT id FROM users WHERE username = 'tester';").fetchone()
user_id = row[0]
role_row = conn.execute("SELECT id FROM roles WHERE name = 'admin';").fetchone()
conn.execute(
    "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
    (user_id, role_row[0]),
)


def make_agent(hostname):
    ep = conn.execute(
        "INSERT INTO endpoints (hostname, os, os_version) VALUES (%s, 'Windows', '11') RETURNING id;",
        (hostname,),
    ).fetchone()
    endpoint_id = ep[0]
    ag = conn.execute(
        "INSERT INTO agents (endpoint_id, agent_version) VALUES (%s, '1.0') RETURNING id;",
        (endpoint_id,),
    ).fetchone()
    agent_id = ag[0]
    token = f"token-{hostname}"
    credential_hash = hashlib.sha256(token.encode()).hexdigest()
    conn.execute(
        "INSERT INTO agent_credentials (agent_id, credential_hash) VALUES (%s, %s);",
        (agent_id, credential_hash),
    )
    return agent_id, token


agent_a, token_a = make_agent("endpoint-A-sin-override")
agent_b, token_b = make_agent("endpoint-B-override-threshold")
agent_c, token_c = make_agent("endpoint-C-override-weight")
agent_d, token_d = make_agent("endpoint-D-override-window")
agent_e, token_e = make_agent("endpoint-E-regla-desactivada")
agent_trace, token_trace = make_agent("endpoint-traza-integracion")

rule_row = conn.execute(
    "SELECT id, weight, threshold, window_seconds FROM heuristic_rules WHERE name = 'Modificacion Masiva Archivos';"
).fetchone()
rule_id, global_weight, global_threshold, global_window = rule_row
global_weight, global_threshold = float(global_weight), float(global_threshold)
print(f"Regla de prueba: 'Modificacion Masiva Archivos' id={rule_id} global weight={global_weight} threshold={global_threshold} window={global_window}")

conn.close()

# --- levantar uvicorn real ---
env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8071"],
    cwd=os.path.join(REPO, "server"),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

BASE = "http://127.0.0.1:8071"

try:
    # Esperar a que levante, drenando stdout para no llenar el pipe.
    log_lines = []

    def drain():
        for line in proc.stdout:
            log_lines.append(line)

    threading.Thread(target=drain, daemon=True).start()

    ok = False
    for _ in range(60):
        try:
            r = httpx.get(BASE + "/docs", timeout=1, trust_env=False)
            if r.status_code == 200:
                ok = True
                break
        except Exception:
            pass
        time_mod.sleep(0.5)
    check("uvicorn levantó correctamente", ok)

    client = httpx.Client(base_url=BASE, trust_env=False)
    r = client.post("/login", json={"username": "tester", "password": "Password123"})
    check("Login admin OK", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

    def agent_rule_policy(token):
        r = client.get("/agent/rule-policy", headers={"X-Agent-Credential": token})
        return r

    def send_event_and_alert(token, count=25, matched_rules=None):
        """Manda 'count' eventos file_modified y reporta una alerta con
        'matched_rules' (default: solo HR-01, igual que reporta
        file_monitor.py de verdad cuando solo esa regla coincide)."""
        for i in range(count):
            client.post(
                "/agent/events",
                headers={"X-Agent-Credential": token},
                json={"event_type": "file_modified", "description": "x", "metadata": {"file_path": f"C:/f{i}.txt", "extension": ".txt"}},
            )
        r = client.post(
            "/agent/alerts",
            headers={"X-Agent-Credential": token},
            json={
                "title": "Prueba HR-01",
                "description": "prueba",
                "matched_rules": matched_rules or ["Modificacion Masiva Archivos"],
            },
        )
        return r

    # ---------------- Escenario A: sin override ----------------
    r = client.get(f"/api/agents/{agent_a}/rules")
    check("A: GET rules 200", r.status_code == 200, r.text[:200])
    rule_a = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("A: has_override=False", rule_a["has_override"] is False)
    check("A: override es None", rule_a["override"] is None)
    check("A: effective == global", rule_a["effective"] == rule_a["global"])

    rp = agent_rule_policy(token_a)
    policy_rule_a = next((x for x in rp.json()["rules"] if x["name"] == "Modificacion Masiva Archivos"), None)
    check("A: rule-policy trae threshold global", policy_rule_a is not None and float(policy_rule_a["threshold"]) == global_threshold)

    # ---------------- Escenario B: override de threshold ----------------
    new_threshold = global_threshold + 30  # bien distinto del global
    r = client.patch(f"/api/agents/{agent_b}/rules/{rule_id}", json={"threshold": new_threshold})
    check("B: PATCH override threshold 200", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/agents/{agent_b}/rules")
    rule_b = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("B: override.threshold = nuevo valor", rule_b["override"]["threshold"] == new_threshold)
    check("B: override.weight sigue None (no tocado)", rule_b["override"]["weight"] is None)
    check("B: effective.threshold = override", rule_b["effective"]["threshold"] == new_threshold)
    check("B: effective.weight = global (heredado)", rule_b["effective"]["weight"] == global_weight)

    rp = agent_rule_policy(token_b)
    policy_rule_b = next((x for x in rp.json()["rules"] if x["name"] == "Modificacion Masiva Archivos"), None)
    check("B: rule-policy refleja threshold personalizado", policy_rule_b is not None and float(policy_rule_b["threshold"]) == new_threshold)

    # ---------------- Escenario C: override de weight ----------------
    new_weight = global_weight + 40
    r = client.patch(f"/api/agents/{agent_c}/rules/{rule_id}", json={"weight": new_weight})
    check("C: PATCH override weight 200", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/agents/{agent_c}/rules")
    rule_c = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("C: effective.weight = override", rule_c["effective"]["weight"] == new_weight)
    check("C: effective.threshold = global (heredado)", rule_c["effective"]["threshold"] == global_threshold)

    alert_resp = send_event_and_alert(token_c, count=25)
    check("C: report_alert 200", alert_resp.status_code == 200, alert_resp.text[:300])
    if alert_resp.status_code == 200:
        risk_score = alert_resp.json().get("risk_score")
        check(
            "C: risk_score usa el weight EFECTIVO del endpoint, no el global",
            risk_score == new_weight,
            f"risk_score={risk_score} esperado={new_weight}",
        )

    # ---------------- Escenario D: override de window ----------------
    new_window = (global_window or 10) + 100
    r = client.patch(f"/api/agents/{agent_d}/rules/{rule_id}", json={"window_seconds": new_window})
    check("D: PATCH override window 200", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/agents/{agent_d}/rules")
    rule_d = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("D: effective.window_seconds = override", rule_d["effective"]["window_seconds"] == new_window)
    rp = agent_rule_policy(token_d)
    policy_rule_d = next((x for x in rp.json()["rules"] if x["name"] == "Modificacion Masiva Archivos"), None)
    check("D: rule-policy refleja window personalizada", policy_rule_d is not None and policy_rule_d["window_seconds"] == new_window)

    # ---------------- Escenario E: regla desactivada para este endpoint ----------------
    r = client.patch(f"/api/agents/{agent_e}/rules/{rule_id}", json={"is_active": False})
    check("E: PATCH override is_active=False 200", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/agents/{agent_e}/rules")
    rule_e = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("E: effective.is_active = False", rule_e["effective"]["is_active"] is False)

    rp = agent_rule_policy(token_e)
    names_e = {x["name"] for x in rp.json()["rules"]}
    check("E: rule-policy NO incluye la regla desactivada para este endpoint", "Modificacion Masiva Archivos" not in names_e)

    # Otro endpoint (A, sin override) sigue viendo la regla activa -- el
    # override de E es puntual, no afecta al resto.
    rp_a = agent_rule_policy(token_a)
    names_a = {x["name"] for x in rp_a.json()["rules"]}
    check("E: otro endpoint (A) sigue viendo la regla activa (override no es global)", "Modificacion Masiva Archivos" in names_a)

    # DELETE del override de E -- vuelve a heredar el global (activa de nuevo)
    r = client.delete(f"/api/agents/{agent_e}/rules/{rule_id}")
    check("E: DELETE override 200", r.status_code == 200, r.text[:300])
    r = client.get(f"/api/agents/{agent_e}/rules")
    rule_e2 = next(x for x in r.json()["rules"] if x["id"] == rule_id)
    check("E: tras DELETE, has_override=False de nuevo", rule_e2["has_override"] is False)
    check("E: tras DELETE, effective vuelve a ser el global", rule_e2["effective"] == rule_e2["global"])

    # ---------------- Traza de integración completa ----------------
    # agente detecta -> evento -> matched_rules -> servidor resuelve
    # config EFECTIVA (override de agent_rule para este endpoint) ->
    # score -> severidad -> alerta -> incidente -> condición de
    # aislamiento. Override de weight=100 en HR-01 para este endpoint
    # puntual + una segunda regla "fuerte" (HR-04, con su weight
    # GLOBAL, sin override) -- para cumplir la condición real de
    # incidente (score>=75 Y al menos 2 reglas fuertes distintas,
    # sección 28: "CRÍTICO por score solo no alcanza"), no solo el
    # score.
    r = client.patch(f"/api/agents/{agent_trace}/rules/{rule_id}", json={"weight": 100, "threshold": 5, "window_seconds": 10})
    check("Traza: override weight=100 threshold=5 creado para HR-01", r.status_code == 200, r.text[:300])

    trace_resp = send_event_and_alert(
        token_trace, count=25,
        matched_rules=["Modificacion Masiva Archivos", "Escritura Intensiva Archivos"],
    )
    check("Traza: report_alert 200", trace_resp.status_code == 200, trace_resp.text[:300])
    if trace_resp.status_code == 200:
        body = trace_resp.json()
        check("Traza: risk_score=100 (peso efectivo personalizado + HR-04 global, acotado a 100)", body.get("risk_score") == 100)
        check("Traza: severidad=CRÍTICO", body.get("severity") == "CRÍTICO", str(body))
        check("Traza: incident_created=True (score>=75 y 2 reglas fuertes distintas)", body.get("incident_created") is True, str(body))
        check("Traza: incident_id no es None", body.get("incident_id") is not None)
        check(
            "Traza: isolation_requested=True (Condición B: score>=75 + 2 indicadores fuertes de archivos)",
            body.get("isolation_requested") is True, str(body),
        )

        # Verificar en BD: incidente creado, alert_rule con el weight
        # EFECTIVO de este endpoint para HR-01 (no el global 25) y el
        # weight GLOBAL para HR-04 (sin override) -- confirma que el
        # override es POR REGLA, no todo-o-nada para el endpoint.
        conn2 = psycopg.connect(DATABASE_URL)
        cur = conn2.cursor()
        cur.execute("SELECT incident_id, risk_score FROM alerts WHERE agent_id = %s ORDER BY id DESC LIMIT 1;", (agent_trace,))
        incident_id, db_risk_score = cur.fetchone()
        check("Traza (BD): alerts.risk_score = 100", float(db_risk_score) == 100.0)
        check("Traza (BD): se creó un incidente automático", incident_id is not None)

        cur.execute(
            """SELECT heuristic_rules.name, alert_rule.weight_applied
               FROM alert_rule
               JOIN alerts ON alerts.id = alert_rule.alert_id
               JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
               WHERE alerts.agent_id = %s;""",
            (agent_trace,),
        )
        applied = {name: float(w) for name, w in cur.fetchall()}
        check(
            "Traza (BD): HR-01 usa el weight EFECTIVO de este endpoint (100), no el global (25)",
            applied.get("Modificacion Masiva Archivos") == 100.0, str(applied),
        )
        check(
            "Traza (BD): HR-04 usa su weight GLOBAL (15, sin override) -- el override es por regla, no por endpoint entero",
            applied.get("Escritura Intensiva Archivos") == 15.0, str(applied),
        )

        # 'agent_rule' del endpoint de traza sigue existiendo intacta --
        # reportar una alerta no la borra ni la modifica.
        cur.execute("SELECT threshold, window_seconds, weight, is_active FROM agent_rule WHERE agent_id = %s AND rule_id = %s;", (agent_trace, rule_id))
        override_row = cur.fetchone()
        check("Traza (BD): agent_rule del endpoint sigue intacta tras la alerta", override_row is not None and float(override_row[2]) == 100.0)

        cur.execute("SELECT status, isolation_type, reason FROM host_isolations WHERE incident_id = %s;", (incident_id,))
        isolation_row = cur.fetchone()
        check(
            "Traza (BD): host_isolations tiene una fila REQUESTED -- una orden real, nadie la ejecutó todavía "
            "(esta prueba no levanta un agente con IsolationSyncThread)",
            isolation_row is not None and isolation_row[0] == "REQUESTED", str(isolation_row),
        )
        conn2.close()

finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    pg.cleanup()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_endpoint_config_and_e2e.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
