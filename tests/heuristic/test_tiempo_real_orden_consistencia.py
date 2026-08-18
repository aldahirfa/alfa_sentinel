"""Pruebas de "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO REAL, ORDENAMIENTO Y
CONSISTENCIA DE ALERTAS, INCIDENTES Y AISLAMIENTO" (2026-08-17, ver
PENDIENTES.md), secciones 27-30.

Lo que YA prueba tests/heuristic/test_aislamiento_manual_liberacion.py
(ciclo completo REQUESTED/EXECUTED/RELEASE_REQUESTED/RELEASED, guard de
duplicado a nivel de fila) y tests/heuristic/test_alertas_flotantes_open.py
(campos nuevos de /alerts/open, escalada de severidad sobre la misma
alerta) NO se repite acá -- este archivo cubre específicamente lo que esos
dos no verifican:

  L-xx (sección 27, latencia end-to-end): tiempo real desde
        POST /agent/alerts hasta que la alerta es visible en
        /alerts/open y en /api/alerts -- mide dónde está la demora en
        vez de asumir que es el frontend.

  O-xx (secciones 5/6/23/24/28, orden): /api/alerts y /api/incidentes
        devuelven "más reciente primero" (created_at/opened_at DESC) sin
        importar el orden de inserción/ID, incluida la paginación
        (sección 6: "si hay paginación, el orden debe ser consistente
        entre páginas").

  CASE A-E (sección 29, un mismo incidente/aislamiento de punta a
        punta): el mismo valor de isolation_status/is_isolated se ve
        IGUAL en /api/incidentes, en el drawer del incidente
        (/api/incidentes/incident/{id}/drawer), en el drawer del
        endpoint (/api/endpoints/{agent_id}/drawer) y en /alerts/open,
        en cada paso: sin aislamiento -> REQUESTED -> EXECUTED ->
        incidente resuelto (sigue visible, sigue aislado) ->
        RELEASE_REQUESTED -> RELEASED. Section 30 (duplicación) se
        verifica de nuevo acá sobre este mismo incidente, en el punto
        exacto donde section 29 lo pide (pulsar "Aislar" dos veces
        sobre el Case A).

Ejecutar: python3 tests/heuristic/test_tiempo_real_orden_consistencia.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time as time_mod
from datetime import datetime

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

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_tiemporeal_pgdata_")
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
       VALUES ('tester', %s, 'Tester Tiempo Real', 'tester.tr@example.com') ON CONFLICT DO NOTHING;""",
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


agent_lat, token_lat = make_agent("endpoint-L1-latencia")
agent_o1, token_o1 = make_agent("endpoint-O1-orden-alertas")
agent_o2, token_o2 = make_agent("endpoint-O2-orden-alertas")
agent_o3, token_o3 = make_agent("endpoint-O3-orden-alertas")
agent_case, token_case = make_agent("endpoint-CASE-aislamiento")

rule_id_by_name = {}
for row in conn.execute("SELECT id, name FROM heuristic_rules;").fetchall():
    rule_id_by_name[row[1]] = row[0]

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8081"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8081"

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
            json={"title": "Prueba tiempo real", "description": "Suite L/O/CASE", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def override_weight(agent_id, rule_name, weight):
        rid = rule_id_by_name[rule_name]
        resp = client.patch(f"/api/agents/{agent_id}/rules/{rid}", json={"weight": weight})
        assert resp.status_code == 200, resp.text

    def open_alerts():
        resp = client.get("/alerts/open")
        assert resp.status_code == 200, resp.text
        return resp.json()["alerts"]

    def find(items, item_id, key="id"):
        return next((x for x in items if x[key] == item_id), None)

    # ============================================================
    # L-xx: LATENCIA END-TO-END (sección 27) -- agente reporta ->
    # servidor procesa -> alerta visible en /alerts/open y /api/alerts.
    # No se asume que la demora está en React: acá se mide el tramo
    # servidor (que es el único medible sin un navegador real), tal
    # como ya se hizo en la medición previa de la sección 43 -- este
    # test deja la medición como algo repetible y con aserciones, no
    # solo un script suelto de una vez.
    # ============================================================
    t0 = time_mod.monotonic()
    r_lat = report(token_lat, ["Consumo CPU Elevado"])
    check("L-01: report_alert 200", r_lat.status_code == 200, r_lat.text[:300])
    alert_lat_id = r_lat.json()["alert_id"]
    t_report = time_mod.monotonic() - t0

    t1 = time_mod.monotonic()
    alerts = open_alerts()
    t_open = time_mod.monotonic() - t1
    row_lat = find(alerts, alert_lat_id)
    check("L-02: la alerta aparece en /alerts/open inmediatamente después de reportada", row_lat is not None, str(alerts))
    check(f"L-03: /alerts/open respondió en <1s ({t_open*1000:.0f} ms) -- no hay caché/staleness artificial", t_open < 1.0)

    t2 = time_mod.monotonic()
    api_alerts_resp = client.get("/api/alerts", params={"page_size": 50})
    t_api_alerts = time_mod.monotonic() - t2
    check("L-04: GET /api/alerts 200", api_alerts_resp.status_code == 200)
    row_lat2 = find(api_alerts_resp.json()["alerts"], alert_lat_id)
    check("L-05: la misma alerta aparece en /api/alerts inmediatamente (sin F5/espera)", row_lat2 is not None)
    check(f"L-06: /api/alerts respondió en <1s ({t_api_alerts*1000:.0f} ms)", t_api_alerts < 1.0)

    print(f"    [latencia] POST /agent/alerts={t_report*1000:.0f}ms  GET /alerts/open={t_open*1000:.0f}ms  GET /api/alerts={t_api_alerts*1000:.0f}ms")

    # ============================================================
    # O-xx: ORDEN (secciones 5/6/23/24/28) -- "más reciente arriba",
    # created_at real, no ID/orden de inserción. Se insertan 3 alertas
    # en un orden y se les fuerza created_at a 10:00/10:05/10:10 en un
    # orden DISTINTO al de inserción (igual que pide la sección 28:
    # "insertar alertas a las 10:00/10:05/10:10... la tabla debe
    # mostrar 10:10/10:05/10:00") -- si el backend ordenara por ID en
    # vez de por fecha, este test lo detectaría.
    # ============================================================
    r_a = report(token_o1, ["Consumo CPU Elevado"])
    r_b = report(token_o2, ["Consumo CPU Elevado"])
    r_c = report(token_o3, ["Consumo CPU Elevado"])
    check("O-00: las 3 alertas de la prueba de orden se crearon", all(r.status_code == 200 for r in (r_a, r_b, r_c)))
    id_a, id_b, id_c = r_a.json()["alert_id"], r_b.json()["alert_id"], r_c.json()["alert_id"]

    # Orden de inserción real: A, B, C (id_a < id_b < id_c). Orden de
    # fecha deseado (a propósito NO coincide con el de inserción):
    # B=10:00 (la más vieja), A=10:05, C=10:10 (la más nueva).
    c = db_conn()
    c.execute("UPDATE alerts SET created_at = %s WHERE id = %s;", (datetime(2026, 8, 17, 10, 5, 0), id_a))
    c.execute("UPDATE alerts SET created_at = %s WHERE id = %s;", (datetime(2026, 8, 17, 10, 0, 0), id_b))
    c.execute("UPDATE alerts SET created_at = %s WHERE id = %s;", (datetime(2026, 8, 17, 10, 10, 0), id_c))
    c.commit()
    c.close()

    resp_order = client.get("/api/alerts", params={"page_size": 50})
    check("O-01: GET /api/alerts 200", resp_order.status_code == 200)
    order_ids = [a["id"] for a in resp_order.json()["alerts"] if a["id"] in (id_a, id_b, id_c)]
    check(
        "O-02: /api/alerts devuelve estas 3 alertas más-reciente-primero (C=10:10, A=10:05, B=10:00), NO por ID/inserción",
        order_ids == [id_c, id_a, id_b], f"order_ids={order_ids}"
    )

    # Paginación (sección 6: "el orden debe ser consistente entre
    # páginas") -- se recorre TODO /api/alerts con page_size=1 (una
    # alerta por página, para forzar que C/A/B queden en páginas
    # distintas sin importar cuántas otras alertas haya creado el resto
    # de la suite) y se verifica que, dentro de esa secuencia completa,
    # C aparece antes que A y A aparece antes que B -- el orden debe
    # sostenerse ENTRE páginas, no solo dentro de una.
    seen_order = []
    page_n = 1
    while True:
        resp_page = client.get("/api/alerts", params={"page_size": 1, "page": page_n})
        body_page = resp_page.json()
        page_alerts = body_page["alerts"]
        if not page_alerts:
            break
        seen_order.extend(a["id"] for a in page_alerts if a["id"] in (id_a, id_b, id_c))
        if page_n >= body_page["total_pages"]:
            break
        page_n += 1
    check(
        "O-03: recorriendo /api/alerts página por página (page_size=1), C/A/B mantienen el orden más-reciente-primero",
        seen_order == [id_c, id_a, id_b], f"seen_order={seen_order}"
    )

    # Mismo criterio para /api/incidentes (ts = incidents.opened_at)
    # -- se insertan 3 incidentes directamente (no hace falta pasar
    # por report_alert(), el orden solo depende de 'opened_at') en
    # orden de inserción X,Y,Z pero con opened_at scrambled.
    c = db_conn()
    inc_x = c.execute(
        "INSERT INTO incidents (agent_id, title, status, opened_at) VALUES (%s, 'Orden X', 'OPEN', %s) RETURNING id;",
        (agent_o1, datetime(2026, 8, 17, 10, 5, 0)),
    ).fetchone()[0]
    inc_y = c.execute(
        "INSERT INTO incidents (agent_id, title, status, opened_at) VALUES (%s, 'Orden Y', 'OPEN', %s) RETURNING id;",
        (agent_o2, datetime(2026, 8, 17, 10, 0, 0)),
    ).fetchone()[0]
    inc_z = c.execute(
        "INSERT INTO incidents (agent_id, title, status, opened_at) VALUES (%s, 'Orden Z', 'OPEN', %s) RETURNING id;",
        (agent_o3, datetime(2026, 8, 17, 10, 10, 0)),
    ).fetchone()[0]
    c.commit()
    c.close()

    resp_inc_order = client.get("/api/incidentes", params={"page": 1})
    check("O-06: GET /api/incidentes 200", resp_inc_order.status_code == 200)
    inc_order_ids = [
        it["id"] for it in resp_inc_order.json()["items"]
        if it["kind"] == "incident" and it["id"] in (inc_x, inc_y, inc_z)
    ]
    check(
        "O-07: /api/incidentes devuelve estos 3 incidentes más-reciente-primero (Z=10:10, X=10:05, Y=10:00)",
        inc_order_ids == [inc_z, inc_x, inc_y], f"inc_order_ids={inc_order_ids}"
    )

    # ============================================================
    # CASE A-E (sección 29) -- un mismo incidente de punta a punta,
    # verificando en cada paso que /api/incidentes, el drawer del
    # incidente y el drawer del endpoint muestran EXACTAMENTE el mismo
    # isolation_status (sección 18: nunca "Aislado" en una pantalla y
    # otra cosa en otra).
    # ============================================================
    override_weight(agent_case, "Proceso Sospechoso", 60)
    r_case = report(token_case, ["Modificacion Masiva Archivos", "Proceso Sospechoso", "Consumo CPU Elevado"])
    check("CASE setup: report_alert 200", r_case.status_code == 200, r_case.text[:300])
    body_case = r_case.json()
    check("CASE setup: se creó un incidente", body_case["incident_id"] is not None, str(body_case))
    check("CASE setup: sin aislamiento automático (solo 1 regla fuerte)", body_case["isolation_requested"] is False, str(body_case))
    incident_case = body_case["incident_id"]
    alert_case_id = body_case["alert_id"]

    def incidentes_item(incident_id):
        # view=todos (2026-08-18, ver PENDIENTES.md, "Revisión y
        # corrección integral de ALFA-Sentinel", problema G): desde esa
        # corrección, GET /api/incidentes sin 'view' explícito devuelve
        # solo la vista OPERATIVA por defecto (excluye 'cerrado') -- este
        # helper lo usa también para CASE-C/D/E, que verifican
        # deliberadamente que un incidente YA CERRADO se siga viendo
        # (sección 29: "el incidente resuelto sigue apareciendo... con su
        # estado real"), así que necesita el historial completo, no la
        # vista operativa. No es un cambio de comportamiento del propio
        # CASE A-E, solo de qué vista pedirle a la API para poder seguir
        # observándolo tras cerrarlo.
        resp = client.get("/api/incidentes", params={"page": 1, "page_size": 50, "view": "todos"})
        return find(resp.json()["items"], incident_id)

    def incident_drawer(incident_id):
        resp = client.get(f"/api/incidentes/incident/{incident_id}/drawer")
        assert resp.status_code == 200, resp.text
        return resp.json()

    def endpoint_drawer(agent_id):
        resp = client.get(f"/api/endpoints/{agent_id}/drawer")
        assert resp.status_code == 200, resp.text
        return resp.json()

    def assert_consistent_isolation(label, expected_status, expected_is_isolated=None):
        item = incidentes_item(incident_case)
        drawer_i = incident_drawer(incident_case)
        drawer_e = endpoint_drawer(agent_case)
        alerts_open = open_alerts()
        row_open = find(alerts_open, alert_case_id)

        check(f"{label}: /api/incidentes.isolation_status == {expected_status}", item is not None and item["isolation_status"] == expected_status, str(item))
        check(f"{label}: drawer del incidente.isolation_status == {expected_status}", drawer_i["isolation_status"] == expected_status, str(drawer_i))
        check(f"{label}: drawer del endpoint.isolation_status == {expected_status}", drawer_e["isolation_status"] == expected_status, str(drawer_e))
        if row_open is not None:
            check(f"{label}: /alerts/open.isolation_status == {expected_status} (misma alerta de origen)", row_open["isolation_status"] == expected_status, str(row_open))
        if expected_is_isolated is not None:
            check(f"{label}: drawer del endpoint.is_isolated == {expected_is_isolated}", drawer_e["is_isolated"] == expected_is_isolated, str(drawer_e))
        return item, drawer_i, drawer_e

    # ---- Case A: incidente SIN aislamiento -> disponible el botón "Aislar" ----
    assert_consistent_isolation("CASE-A (sin aislamiento)", None, expected_is_isolated=False)

    r_iso = client.post(f"/incidents/{incident_case}/isolate")
    check("CASE-A: POST /incidents/{id}/isolate 200", r_iso.status_code == 200, r_iso.text[:300])
    isolation_case = r_iso.json()["isolation_id"]

    # Sección 30 (duplicación) aplicada exactamente sobre este Case A:
    # pulsar "Aislar" dos veces no debe crear una segunda fila.
    r_iso_dup = client.post(f"/incidents/{incident_case}/isolate")
    check("CASE-A dup: segunda orden sobre el mismo incidente -> 409 (no duplica)", r_iso_dup.status_code == 409, f"status={r_iso_dup.status_code}")
    c = db_conn()
    dup_count = c.execute("SELECT COUNT(*) FROM host_isolations WHERE incident_id = %s;", (incident_case,)).fetchone()[0]
    c.close()
    check("CASE-A dup: sigue habiendo UNA sola fila de host_isolations para este incidente", dup_count == 1, f"count={dup_count}")

    assert_consistent_isolation("CASE-A (REQUESTED)", "REQUESTED")

    # ---- Case B: agente confirma -> endpoint aislado -> "Liberar" disponible ----
    confirm = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_case, "status": "EXECUTED", "result": "[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO (CASE-B)."},
        headers={"X-Agent-Credential": token_case},
        timeout=10,
    )
    check("CASE-B: POST /agent/isolation-status/report(EXECUTED) 200", confirm.status_code == 200, confirm.text[:300])
    _, _, drawer_e_b = assert_consistent_isolation("CASE-B (EXECUTED)", "EXECUTED", expected_is_isolated=True)
    check("CASE-B: drawer del endpoint expone isolation_id para el botón Liberar", drawer_e_b.get("isolation_id") == isolation_case, str(drawer_e_b))

    # ---- Case C: resolver el incidente -> sigue visible en el historial, con estado Cerrado ----
    c = db_conn()
    count_before_close = c.execute("SELECT COUNT(*) FROM incidents WHERE id = %s;", (incident_case,)).fetchone()[0]
    c.close()

    r_close = client.patch(f"/incidents/{incident_case}/status", json={"status": "CLOSED"})
    check("CASE-C: PATCH /incidents/{id}/status(CLOSED) 200", r_close.status_code == 200, r_close.text[:300])

    c = db_conn()
    count_after_close = c.execute("SELECT COUNT(*) FROM incidents WHERE id = %s;", (incident_case,)).fetchone()[0]
    c.close()
    check("CASE-C: el incidente NO se borró de la base de datos al resolverse", count_before_close == 1 and count_after_close == 1)

    item_closed = incidentes_item(incident_case)
    check("CASE-C: el incidente resuelto sigue apareciendo en /api/incidentes (historial)", item_closed is not None, str(item_closed))
    check("CASE-C: status_bucket == 'cerrado' (estado real, no desaparece)", item_closed is not None and item_closed["status_bucket"] == "cerrado", str(item_closed))
    check("CASE-C: raw_status == 'CLOSED'", item_closed is not None and item_closed["raw_status"] == "CLOSED", str(item_closed))

    # ---- Case D: el endpoint SIGUE aislado después de resolver el incidente ----
    # (resolver el incidente y liberar el endpoint son operaciones
    # distintas -- sección 17: no se asume "incidente resuelto =>
    # endpoint liberado automáticamente").
    assert_consistent_isolation("CASE-D (incidente cerrado, endpoint sigue aislado)", "EXECUTED", expected_is_isolated=True)

    # ---- Case E: liberar el endpoint -> RELEASE_REQUESTED -> RELEASED ----
    r_release = client.post(f"/host-isolations/{isolation_case}/release")
    check("CASE-E: POST /host-isolations/{id}/release 200", r_release.status_code == 200, r_release.text[:300])
    assert_consistent_isolation("CASE-E (RELEASE_REQUESTED)", "RELEASE_REQUESTED", expected_is_isolated=True)

    # Duplicación también sobre Liberar (sección 30): pulsarlo dos
    # veces mientras está RELEASE_REQUESTED no debe generar una nueva
    # fila ni aceptarse.
    r_release_dup = client.post(f"/host-isolations/{isolation_case}/release")
    check("CASE-E dup: liberar de nuevo mientras RELEASE_REQUESTED -> 409 (no duplica)", r_release_dup.status_code == 409, f"status={r_release_dup.status_code}")

    confirm_release = httpx.post(
        f"{BASE}/agent/isolation-status/report",
        json={"isolation_id": isolation_case, "status": "RELEASED", "result": "[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO (CASE-E)."},
        headers={"X-Agent-Credential": token_case},
        timeout=10,
    )
    check("CASE-E: POST /agent/isolation-status/report(RELEASED) 200", confirm_release.status_code == 200, confirm_release.text[:300])
    assert_consistent_isolation("CASE-E (RELEASED, endpoint normalizado)", "RELEASED", expected_is_isolated=False)

    c = db_conn()
    count_final = c.execute("SELECT COUNT(*) FROM host_isolations WHERE incident_id = %s;", (incident_case,)).fetchone()[0]
    c.close()
    check("CASE-E: sigue habiendo UNA sola fila de host_isolations para todo el ciclo A-E (nunca se duplicó)", count_final == 1, f"count={count_final}")

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
