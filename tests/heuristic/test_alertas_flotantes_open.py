"""Prueba de la extensión de GET /alerts/open (2026-08-17, ver
PENDIENTES.md, "Alertas flotantes globales de alta prioridad").

La capa de notificaciones flotantes (frontend/src/hooks/useGlobalAlerts.ts)
es pura lógica de polling/dedupe/escalada en TypeScript sin runtime de
pruebas en este proyecto (igual que el resto de la UI React, verificada
con `npm run build` + revisión de escenarios) -- lo que SÍ es responsabilidad
real del backend, y por eso se prueba acá, es que /alerts/open devuelva los
tres campos nuevos (risk_score, incident_id, isolation_status) con los
valores REALES en cada escenario relevante para esa capa:

  F-01: alerta ALTO sin incidente -> incident_id/isolation_status null.
  F-02: alerta CRÍTICO con Condición B (>=2 reglas fuertes, score>=75)
        -> incident_id no nulo, isolation_status='REQUESTED' de inmediato
        (nunca 'RECOMMENDED', sección 23).
  F-03: el agente confirma la ejecución real (POST
        /agent/isolation-status/report) -> isolation_status pasa a
        'EXECUTED' en el MISMO /alerts/open (el frontend debe ver el
        estado real, nunca uno optimista/desactualizado, sección 32).
  F-04: escalada de severidad de una alerta ya abierta (mismo alert_id,
        misma fila) -- /alerts/open refleja la severidad nueva, que es
        justo lo que useGlobalAlerts.ts usa para decidir "re-notificar"
        (sección 9/10/12).

Ejecutar: python3 tests/heuristic/test_alertas_flotantes_open.py
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


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_flotantes_pgdata_")
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


def make_agent(hostname):
    ep = conn.execute(
        "INSERT INTO endpoints (hostname, os, os_version) VALUES (%s, 'Windows', '11') RETURNING id;",
        (hostname,),
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


agent_alto, token_alto = make_agent("endpoint-F1-alto")          # F-01
agent_crit, token_crit = make_agent("endpoint-F2-critico-iso")   # F-02/F-03
agent_esc, token_esc = make_agent("endpoint-F3-escalada")        # F-04

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8079"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8079"

try:
    def _drain():
        for line in proc.stdout:
            pass
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

    def report(token, matched_rules):
        return httpx.post(
            f"{BASE}/agent/alerts",
            json={"title": "Prueba flotantes", "description": "Prueba F-01..F-04", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def open_alerts():
        resp = client.get("/alerts/open")
        assert resp.status_code == 200, resp.text
        return resp.json()["alerts"]

    def find(alerts, alert_id):
        return next((a for a in alerts if a["id"] == alert_id), None)

    # ================= F-01: ALTO sin incidente =================
    # HR-01 (25) + HR-04 (15) + HR-09 (15) = 55 + bonus 3 reglas (+10) = 65 -> ALTO, sin incidente.
    r1 = report(token_alto, ["Modificacion Masiva Archivos", "Escritura Intensiva Archivos", "Eliminacion Anomala Archivos"])
    check("F-01: report_alert 200", r1.status_code == 200, r1.text[:300])
    body1 = r1.json()
    check("F-01: severidad ALTO", 50 <= body1["risk_score"] < 75, str(body1))
    check("F-01: sin incidente", body1["incident_id"] is None, str(body1))

    alerts = open_alerts()
    row1 = find(alerts, body1["alert_id"])
    check("F-01: aparece en /alerts/open", row1 is not None, str(alerts))
    if row1:
        check("F-01: severity == ALTO", row1["severity"] == "ALTO", str(row1))
        check("F-01: risk_score coincide", abs(row1["risk_score"] - body1["risk_score"]) < 0.01, str(row1))
        check("F-01: incident_id null", row1["incident_id"] is None, str(row1))
        check("F-01: isolation_status null", row1["isolation_status"] is None, str(row1))

    # ================= F-02: CRÍTICO + Condición B (aislamiento REQUESTED) =================
    # HR-01(25)+HR-02(20)+HR-04(15)+HR-09(15) = 75 + bonus 4 reglas (+15) = 90 -> CRÍTICO,
    # 4 reglas fuertes de actividad de archivos (>=2) -> Condición B: incidente + aislamiento REQUESTED.
    r2 = report(token_crit, [
        "Modificacion Masiva Archivos", "Renombrado Extension Anomala",
        "Escritura Intensiva Archivos", "Eliminacion Anomala Archivos",
    ])
    check("F-02: report_alert 200", r2.status_code == 200, r2.text[:300])
    body2 = r2.json()
    check("F-02: severidad CRÍTICO (score >= 75)", body2["risk_score"] >= 75, str(body2))
    check("F-02: se creó incidente", body2["incident_id"] is not None, str(body2))
    check("F-02: isolation_requested == True", body2["isolation_requested"] is True, str(body2))

    alerts = open_alerts()
    row2 = find(alerts, body2["alert_id"])
    check("F-02: aparece en /alerts/open", row2 is not None, str(alerts))
    if row2:
        check("F-02: severity == CRÍTICO", row2["severity"] == "CRÍTICO", str(row2))
        check("F-02: incident_id coincide", row2["incident_id"] == body2["incident_id"], str(row2))
        check(
            "F-02: isolation_status == REQUESTED (nunca RECOMMENDED)",
            row2["isolation_status"] == "REQUESTED", str(row2),
        )

    # ================= F-03: agente confirma ejecución -> estado REAL visible =================
    status_resp = httpx.get(f"{BASE}/agent/isolation-status", headers={"X-Agent-Credential": token_crit}, timeout=10)
    check("F-03: GET /agent/isolation-status 200", status_resp.status_code == 200, status_resp.text[:300])
    pending = status_resp.json().get("pending")
    check("F-03: hay una orden pendiente", pending is not None, str(status_resp.json()))

    if pending:
        confirm = httpx.post(
            f"{BASE}/agent/isolation-status/report",
            json={"isolation_id": pending["isolation_id"], "status": "EXECUTED", "result": "Prueba: aislamiento simulado ejecutado"},
            headers={"X-Agent-Credential": token_crit},
            timeout=10,
        )
        check("F-03: POST /agent/isolation-status/report 200", confirm.status_code == 200, confirm.text[:300])

    alerts = open_alerts()
    row2b = find(alerts, body2["alert_id"])
    if row2b:
        check(
            "F-03: isolation_status == EXECUTED (estado real, no RECOMMENDED/REQUESTED desactualizado)",
            row2b["isolation_status"] == "EXECUTED", str(row2b),
        )

    # ================= F-04: escalada de severidad de una alerta ya abierta =================
    # Primer evento: solo HR-06 (débil, score bajo) -> MEDIO/BAJO, sin incidente.
    r3a = report(token_esc, ["Consumo CPU Elevado"])
    check("F-04a: report_alert 200", r3a.status_code == 200)
    body3a = r3a.json()
    check("F-04a: score bajo, no CRÍTICO todavía", body3a["risk_score"] < 75, str(body3a))
    alert_esc_id = body3a["alert_id"]

    # Mismo episodio, nueva evidencia fuerte que empuja a CRÍTICO -- misma alerta (alert_id), severidad nueva.
    r3b = report(token_esc, [
        "Modificacion Masiva Archivos", "Renombrado Extension Anomala",
        "Escritura Intensiva Archivos", "Eliminacion Anomala Archivos",
    ])
    check("F-04b: report_alert 200", r3b.status_code == 200)
    body3b = r3b.json()
    check("F-04b: sigue siendo la MISMA alerta (mismo episodio)", body3b["alert_id"] == alert_esc_id, str(body3b))
    check("F-04b: ahora CRÍTICO (score >= 75)", body3b["risk_score"] >= 75, str(body3b))

    alerts = open_alerts()
    row3 = find(alerts, alert_esc_id)
    check("F-04: /alerts/open refleja la severidad ESCALADA (CRÍTICO), no la original", row3 is not None and row3["severity"] == "CRÍTICO", str(row3))

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)

print()
total = len(RESULTS)
passed = sum(1 for _, ok in RESULTS if ok)
print(f"{passed}/{total} pruebas pasaron")
if passed != total:
    sys.exit(1)
