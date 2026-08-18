"""Series MI (aislamiento manual) y MR (liberación/UNISOLATE) de la
especificación "ALFA_SENTINEL -- AISLAMIENTO DE HOST, MODO DEVELOPMENT,
LABORATORIO Y PRODUCCIÓN" (2026-08-17, ver PENDIENTES.md).

Prueba contra un servidor real (pgserver + uvicorn), igual que
test_episodios_incidentes_aislamiento.py -- el disparo manual
(POST /incidents/{id}/isolate) reutiliza EXACTAMENTE el mismo
mecanismo que el automático (misma tabla, mismo agente, mismo
ejecutor), así que estas pruebas verifican: creación de la orden con
el usuario real (requested_by), el guard de no-duplicar (sección 27:
"pulsar Aislar dos veces... no debe duplicar"), el ciclo completo de
liberación (UNISOLATE, sección 18), y la validación cruzada de
POST /agent/isolation-status/report (no confundir una confirmación de
aislar con una de liberar).

Ejecutar: python3 tests/heuristic/test_aislamiento_manual_liberacion.py
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

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_manual_iso_pgdata_")
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
       VALUES ('tester', %s, 'Tester Manual', 'tester.manual@example.com') ON CONFLICT DO NOTHING;""",
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


agent_m1, token_m1 = make_agent("endpoint-MI1-manual")       # MI-01..MI-04 (ciclo completo)
agent_m2, token_m2 = make_agent("endpoint-MI2-duplicado")    # MI-05 (guard de duplicado)
agent_m3, token_m3 = make_agent("endpoint-MI3-crossval")     # MI-06 (validación cruzada)
agent_m4, token_m4 = make_agent("endpoint-MI4-cerrado")      # MI-02 (incidente cerrado)

rule_id_by_name = {}
for row in conn.execute("SELECT id, name FROM heuristic_rules;").fetchall():
    rule_id_by_name[row[1]] = row[0]

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")
env.pop("ALFA_SENTINEL_ENV", None)  # servidor no depende de esto -- solo el agente

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8080"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8080"

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

    def db_conn():
        return psycopg.connect(DATABASE_URL)

    def report(token, matched_rules):
        return httpx.post(
            f"{BASE}/agent/alerts",
            json={"title": "Prueba aislamiento manual", "description": "Serie MI/MR", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def override_weight(agent_id, rule_name, weight):
        rid = rule_id_by_name[rule_name]
        resp = client.patch(f"/api/agents/{agent_id}/rules/{rid}", json={"weight": weight})
        assert resp.status_code == 200, resp.text

    def isolation_row(isolation_id):
        c = db_conn()
        row = c.execute(
            "SELECT status, requested_by, executed_at, released_at, result, reason FROM host_isolations WHERE id = %s;",
            (isolation_id,),
        ).fetchone()
        c.close()
        return row

    # ================= Preparar un incidente SIN aislamiento automático =================
    # Actualizado 2026-08-18 (ver PENDIENTES.md): ahora TODA alerta
    # CRÍTICA aísla automáticamente (ya no depende de reglas fuertes
    # adicionales), y un incidente puede abrirse también en severidad
    # ALTO (score>=50) si hay evidencia (>=3 reglas distintas
    # coincidiendo). Para seguir probando el aislamiento MANUAL sin que
    # el automático se adelante, este setup usa los pesos REALES (sin
    # override) de 3 reglas distintas: 25 (Modificacion Masiva
    # Archivos) + 10 (Proceso Sospechoso) + 5 (Consumo CPU Elevado) +
    # 10 de bonus de correlación (3 reglas distintas) = score 50 ->
    # severidad ALTO, incidente creado por evidencia (3 reglas), pero
    # NO CRÍTICO -> no dispara aislamiento automático.
    r_setup = report(token_m1, ["Modificacion Masiva Archivos", "Proceso Sospechoso", "Consumo CPU Elevado"])
    check("Setup: report_alert 200", r_setup.status_code == 200, r_setup.text[:300])
    body_setup = r_setup.json()
    check("Setup: se creó un incidente", body_setup["incident_id"] is not None, str(body_setup))
    check("Setup: severidad ALTO (score 50, no CRÍTICO)", body_setup["severity"] == "ALTO", str(body_setup))
    check("Setup: NO se disparó aislamiento automático (severidad ALTO, no CRÍTICO)", body_setup["isolation_requested"] is False, str(body_setup))
    incident_m1 = body_setup["incident_id"]

    # ================= MI-01: incidente inexistente =================
    r = client.post("/incidents/999999/isolate")
    check("MI-01: incidente inexistente -> 404", r.status_code == 404, f"status={r.status_code}")

    # ================= MI-02: aislamiento manual real =================
    r = client.post(f"/incidents/{incident_m1}/isolate")
    check("MI-02: POST /incidents/{id}/isolate 200", r.status_code == 200, r.text[:300])
    body = r.json()
    check("MI-02: status devuelto REQUESTED", body.get("status") == "REQUESTED", str(body))
    isolation_m1 = body["isolation_id"]

    row = isolation_row(isolation_m1)
    check("MI-02: fila creada con status REQUESTED", row[0] == "REQUESTED", str(row))
    check("MI-02: requested_by es el usuario real (no NULL como el automático)", row[1] == user_id, str(row))
    check("MI-02: reason menciona aislamiento manual", "manual" in (row[5] or "").lower(), str(row))

    # ================= MI-03: no duplicar (sección 27) =================
    r_dup = client.post(f"/incidents/{incident_m1}/isolate")
    check("MI-03: segunda orden sobre el mismo incidente -> 409", r_dup.status_code == 409, f"status={r_dup.status_code}")
    c = db_conn()
    count = c.execute("SELECT COUNT(*) FROM host_isolations WHERE incident_id = %s;", (incident_m1,)).fetchone()[0]
    c.close()
    check("MI-03: sigue habiendo UNA sola fila para este incidente", count == 1, f"count={count}")

    # ================= MI-04: el agente confirma (desarrollo, simulado) =================
    status_resp = httpx.get(f"{BASE}/agent/isolation-status", headers={"X-Agent-Credential": token_m1}, timeout=10)
    check("MI-04: GET /agent/isolation-status 200", status_resp.status_code == 200, status_resp.text[:300])
    pending = status_resp.json().get("pending")
    check("MI-04: hay una orden pendiente", pending is not None, str(status_resp.json()))
    check("MI-04: action == ISOLATE", pending is not None and pending.get("action") == "ISOLATE", str(pending))

    confirm = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m1, "status": "EXECUTED", "result": "[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO (prueba manual)."},
        headers={"X-Agent-Credential": token_m1},
        timeout=10,
    )
    check("MI-04: POST /agent/isolation-status/report 200", confirm.status_code == 200, confirm.text[:300])
    row = isolation_row(isolation_m1)
    check("MI-04: status final EXECUTED", row[0] == "EXECUTED", str(row))
    check("MI-04: executed_at quedó registrado", row[2] is not None, str(row))

    # ================= MR-01: liberar solo si está EXECUTED =================
    # Reutilizamos incident_m1/isolation_m1, ya EXECUTED.
    r_release_early = client.post("/host-isolations/999999/release")
    check("MR-01: orden inexistente -> 404", r_release_early.status_code == 404, f"status={r_release_early.status_code}")

    r_release = client.post(f"/host-isolations/{isolation_m1}/release")
    check("MR-02: POST /host-isolations/{id}/release 200 sobre fila EXECUTED", r_release.status_code == 200, r_release.text[:300])
    row = isolation_row(isolation_m1)
    check("MR-02: status pasó a RELEASE_REQUESTED", row[0] == "RELEASE_REQUESTED", str(row))

    # No se puede volver a pedir liberación mientras sigue RELEASE_REQUESTED (no está EXECUTED).
    r_release_dup = client.post(f"/host-isolations/{isolation_m1}/release")
    check("MR-03: liberar de nuevo mientras RELEASE_REQUESTED -> 409", r_release_dup.status_code == 409, f"status={r_release_dup.status_code}")

    # GET /agent/isolation-status ahora debe ofrecer la orden de LIBERAR.
    status_resp2 = httpx.get(f"{BASE}/agent/isolation-status", headers={"X-Agent-Credential": token_m1}, timeout=10)
    pending2 = status_resp2.json().get("pending")
    check("MR-04: pending.action == RELEASE", pending2 is not None and pending2.get("action") == "RELEASE", str(pending2))
    check("MR-04: mismo isolation_id que antes", pending2 is not None and pending2.get("isolation_id") == isolation_m1, str(pending2))

    # El agente confirma la liberación (desarrollo, simulado).
    confirm_release = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m1, "status": "RELEASED", "result": "[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO."},
        headers={"X-Agent-Credential": token_m1},
        timeout=10,
    )
    check("MR-05: POST report(RELEASED) 200", confirm_release.status_code == 200, confirm_release.text[:300])
    row = isolation_row(isolation_m1)
    check("MR-05: status final RELEASED", row[0] == "RELEASED", str(row))
    check("MR-05: released_at quedó registrado", row[3] is not None, str(row))

    # Después de liberado, se puede volver a aislar manualmente el mismo incidente sin conflicto.
    r_reisolate = client.post(f"/incidents/{incident_m1}/isolate")
    check("MR-06: tras liberar, una nueva orden manual sobre el mismo incidente es aceptada", r_reisolate.status_code == 200, r_reisolate.text[:300])

    # ================= MI-05: incidente cerrado no se puede aislar =================
    r_close_setup = report(token_m4, ["Modificacion Masiva Archivos"])
    check("MI-05 setup: report_alert 200", r_close_setup.status_code == 200)
    c = db_conn()
    alert_row = c.execute("SELECT id FROM alerts WHERE agent_id = %s ORDER BY id DESC LIMIT 1;", (agent_m4,)).fetchone()
    inc = c.execute(
        "INSERT INTO incidents (agent_id, title, status) VALUES (%s, 'Incidente cerrado de prueba', 'CLOSED') RETURNING id;",
        (agent_m4,),
    ).fetchone()
    c.commit()
    c.close()
    incident_closed = inc[0]
    r_closed = client.post(f"/incidents/{incident_closed}/isolate")
    check("MI-05: incidente CLOSED -> 409, no se aísla", r_closed.status_code == 409, f"status={r_closed.status_code}")

    # ================= MI-06: validación cruzada del reporte del agente =================
    # Mismo criterio que el setup de MI-01: pesos reales (sin
    # override) de 3 reglas distintas -> score 50 -> ALTO, incidente
    # por evidencia (3 reglas), sin aislamiento automático (no CRÍTICO).
    r_setup3 = report(token_m3, ["Modificacion Masiva Archivos", "Proceso Sospechoso", "Consumo CPU Elevado"])
    incident_m3 = r_setup3.json()["incident_id"]
    check("MI-06 setup: incidente creado sin aislamiento automático", incident_m3 is not None and r_setup3.json()["isolation_requested"] is False, r_setup3.text[:300])

    r_iso3 = client.post(f"/incidents/{incident_m3}/isolate")
    isolation_m3 = r_iso3.json()["isolation_id"]

    # Reportar RELEASED sobre una orden que en realidad sigue REQUESTED (nunca se confirmó EXECUTED) -> debe rechazarse.
    bad_release = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m3, "status": "RELEASED", "result": "intento inválido"},
        headers={"X-Agent-Credential": token_m3},
        timeout=10,
    )
    check("MI-06: reportar RELEASED sobre una orden REQUESTED -> 404 (validación cruzada)", bad_release.status_code == 404, f"status={bad_release.status_code}")

    # Confirmar EXECUTED de verdad, después intentar reportar EXECUTED de nuevo (ya no está REQUESTED) -> debe rechazarse.
    ok_confirm = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m3, "status": "EXECUTED", "result": "ok"},
        headers={"X-Agent-Credential": token_m3},
        timeout=10,
    )
    check("MI-06: confirmar EXECUTED real 200", ok_confirm.status_code == 200)

    double_confirm = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m3, "status": "EXECUTED", "result": "doble confirmación"},
        headers={"X-Agent-Credential": token_m3},
        timeout=10,
    )
    check("MI-06: confirmar EXECUTED dos veces -> 404 (ya no está REQUESTED)", double_confirm.status_code == 404, f"status={double_confirm.status_code}")

    # status inválido -> 422.
    invalid_status = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m3, "status": "ALGO_INVENTADO", "result": "x"},
        headers={"X-Agent-Credential": token_m3},
        timeout=10,
    )
    check("MI-06: status inválido -> 422", invalid_status.status_code == 422, f"status={invalid_status.status_code}")

    # ================= MR-07: falla real al liberar -> vuelve a EXECUTED, no queda huérfano =================
    r_release3 = client.post(f"/host-isolations/{isolation_m3}/release")
    check("MR-07 setup: release aceptado", r_release3.status_code == 200, r_release3.text[:300])
    fail_release = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_m3, "status": "RELEASE_FAILED", "result": "[execution_mode=CONTROLLED_TEST] firewall ocupado (prueba)."},
        headers={"X-Agent-Credential": token_m3},
        timeout=10,
    )
    check("MR-07: reportar RELEASE_FAILED 200", fail_release.status_code == 200, fail_release.text[:300])
    row3 = isolation_row(isolation_m3)
    check("MR-07: status vuelve a EXECUTED (sigue aislado de verdad, no un estado inventado)", row3[0] == "EXECUTED", str(row3))
    check("MR-07: released_at sigue NULL (no se liberó de verdad)", row3[3] is None, str(row3))

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
