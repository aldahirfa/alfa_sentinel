"""Serie H/Q/G de "Revisión y corrección integral de ALFA-Sentinel"
(2026-08-18, ver PENDIENTES.md).

Cubre el caso concreto que pidió el usuario (problema Q): un mismo
endpoint con TRES incidentes (PC-01 -> INC-1, INC-2, INC-3). Se aísla
desde INC-1 -- INC-2 e INC-3 deben reconocer el endpoint como aislado
(sin ofrecer "Aislar" de nuevo) en TODAS las fuentes que lo muestran
(COMBINED_CTE/'/api/incidentes', el drawer, '/alerts/open',
'/api/respuesta'), y un segundo intento real de aislar -- manual desde
otro incidente O automático desde un tercer episodio -- debe ser
rechazado, no crear una segunda orden 'host_isolations' para el mismo
agente (problema H, prueba obligatoria R-13/R-14).

También cubre el problema G (vista operativa por defecto oculta
cerradas/resueltas, con 'view=todos' disponible).

No usa mocks: llama a los endpoints HTTP reales de server/main.py
(mismo patrón de tests/heuristic/test_episodios_incidentes_aislamiento.py).

Ejecutar: python3 tests/heuristic/test_aislamiento_pertenece_al_endpoint.py
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

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_iso_pgdata_")
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


agent_q, token_q = make_agent("PC-01-tres-incidentes")   # serie Q/H
agent_g1, token_g1 = make_agent("endpoint-G-vista")       # serie G

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

    def db_conn():
        return psycopg.connect(DATABASE_URL)

    def report(token, matched_rules):
        return httpx.post(
            f"{BASE}/agent/alerts",
            json={"title": "Prueba", "description": "Serie H/Q/G", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def age_episode_evidence(agent_id, seconds_ago):
        c = db_conn()
        c.execute(
            "UPDATE alerts SET created_at = NOW() - (%s || ' seconds')::INTERVAL WHERE agent_id = %s AND status IN ('NEW', 'ACKNOWLEDGED');",
            (seconds_ago, agent_id),
        )
        c.execute(
            "UPDATE alert_rule SET matched_at = NOW() - (%s || ' seconds')::INTERVAL "
            "WHERE alert_id IN (SELECT id FROM alerts WHERE agent_id = %s AND status IN ('NEW', 'ACKNOWLEDGED'));",
            (seconds_ago, agent_id),
        )
        c.commit()
        c.close()

    def host_isolations_for(agent_id):
        c = db_conn()
        rows = c.execute(
            "SELECT id, incident_id, status FROM host_isolations WHERE agent_id = %s ORDER BY id ASC;",
            (agent_id,),
        ).fetchall()
        c.close()
        return rows

    # ============= Q/H: tres incidentes, mismo endpoint =============

    # INC-1: honeyfile + modificación masiva -> condición A de incidente
    # Y de aislamiento -> se crea incidente 1 y una orden REQUESTED real.
    r1 = report(token_q, ["Acceso Honeyfile", "Modificacion Masiva Archivos"])
    check("Q: report 1 -> 200", r1.status_code == 200, r1.text[:200])
    body1 = r1.json()
    incident_1 = body1["incident_id"]
    check("Q: INC-1 se creó automáticamente", incident_1 is not None, str(body1))

    isolations_after_1 = host_isolations_for(agent_q)
    check("Q: se creó exactamente 1 orden de aislamiento tras INC-1", len(isolations_after_1) == 1, str(isolations_after_1))
    check("Q: la orden nació 'REQUESTED'", isolations_after_1 and isolations_after_1[0][2] == "REQUESTED", str(isolations_after_1))
    isolation_row_id = isolations_after_1[0][0] if isolations_after_1 else None

    # INC-2: episodio nuevo (evidencia envejecida > EPISODE_WINDOW_SECONDS)
    # -- mismo agente, ya aislado. La condición de aislamiento se vuelve
    # a cumplir (honeyfile de nuevo), pero el guard debe reconocer que
    # este AGENTE ya está aislado y NO insertar una segunda orden.
    age_episode_evidence(agent_q, 130)
    r2 = report(token_q, ["Acceso Honeyfile", "Modificacion Masiva Archivos"])
    check("Q: report 2 -> 200", r2.status_code == 200, r2.text[:200])
    body2 = r2.json()
    incident_2 = body2["incident_id"]
    check("Q: INC-2 es un incidente DISTINTO de INC-1", incident_2 is not None and incident_2 != incident_1, str(body2))

    isolations_after_2 = host_isolations_for(agent_q)
    check(
        "Q/H: el camino AUTOMÁTICO no duplicó la orden -- sigue habiendo 1 sola fila en host_isolations para este agente",
        len(isolations_after_2) == 1,
        str(isolations_after_2),
    )

    # INC-3: mismo patrón otra vez -- tercer incidente del mismo agente.
    age_episode_evidence(agent_q, 130)
    r3 = report(token_q, ["Acceso Honeyfile", "Modificacion Masiva Archivos"])
    check("Q: report 3 -> 200", r3.status_code == 200, r3.text[:200])
    body3 = r3.json()
    incident_3 = body3["incident_id"]
    check("Q: INC-3 es un incidente DISTINTO de INC-1 e INC-2", incident_3 is not None and incident_3 not in (incident_1, incident_2), str(body3))

    isolations_after_3 = host_isolations_for(agent_q)
    check(
        "Q/H: sigue habiendo 1 sola orden de aislamiento tras el TERCER incidente",
        len(isolations_after_3) == 1,
        str(isolations_after_3),
    )

    # GET /api/incidentes (COMBINED_CTE) -- los TRES incidentes deben
    # mostrar isolation_status = REQUESTED, no solo INC-1.
    r_list = client.get("/api/incidentes", params={"agent_id": agent_q, "view": "todos", "page_size": 50})
    check("Q: GET /api/incidentes 200", r_list.status_code == 200, r_list.text[:200])
    items_by_id = {it["id"]: it for it in r_list.json().get("items", []) if it["kind"] == "incident"}
    for inc_id, label in ((incident_1, "INC-1"), (incident_2, "INC-2"), (incident_3, "INC-3")):
        it = items_by_id.get(inc_id)
        check(
            f"Q/H: {label} (id={inc_id}) aparece en /api/incidentes con isolation_status=REQUESTED",
            it is not None and it.get("isolation_status") == "REQUESTED",
            str(it),
        )

    # Drawer de INC-2 e INC-3 -- deben resolver el MISMO isolation_id que
    # INC-1 (la fila real vive con incident_id=INC-1, pero pertenece al
    # agente) y el mismo status.
    for inc_id, label in ((incident_2, "INC-2"), (incident_3, "INC-3")):
        r_drawer = client.get(f"/api/incidentes/incident/{inc_id}/drawer")
        check(f"Q/H: drawer de {label} 200", r_drawer.status_code == 200, r_drawer.text[:200])
        d = r_drawer.json()
        check(f"Q/H: drawer de {label} -- isolation_status=REQUESTED", d.get("isolation_status") == "REQUESTED", str(d.get("isolation_status")))
        check(f"Q/H: drawer de {label} -- isolation_id apunta a la orden real de INC-1", d.get("isolation_id") == isolation_row_id, f"got={d.get('isolation_id')} expected={isolation_row_id}")

    # GET /alerts/open -- misma corrección, ahora por agent_id.
    r_open = client.get("/alerts/open")
    check("Q/H: GET /alerts/open 200", r_open.status_code == 200)
    open_alerts = [a for a in r_open.json().get("alerts", []) if a.get("hostname") == "PC-01-tres-incidentes"]
    check(
        "Q/H: /alerts/open muestra isolation_status=REQUESTED para las alertas de PC-01 (incluidas las de INC-2/INC-3)",
        len(open_alerts) > 0 and all(a.get("isolation_status") == "REQUESTED" for a in open_alerts),
        str(open_alerts),
    )

    # PRUEBA CRÍTICA (R-14): un segundo aislamiento MANUAL disparado
    # desde INC-2 (un incidente DISTINTO del que originó la orden real)
    # debe ser rechazado con 409, no crear una segunda orden.
    r_dup = client.post(f"/incidents/{incident_2}/isolate")
    check("Q/H (R-14): aislar manualmente desde INC-2 -- rechazado con 409 (endpoint ya aislado)", r_dup.status_code == 409, f"status={r_dup.status_code} body={r_dup.text[:200]}")

    r_dup3 = client.post(f"/incidents/{incident_3}/isolate")
    check("Q/H (R-14): aislar manualmente desde INC-3 -- también rechazado con 409", r_dup3.status_code == 409, f"status={r_dup3.status_code}")

    isolations_final = host_isolations_for(agent_q)
    check("Q/H: después de los 2 intentos rechazados, sigue habiendo 1 sola orden real", len(isolations_final) == 1, str(isolations_final))

    # Confirmar la orden como EXECUTED (el agente real la ejecutó) y
    # verificar que los 3 incidentes reflejan 'EXECUTED', no solo INC-1.
    r_confirm = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_row_id, "status": "EXECUTED", "result": "Aislado (modo desarrollo, simulado)."},
        headers={"X-Agent-Credential": token_q},
        timeout=10,
    )
    check("Q/H: el agente confirma EXECUTED -- 200", r_confirm.status_code == 200, r_confirm.text[:200])

    r_list2 = client.get("/api/incidentes", params={"agent_id": agent_q, "view": "todos", "page_size": 50})
    items_by_id2 = {it["id"]: it for it in r_list2.json().get("items", []) if it["kind"] == "incident"}
    for inc_id, label in ((incident_1, "INC-1"), (incident_2, "INC-2"), (incident_3, "INC-3")):
        it = items_by_id2.get(inc_id)
        check(f"Q/H: tras confirmar, {label} muestra isolation_status=EXECUTED", it is not None and it.get("isolation_status") == "EXECUTED", str(it))

    # Liberar desde el drawer de INC-3 (un incidente que NUNCA tuvo su
    # propia fila en host_isolations) usando el isolation_id que ese
    # mismo drawer devolvió -- debe funcionar igual que si se liberara
    # desde INC-1.
    r_release = client.post(f"/host-isolations/{isolation_row_id}/release")
    check("Q/H: liberar usando el isolation_id resuelto vía INC-3 -- 200", r_release.status_code == 200, r_release.text[:200])

    # ============= G: vista operativa vs. historial =============

    r_g1 = report(token_g1, ["Consumo CPU Elevado"])
    check("G: report (alerta simple) -> 200", r_g1.status_code == 200)
    alert_g1_id = r_g1.json()["alert_id"] if "alert_id" in r_g1.json() else None
    if alert_g1_id is None:
        c = db_conn()
        alert_g1_id = c.execute("SELECT id FROM alerts WHERE agent_id = %s ORDER BY id DESC LIMIT 1;", (agent_g1,)).fetchone()[0]
        c.close()

    # Por defecto (view=activas, implícito) la alerta NUEVA aparece.
    r_alerts_default = client.get("/api/alerts", params={"search": "", "page_size": 50})
    ids_default = {a["id"] for a in r_alerts_default.json().get("alerts", [])}
    check("G: con la vista por defecto, la alerta NUEVA aparece", alert_g1_id in ids_default, str(sorted(ids_default))[:200])

    # Se cierra manualmente (CLOSED) -- estado final real.
    c = db_conn()
    c.execute("UPDATE alerts SET status = 'CLOSED', resolved_at = NOW() WHERE id = %s;", (alert_g1_id,))
    c.commit()
    c.close()

    r_alerts_activas = client.get("/api/alerts", params={"page_size": 50})
    ids_activas = {a["id"] for a in r_alerts_activas.json().get("alerts", [])}
    check("G: con la vista 'activas' (default), la alerta CERRADA queda afuera", alert_g1_id not in ids_activas, str(sorted(ids_activas))[:200])

    r_alerts_todos = client.get("/api/alerts", params={"view": "todos", "page_size": 50})
    ids_todos = {a["id"] for a in r_alerts_todos.json().get("alerts", [])}
    check("G: con view=todos, la alerta CERRADA sigue apareciendo (no se borró nada)", alert_g1_id in ids_todos, str(sorted(ids_todos))[:200])

    r_alerts_status_closed = client.get("/api/alerts", params={"status": "CLOSED", "page_size": 50})
    ids_status_closed = {a["id"] for a in r_alerts_status_closed.json().get("alerts", [])}
    check("G: elegir el estado 'CLOSED' explícito manda sobre la vista por defecto", alert_g1_id in ids_status_closed, str(sorted(ids_status_closed))[:200])

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
print(f"{passed}/{total} pruebas OK (test_aislamiento_pertenece_al_endpoint.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
    print("\n--- últimas líneas del log de uvicorn ---")
    for line in server_log_lines[-60:]:
        print(line, end="")
sys.exit(0 if passed == total else 1)
