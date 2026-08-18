"""Pruebas de "Corrección definitiva en la lógica y presentación de
ALERTAS" (2026-08-18, ver PENDIENTES.md) -- las 10 pruebas obligatorias
que pidió el usuario, más los casos concretos que originaron el pedido
(alerta titulada "Consumo de CPU elevado" cuando en realidad incluía
"Acceso Honeyfile" en el mismo episodio).

  T-01: solo CPU -> título corresponde al nivel de riesgo alcanzado
        (BAJO con el peso real de HR-06), nunca "Consumo de CPU elevado".
  T-02: solo Honeyfile -> CRÍTICO de inmediato (weight=100 fijo),
        título "ATAQUE DE RANSOMWARE PROBABLE", nunca "Acceso Honeyfile".
  T-03: CPU + Honeyfile en el mismo episodio -> UNA sola alerta, título
        general por la severidad final, AMBAS reglas visibles en el
        detalle (el caso exacto que reportó el usuario).
  T-04: CPU + actividad masiva + Honeyfile -> una sola alerta, score
        acumulado, las 3 reglas visibles, título "ATAQUE DE RANSOMWARE
        PROBABLE" si crítico.
  T-05: el orden de llegada de las reglas no determina el título NI el
        orden en que se listan en el detalle (se prueba con dos
        episodios equivalentes, reglas en orden inverso).
  T-06: el proceso solo se muestra cuando existe realmente (nunca se
        inventa un PID/nombre de proceso).
  T-07: latencia -- la alerta aparece de inmediato en /alerts/open y
        /api/alerts con el título ya calculado (sin esperar un paso
        aparte).
  T-08: la campana (conteo de /alerts/open) no duplica al acumular más
        evidencia sobre el mismo episodio -- sigue siendo 1 alerta.
  T-09: ventana flotante -- cubierta por
        tests/heuristic/test_alertas_flotantes_open.py (dedupe por
        alert_id) y por inspección de código de
        frontend/src/context/GlobalAlertsContext.tsx (sin cambios en
        esta tarea); acá se verifica la precondición de la que depende
        ese dedupe: /alerts/open sigue devolviendo una fila por alerta
        real, nunca una fila por regla vinculada.
  T-10: la relación alerts -> alert_rule -> heuristic_rules sigue
        intacta (no se tocó el schema ni el INSERT de alert_rule).

Ejecutar: python3 tests/heuristic/test_titulo_general_severidad.py
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

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_titulo_pgdata_")
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
       VALUES ('tester', %s, 'Tester Titulo', 'tester.titulo@example.com') ON CONFLICT DO NOTHING;""",
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


agent_t1, token_t1 = make_agent("endpoint-T1-solo-cpu")
agent_t2, token_t2 = make_agent("endpoint-T2-solo-honeyfile")
agent_t3, token_t3 = make_agent("endpoint-T3-cpu-honeyfile")
agent_t4, token_t4 = make_agent("endpoint-T4-combo")
agent_t5a, token_t5a = make_agent("endpoint-T5a-orden-cpu-primero")
agent_t5b, token_t5b = make_agent("endpoint-T5b-orden-honeyfile-primero")
agent_t6a, token_t6a = make_agent("endpoint-T6a-proceso-real")
agent_t6b, token_t6b = make_agent("endpoint-T6b-proceso-ausente")
agent_t7, token_t7 = make_agent("endpoint-T7-latencia")
agent_t8, token_t8 = make_agent("endpoint-T8-campana")
agent_t10, token_t10 = make_agent("endpoint-T10-relacion-fk")

conn.close()

env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8082"],
    cwd=os.path.join(REPO, "server"), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

BASE = "http://127.0.0.1:8082"

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

    def report(token, matched_rules, title="Prueba título general"):
        return httpx.post(
            f"{BASE}/agent/alerts",
            json={"title": title, "description": "Suite T-01..T-10", "matched_rules": matched_rules},
            headers={"X-Agent-Credential": token},
            timeout=10,
        )

    def open_alerts():
        resp = client.get("/alerts/open")
        assert resp.status_code == 200, resp.text
        return resp.json()

    def find(items, item_id, key="id"):
        return next((x for x in items if x[key] == item_id), None)

    def alert_drawer(alert_id):
        resp = client.get(f"/api/incidentes/alert/{alert_id}/drawer")
        assert resp.status_code == 200, resp.text
        return resp.json()

    ALERT_TITLE_BY_SEVERITY = {
        "BAJO": "ACTIVIDAD ANÓMALA",
        "MEDIO": "ACTIVIDAD SOSPECHOSA",
        "ALTO": "POSIBLE ATAQUE DE RANSOMWARE",
        "CRÍTICO": "ATAQUE DE RANSOMWARE PROBABLE",
    }
    BANNED_RULE_TITLES = {
        "Consumo de CPU elevado", "Acceso a Honeyfile", "Acceso Honeyfile",
        "Borrado masivo", "Renombrado sospechoso", "Honeyfile activado",
    }

    # ================= T-01: solo CPU =================
    r1 = report(token_t1, ["Consumo CPU Elevado"])
    check("T-01: report_alert 200", r1.status_code == 200, r1.text[:300])
    body1 = r1.json()
    alert1 = find(open_alerts()["alerts"], body1["alert_id"])
    check("T-01: aparece en /alerts/open", alert1 is not None)
    if alert1:
        expected_title = ALERT_TITLE_BY_SEVERITY[alert1["severity"]]
        check(
            f"T-01: título == '{expected_title}' (según severidad {alert1['severity']}), nunca el nombre de la regla",
            alert1["title"] == expected_title, str(alert1)
        )
        check("T-01: el título NO es el nombre de una regla individual", alert1["title"] not in BANNED_RULE_TITLES, str(alert1))

    api_alerts1 = client.get("/api/alerts", params={"page_size": 50}).json()["alerts"]
    row1 = find(api_alerts1, body1["alert_id"])
    check("T-01: mismo título general en /api/alerts (tabla de Alertas)", row1 is not None and row1["title"] == ALERT_TITLE_BY_SEVERITY[row1["severity"]], str(row1))
    check("T-01: rule_count == 1 (una sola señal, sin nombrarla en el título)", row1 is not None and row1["rule_count"] == 1, str(row1))

    # ================= T-02: solo Honeyfile =================
    r2 = report(token_t2, ["Acceso Honeyfile"])
    check("T-02: report_alert 200", r2.status_code == 200, r2.text[:300])
    body2 = r2.json()
    check("T-02: severidad CRÍTICO de inmediato (weight fijo 100)", body2["risk_score"] >= 75, str(body2))
    drawer2 = alert_drawer(body2["alert_id"])
    check("T-02: título == 'ATAQUE DE RANSOMWARE PROBABLE'", drawer2["title"] == "ATAQUE DE RANSOMWARE PROBABLE", str(drawer2))
    check("T-02: el título NO es 'Acceso Honeyfile'/'Honeyfile activado'", drawer2["title"] not in BANNED_RULE_TITLES, str(drawer2))
    check("T-02: la regla real sigue visible en el detalle", any(x["rule_name"] == "Acceso Honeyfile" for x in drawer2["rules"]), str(drawer2))

    # ================= T-03: CPU + Honeyfile, mismo episodio =================
    # Este es el caso EXACTO que reportó el usuario: "aparece 'Consumo
    # de CPU elevado -- python.exe' y 'Acceso Honeyfile' en la misma
    # fila -- ¿por qué dice CPU si es Honeyfile?".
    r3a = report(token_t3, ["Consumo CPU Elevado"])
    check("T-03a: report_alert 200 (CPU primero)", r3a.status_code == 200)
    alert_id_3 = r3a.json()["alert_id"]

    r3b = report(token_t3, ["Acceso Honeyfile"])
    check("T-03b: report_alert 200 (Honeyfile después, mismo episodio)", r3b.status_code == 200)
    check("T-03b: sigue siendo LA MISMA alerta (mismo episodio, no una nueva)", r3b.json()["alert_id"] == alert_id_3, str(r3b.json()))

    drawer3 = alert_drawer(alert_id_3)
    check("T-03: título == 'ATAQUE DE RANSOMWARE PROBABLE' (severidad final, no la primera regla)", drawer3["title"] == "ATAQUE DE RANSOMWARE PROBABLE", str(drawer3))
    rule_names_3 = {x["rule_name"] for x in drawer3["rules"]}
    check("T-03: 'Consumo CPU Elevado' sigue visible en el detalle", "Consumo CPU Elevado" in rule_names_3, str(drawer3))
    check("T-03: 'Acceso Honeyfile' sigue visible en el detalle", "Acceso Honeyfile" in rule_names_3, str(drawer3))
    check("T-03: 'Acceso Honeyfile' aparece PRIMERO en el detalle (señal más relevante, sección 7)", drawer3["rules"][0]["rule_name"] == "Acceso Honeyfile", str(drawer3))

    # rule_count == 3, no 2: además de las 2 señales reales
    # (Consumo CPU Elevado + Acceso Honeyfile), report_alert() suma acá
    # la bonificación real de HR-12 "Correlacion Multiples Indicadores"
    # (distinct_rule_count == 2 -> +5, ver server/main.py) como una
    # fila más de alert_rule -- es una contribución real al risk_score,
    # no se oculta (sección 3: "no ocultar reglas secundarias").
    api_alerts3 = client.get("/api/alerts", params={"page_size": 50}).json()["alerts"]
    row3 = find(api_alerts3, alert_id_3)
    check("T-03: en la tabla de Alertas, título general y rule_count == 3 (2 señales + bonificación de correlación, no un nombre de regla)", row3 is not None and row3["title"] == "ATAQUE DE RANSOMWARE PROBABLE" and row3["rule_count"] == 3, str(row3))

    # ================= T-04: CPU + actividad masiva + Honeyfile =================
    r4a = report(token_t4, ["Consumo CPU Elevado"])
    r4b = report(token_t4, ["Modificacion Masiva Archivos"])
    r4c = report(token_t4, ["Acceso Honeyfile"])
    check("T-04: las 3 reglas quedan en LA MISMA alerta (mismo episodio)", r4a.json()["alert_id"] == r4b.json()["alert_id"] == r4c.json()["alert_id"], f"{r4a.json()} / {r4b.json()} / {r4c.json()}")
    alert_id_4 = r4c.json()["alert_id"]
    check("T-04: risk_score acumulado >= 75 (CRÍTICO)", r4c.json()["risk_score"] >= 75, str(r4c.json()))

    drawer4 = alert_drawer(alert_id_4)
    check("T-04: título == 'ATAQUE DE RANSOMWARE PROBABLE'", drawer4["title"] == "ATAQUE DE RANSOMWARE PROBABLE", str(drawer4))
    rule_names_4 = {x["rule_name"] for x in drawer4["rules"]}
    check(
        "T-04: las 3 reglas visibles en el detalle (no se oculta ninguna)",
        {"Consumo CPU Elevado", "Modificacion Masiva Archivos", "Acceso Honeyfile"} <= rule_names_4,
        str(drawer4)
    )

    # ================= T-05: el orden de llegada NO determina el título ni el orden de reglas =================
    r5a1 = report(token_t5a, ["Consumo CPU Elevado"])
    r5a2 = report(token_t5a, ["Acceso Honeyfile"])
    alert_id_5a = r5a2.json()["alert_id"]

    r5b1 = report(token_t5b, ["Acceso Honeyfile"])
    r5b2 = report(token_t5b, ["Consumo CPU Elevado"])
    alert_id_5b = r5b2.json()["alert_id"]

    drawer5a = alert_drawer(alert_id_5a)
    drawer5b = alert_drawer(alert_id_5b)
    check("T-05: mismo título sin importar el orden de llegada (CPU->Honeyfile)", drawer5a["title"] == "ATAQUE DE RANSOMWARE PROBABLE", str(drawer5a))
    check("T-05: mismo título sin importar el orden de llegada (Honeyfile->CPU)", drawer5b["title"] == drawer5a["title"], f"a={drawer5a['title']} b={drawer5b['title']}")
    # Se excluye 'Correlacion Multiples Indicadores' de esta comparación
    # a propósito: su 'matched_at' se actualiza en CADA report_alert()
    # que sigue sumando evidencia al episodio (representa "la
    # contribución más reciente", no una detección puntual como las
    # demás), así que su posición exacta entre señales del mismo peso
    # puede variar por timing -- eso es un comportamiento propio de esa
    # regla sintética, no algo que esta sección deba garantizar. Lo que
    # sí debe sostenerse pase lo que pase es el orden relativo de las
    # señales REALES (sección 5 de la especificación: "el orden de
    # llegada de las reglas no debe determinar el título" -- por
    # extensión, tampoco el orden en que se listan).
    order_a = [x["rule_name"] for x in drawer5a["rules"] if x["rule_name"] != "Correlacion Multiples Indicadores"]
    order_b = [x["rule_name"] for x in drawer5b["rules"] if x["rule_name"] != "Correlacion Multiples Indicadores"]
    check(
        "T-05: mismo orden de señales REALES en el detalle sin importar en qué orden llegaron (Acceso Honeyfile siempre primero)",
        order_a == order_b == ["Acceso Honeyfile", "Consumo CPU Elevado"], f"order_a={order_a} order_b={order_b}"
    )

    # ================= T-06: proceso solo cuando existe realmente =================
    # T6a: hay una activación de honeyfile real con proceso atribuido
    # DENTRO de la ventana de correlación -- debe aparecer tal cual.
    r6a = report(token_t6a, ["Acceso Honeyfile"])
    alert_id_6a = r6a.json()["alert_id"]
    c = db_conn()
    hf = c.execute("SELECT id FROM honeyfiles LIMIT 1;").fetchone()
    if hf is None:
        hf = c.execute(
            "INSERT INTO honeyfiles (agent_id, file_name, file_path, file_hash) VALUES (%s, 'trampa.docx', '/tmp/trampa.docx', 'hash') RETURNING id;",
            (agent_t6a,),
        ).fetchone()
        c.commit()
    c.execute(
        """
        INSERT INTO honeyfile_activations (honeyfile_id, agent_id, operation, process_name, process_id, detected_at)
        VALUES (%s, %s, 'READ', 'ransom.exe', 4321, CURRENT_TIMESTAMP);
        """,
        (hf[0], agent_t6a)
    )
    c.commit()
    c.close()

    drawer6a = alert_drawer(alert_id_6a)
    check("T-06a: 'Proceso' viene con el nombre real correlacionado", drawer6a["process"]["process_name"] == "ransom.exe", str(drawer6a["process"]))
    check("T-06a: 'PID' viene con el valor real correlacionado", drawer6a["process"]["process_id"] == 4321, str(drawer6a["process"]))
    check("T-06a: 'Ruta' es honestamente 'None' (no existe esa columna en ninguna tabla real)", drawer6a["process"]["executable_path"] is None, str(drawer6a["process"]))
    check("T-06a: 'Usuario' es honestamente 'None' (no existe esa columna en ninguna tabla real)", drawer6a["process"]["username"] is None, str(drawer6a["process"]))

    # T6b: ninguna fuente real tiene proceso atribuido en la ventana --
    # todo el bloque debe quedar en None, nunca inventado.
    r6b = report(token_t6b, ["Modificacion Masiva Archivos", "Escritura Intensiva Archivos"])
    alert_id_6b = r6b.json()["alert_id"]
    drawer6b = alert_drawer(alert_id_6b)
    check("T-06b: sin proceso atribuido en la ventana -> 'process_name' None (no se inventa)", drawer6b["process"]["process_name"] is None, str(drawer6b["process"]))
    check("T-06b: sin proceso atribuido en la ventana -> 'process_id' None (no se inventa)", drawer6b["process"]["process_id"] is None, str(drawer6b["process"]))

    # ================= T-07: latencia -- título ya calculado de inmediato =================
    t0 = time_mod.monotonic()
    r7 = report(token_t7, ["Acceso Honeyfile"])
    elapsed_report = time_mod.monotonic() - t0
    check("T-07: report_alert 200", r7.status_code == 200)

    t1 = time_mod.monotonic()
    alerts7 = open_alerts()["alerts"]
    elapsed_open = time_mod.monotonic() - t1
    row7 = find(alerts7, r7.json()["alert_id"])
    check("T-07: la alerta aparece en /alerts/open de inmediato, YA con el título general calculado", row7 is not None and row7["title"] == "ATAQUE DE RANSOMWARE PROBABLE", str(row7))
    check(f"T-07: /alerts/open respondió en <1s ({elapsed_open*1000:.0f} ms)", elapsed_open < 1.0)
    print(f"    [T-07 latencia] POST /agent/alerts={elapsed_report*1000:.0f}ms  GET /alerts/open={elapsed_open*1000:.0f}ms")

    # ================= T-08: la campana no duplica al acumular evidencia =================
    count_before = open_alerts()["count"]
    r8a = report(token_t8, ["Consumo CPU Elevado"])
    count_after_first = open_alerts()["count"]
    check("T-08: primera evidencia del episodio suma 1 al conteo de /alerts/open", count_after_first == count_before + 1, f"before={count_before} after={count_after_first}")

    r8b = report(token_t8, ["Modificacion Masiva Archivos"])
    check("T-08: la segunda evidencia sigue siendo LA MISMA alerta", r8b.json()["alert_id"] == r8a.json()["alert_id"], str(r8b.json()))
    count_after_second = open_alerts()["count"]
    check("T-08: el conteo NO sube de nuevo -- no duplica la alerta al acumular evidencia", count_after_second == count_after_first, f"after_first={count_after_first} after_second={count_after_second}")

    # ================= T-09: precondición del dedupe de la ventana flotante =================
    # El dedupe real (Map por alert_id) vive en
    # frontend/src/context/GlobalAlertsContext.tsx y no se tocó en esta
    # tarea -- ver test_alertas_flotantes_open.py (F-04) para la prueba
    # de escalada de severidad sobre la MISMA fila. Acá se confirma la
    # precondición backend: una alerta con varias reglas vinculadas
    # sigue siendo UNA fila en /alerts/open (nunca una fila por regla,
    # que sería el escenario que rompería ese dedupe).
    alerts_open_final = open_alerts()["alerts"]
    matches_alert_id_3 = [a for a in alerts_open_final if a["id"] == alert_id_3]
    check("T-09: la alerta T-03 (2 reglas vinculadas) aparece UNA sola vez en /alerts/open", len(matches_alert_id_3) == 1, f"count={len(matches_alert_id_3)}")

    # ================= T-10: alerts -> alert_rule -> heuristic_rules intacta =================
    r10a = report(token_t10, ["Consumo CPU Elevado"])
    r10b = report(token_t10, ["Acceso Honeyfile"])
    alert_id_10 = r10b.json()["alert_id"]
    c = db_conn()
    fk_rows = c.execute(
        """
        SELECT heuristic_rules.name, alert_rule.weight_applied
        FROM alert_rule
        JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
        JOIN alerts ON alerts.id = alert_rule.alert_id
        WHERE alerts.id = %s;
        """,
        (alert_id_10,)
    ).fetchall()
    c.close()
    fk_names = {row[0] for row in fk_rows}
    check("T-10: alerts -> alert_rule -> heuristic_rules sigue resolviendo (FK intactas)", len(fk_rows) >= 2, f"fk_rows={fk_rows}")
    check("T-10: 'Consumo CPU Elevado' vinculada con su peso real (5.0)", any(n == "Consumo CPU Elevado" and abs(float(w) - 5.0) < 0.01 for n, w in fk_rows), str(fk_rows))
    check("T-10: 'Acceso Honeyfile' vinculada con su peso real (100.0)", any(n == "Acceso Honeyfile" and abs(float(w) - 100.0) < 0.01 for n, w in fk_rows), str(fk_rows))

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
