"""Series A (episodios/alertas), I (incidentes) y parte de la serie
ISO (aislamiento) de la especificación "ALFA_SENTINEL — CORRECCIÓN
DEFINITIVA DEL MOTOR HEURÍSTICO..." (2026-08-17, ver PENDIENTES.md).

Llama directo a POST /agent/alerts (report_alert real, sin mocks) con
matched_rules armados a mano -- no hace falta un watchdog.Observer real
para probar la lógica de episodios/score/incidente/aislamiento, que
vive enteramente en el servidor. H1-H8/G1-G6/la prueba crítica
combinada (tests/honeyfiles/) ya cubren el camino end-to-end con
eventos de archivo reales; esta serie aísla específicamente la lógica
de report_alert() con datos de entrada controlados, incluyendo casos
límite (I-02/I-03/I-04) que son difíciles o imposibles de alcanzar solo
con actividad de archivos real dados los pesos actuales -- se
construyen con el override por endpoint (agent_rule, mecanismo ya
existente, no inventado para esta prueba, sección 32: "no alterar estas
excepciones sin evidencia de que la implementación actual no coincide").

ISO-02/03/04 (aislamiento ejecutado de punta a punta, Condición A) ya
están cubiertos por tests/honeyfiles/test_critico_combinado.py; acá se
agrega el caso de Condición B (CRÍTICO + 2 reglas fuertes, sin
honeyfile) más ISO-01 (no corresponde) e ISO-05 (fallo real).

Ejecutar: python3 tests/heuristic/test_episodios_incidentes_aislamiento.py
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
sys.path.insert(0, os.path.join(REPO, "agent"))

import paths as agent_paths  # noqa: E402
from isolation_executor import execute_isolation  # noqa: E402

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_aie_pgdata_")
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


agent_a, token_a = make_agent("endpoint-A-episodios")       # serie A
agent_i2, token_i2 = make_agent("endpoint-I2-sin-incidente")  # I-01/I-02
agent_i3, token_i3 = make_agent("endpoint-I3-tres-reglas")    # I-03
agent_i4, token_i4 = make_agent("endpoint-I4-dos-fuertes")    # I-04 + ISO-03
agent_i5, token_i5 = make_agent("endpoint-I5-honeyfile")      # I-05
agent_iso1, token_iso1 = make_agent("endpoint-ISO1-no-aisla")  # ISO-01

rule_id_by_name = {}
for row in conn.execute("SELECT id, name FROM heuristic_rules;").fetchall():
    rule_id_by_name[row[1]] = row[0]

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8078"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8078"

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
            json={"title": "Prueba", "description": "Prueba serie A/I/ISO", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def alerts_for(agent_id):
        c = db_conn()
        rows = c.execute("SELECT id, risk_score, incident_id FROM alerts WHERE agent_id = %s ORDER BY id ASC;", (agent_id,)).fetchall()
        c.close()
        return rows

    def linked_rule_names(alert_id):
        """Nunca cuenta 'Correlacion Multiples Indicadores' -- esa fila
        es la bonificación HR-12, no una regla que coincidió de
        verdad sobre un evento (mismo criterio que usa report_alert()
        para 'already_linked')."""
        c = db_conn()
        rows = c.execute(
            """SELECT heuristic_rules.name FROM alert_rule
               JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
               WHERE alert_rule.alert_id = %s AND heuristic_rules.name != 'Correlacion Multiples Indicadores';""",
            (alert_id,),
        ).fetchall()
        c.close()
        return {row[0] for row in rows}

    def override_weight(agent_id, rule_name, weight):
        rid = rule_id_by_name[rule_name]
        resp = client.patch(f"/api/agents/{agent_id}/rules/{rid}", json={"weight": weight})
        assert resp.status_code == 200, resp.text

    def age_episode_evidence(agent_id, seconds_ago):
        """Simula que pasó 'seconds_ago' desde la última evidencia real
        de la alerta abierta de este agente -- sin esto habría que
        esperar EPISODE_WINDOW_SECONDS (120s) de verdad para probar
        A-04. Se manipula el timestamp real en la base (no la lógica de
        report_alert, que sigue siendo la real) -- técnica honesta: se
        ejerce la MISMA consulta SQL de producción contra un dato de
        tiempo fabricado, igual que test_h_honeyfiles.py manipula
        directamente el status de una alerta para forzar un episodio
        nuevo (close_current_episode)."""
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

    # ================= SERIE A: episodios/alertas =================

    # A-01: un evento que activa una regla -> una alerta.
    r1 = report(token_a, ["Modificacion Masiva Archivos"])
    check("A-01: report_alert 200", r1.status_code == 200, r1.text[:200])
    rows_a = alerts_for(agent_a)
    check("A-01: se creó exactamente UNA alerta", len(rows_a) == 1, str(rows_a))
    alert_a_id = rows_a[0][0] if rows_a else None

    # A-02: la MISMA regla vuelve a coincidir dentro del mismo episodio -> misma alerta, sin duplicar evidencia.
    r2 = report(token_a, ["Modificacion Masiva Archivos"])
    check("A-02: report_alert 200", r2.status_code == 200)
    rows_a = alerts_for(agent_a)
    check("A-02: sigue habiendo UNA sola alerta (mismo episodio)", len(rows_a) == 1, str(rows_a))
    c = db_conn()
    dup_count = c.execute(
        "SELECT COUNT(*) FROM alert_rule WHERE alert_id = %s AND rule_id = %s;",
        (alert_a_id, rule_id_by_name["Modificacion Masiva Archivos"]),
    ).fetchone()[0]
    c.close()
    check("A-02: la regla sigue apareciendo UNA sola vez en alert_rule (no duplicada)", dup_count == 1, f"count={dup_count}")

    # A-03: OTRA regla coincide dentro del episodio -> misma alerta + nueva evidencia.
    r3 = report(token_a, ["Escritura Intensiva Archivos"])
    check("A-03: report_alert 200", r3.status_code == 200)
    rows_a = alerts_for(agent_a)
    check("A-03: sigue siendo la MISMA alerta (mismo episodio)", len(rows_a) == 1 and rows_a[0][0] == alert_a_id, str(rows_a))
    names_a = linked_rule_names(alert_a_id)
    check("A-03: ahora hay 2 reglas distintas vinculadas (evidencia nueva sumada)", names_a == {"Modificacion Masiva Archivos", "Escritura Intensiva Archivos"}, str(names_a))

    # A-04: el episodio queda sin evidencia nueva por más de EPISODE_WINDOW_SECONDS reales -> la próxima coincidencia abre una alerta NUEVA (ventana deslizante, sección 16).
    age_episode_evidence(agent_a, 130)
    r4 = report(token_a, ["Modificacion Masiva Archivos"])
    check("A-04: report_alert 200", r4.status_code == 200)
    rows_a = alerts_for(agent_a)
    check("A-04: episodio cerrado por inactividad real -> alerta NUEVA distinta de la anterior", len(rows_a) == 2 and rows_a[1][0] != alert_a_id, str(rows_a))

    # ================= SERIE I: incidentes =================

    # I-01: score bajo (una sola regla débil) -> sin incidente.
    r_i1 = report(token_i2, ["Consumo CPU Elevado"])
    check("I-01: report_alert 200", r_i1.status_code == 200)
    body_i1 = r_i1.json()
    check("I-01: score < 75", body_i1["risk_score"] < 75, str(body_i1))
    check("I-01: NO se crea incidente", body_i1["incident_id"] is None, str(body_i1))

    # I-02 (actualizado 2026-08-18, ver PENDIENTES.md): score >= 75
    # (CRÍTICO) SIN evidencia fuerte adicional (2 reglas no-fuertes) --
    # antes esto NO alcanzaba a crear incidente. Ahora CRÍTICO por sí
    # solo YA es evidencia suficiente (se pidió que toda alerta CRÍTICA
    # abra incidente y aísle automáticamente, sin depender de qué
    # reglas puntuales la componen) -> SÍ se crea incidente y SÍ se
    # solicita aislamiento. Con los pesos reales no alcanza 75 sin
    # honeyfile/3 reglas/2 fuertes -- se ajusta el peso de 2 reglas NO
    # fuertes con el override por endpoint (mecanismo ya existente)
    # para construir el caso límite exacto que pide la especificación.
    override_weight(agent_i2, "Actividad Repetitiva Automatizada", 70.0)  # HR-11, no está en STRONG_RULE_NAMES
    r_i2 = report(token_i2, ["Actividad Repetitiva Automatizada", "Consumo CPU Elevado"])
    check("I-02: report_alert 200", r_i2.status_code == 200, r_i2.text[:200])
    body_i2 = r_i2.json()
    check("I-02: score >= 75", body_i2["risk_score"] >= 75, str(body_i2))
    check("I-02: CRÍTICO por sí solo -- SÍ se crea incidente (sin exigir evidencia extra)", body_i2["incident_id"] is not None, str(body_i2))
    check("I-02: CRÍTICO por sí solo -- SÍ se solicita aislamiento automático", body_i2["isolation_requested"] is True, str(body_i2))

    # I-03: score >= 75 con >= 3 reglas distintas (solo 1 fuerte) -> incidente por Condición B.
    override_weight(agent_i3, "Proceso Sospechoso", 30.0)       # HR-05, no fuerte
    override_weight(agent_i3, "Actividad Repetitiva Automatizada", 20.0)  # HR-11, no fuerte
    r_i3 = report(token_i3, ["Modificacion Masiva Archivos", "Proceso Sospechoso", "Actividad Repetitiva Automatizada"])
    check("I-03: report_alert 200", r_i3.status_code == 200, r_i3.text[:200])
    body_i3 = r_i3.json()
    check("I-03: score >= 75", body_i3["risk_score"] >= 75, str(body_i3))
    check("I-03: 3 reglas distintas (1 sola fuerte) -> SÍ se crea incidente", body_i3["incident_id"] is not None, str(body_i3))

    # I-04: score >= 75 con exactamente 2 reglas, AMBAS fuertes (< 3
    # reglas en total, para aislar de la Condición B de arriba) ->
    # incidente por Condición C. Este mismo escenario también satisface
    # la Condición B de AISLAMIENTO (CRÍTICO + 2 reglas fuertes de
    # archivos, sin honeyfile) -- ISO-03 de la especificación.
    override_weight(agent_i4, "Modificacion Masiva Archivos", 60.0)
    r_i4 = report(token_i4, ["Modificacion Masiva Archivos", "Escritura Intensiva Archivos"])
    check("I-04: report_alert 200", r_i4.status_code == 200, r_i4.text[:200])
    body_i4 = r_i4.json()
    check("I-04: score >= 75", body_i4["risk_score"] >= 75, str(body_i4))
    check("I-04: 2 reglas fuertes (< 3 en total) -> SÍ se crea incidente (Condición C)", body_i4["incident_id"] is not None, str(body_i4))
    check(
        "ISO-03: CRÍTICO (sin honeyfile) -> aislamiento SOLICITADO (severidad por sí sola)",
        body_i4.get("isolation_requested") is True, str(body_i4),
    )
    c = db_conn()
    iso_row_i4 = c.execute("SELECT status, reason FROM host_isolations WHERE incident_id = %s;", (body_i4["incident_id"],)).fetchone()
    c.close()
    check("ISO-03 (BD): host_isolations tiene una fila REQUESTED con la severidad CRÍTICA en el motivo", iso_row_i4 is not None and iso_row_i4[0] == "REQUESTED" and "CRÍTICA" in (iso_row_i4[1] or ""), str(iso_row_i4))

    # I-05: honeyfile activado -> siempre incidente (Condición A), sin importar cuántas otras reglas participaron.
    r_i5 = report(token_i5, ["Acceso Honeyfile"])
    check("I-05: report_alert 200", r_i5.status_code == 200)
    body_i5 = r_i5.json()
    check("I-05: risk_score = 100", body_i5["risk_score"] == 100, str(body_i5))
    check("I-05: honeyfile -> SÍ se crea incidente (Condición A)", body_i5["incident_id"] is not None, str(body_i5))

    # ================= SERIE ISO: aislamiento =================
    # (ISO-02/03/04 -- Condición A end-to-end con ejecución real
    # simulada -- ya cubiertos por tests/honeyfiles/test_critico_combinado.py;
    # ISO-03/Condición B ya se verificó arriba junto con I-04.)

    # ISO-01 (actualizado 2026-08-18, ver PENDIENTES.md): I-03 es un
    # incidente real con score>=75 (CRÍTICO) y solo 1 regla fuerte --
    # antes esto NO alcanzaba a aislar (exigía Condición A/B con
    # evidencia extra). Se pidió explícitamente que TODA alerta
    # CRÍTICA aísle el endpoint automáticamente sin condiciones
    # adicionales -> ahora SÍ se registra la orden de aislamiento.
    check(
        "ISO-01: incidente CRÍTICO (aunque sea con 1 sola regla fuerte) -> SÍ se solicita aislamiento",
        body_i3.get("isolation_requested") is True, str(body_i3),
    )
    c = db_conn()
    iso_row_i3 = c.execute("SELECT id, status FROM host_isolations WHERE incident_id = %s;", (body_i3["incident_id"],)).fetchone()
    c.close()
    check("ISO-01 (BD): host_isolations SÍ tiene una fila REQUESTED para ese incidente", iso_row_i3 is not None and iso_row_i3[1] == "REQUESTED", str(iso_row_i3))

    # ISO-05: fallo REAL de ejecución -- se fuerza ALFA_SENTINEL_ENV=production
    # (agent_paths.get_env_mode(), sin monkeypatchear ningún resultado)
    # en este sandbox, que no tiene privilegios de root/Administrador
    # reales -- execute_isolation() tiene que fallar HONESTAMENTE (nunca
    # fingir éxito), igual que fanotify_init() devuelve EPERM en vez de
    # simular que funciona (mismo criterio ya establecido en el
    # proyecto, ver PENDIENTES.md, "Atribución de procesos...").
    original_env = os.environ.get("ALFA_SENTINEL_ENV")
    os.environ["ALFA_SENTINEL_ENV"] = "production"
    try:
        success, detail = execute_isolation("NETWORK")
    finally:
        if original_env is None:
            os.environ.pop("ALFA_SENTINEL_ENV", None)
        else:
            os.environ["ALFA_SENTINEL_ENV"] = original_env
    check("ISO-05: execute_isolation() en production sin privilegios reales -> falla honesto (success=False)", success is False, detail)
    check("ISO-05: el detalle del fallo es real, no genérico (menciona privilegios)", "rivilegi" in detail, detail)

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
print(f"{passed}/{total} pruebas OK (test_episodios_incidentes_aislamiento.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
    print("\n--- últimas líneas del log de uvicorn ---")
    for line in server_log_lines[-60:]:
        print(line, end="")
sys.exit(0 if passed == total else 1)
