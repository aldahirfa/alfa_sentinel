"""Prueba consolidada end-to-end (pgserver + uvicorn real + agente real
en proceso, nunca simulado) de "Honeyfiles: despliegue automático,
rutas, integridad, reconciliación y ejecución en tiempo real"
(2026-08-17, ver PENDIENTES.md), sección 33: los 10 escenarios pedidos.

Metodología: pgserver efímero (Postgres embebido, no toca la base real
del usuario) + uvicorn real en subproceso + httpx.Client(trust_env=False)
para el lado servidor/admin, y las funciones REALES de agent/ (no
reimplementadas ni mockeadas) para el lado agente:
agent.honeyfile_deployer.apply_honeyfile_policy(), agent.paths, y
agent.honeyfile_sync.HoneyfileSyncThread -- exactamente el mismo código
que corre agent/main.py, contra un directorio temporal real en disco
(ALFA_SENTINEL_ENV se deja en su default 'development', pero se
monkeypatchea agent.paths._DEV_HONEYFILES_DIR a una carpeta temporal
de la prueba en vez de agent/honeyfiles/, para no ensuciar el
repositorio ni pisar honeyfiles reales de otra corrida).

Ejecutar: python3 tests/honeyfiles/test_honeyfiles_e2e.py
"""
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time as time_mod

import pgserver
import httpx
import psycopg

# El sandbox de esta tarea define variables de entorno de proxy
# (ALL_PROXY=socks5h://... etc.) para OTRAS herramientas -- agent/client.py
# usa httpx.get()/post() lisos (sin trust_env=False, a propósito: en
# un despliegue real no hay que tocar eso), y httpx intenta armar un
# transporte SOCKS con esas variables aunque el destino sea 127.0.0.1,
# lo que revienta acá porque 'socksio' no está instalado (no es una
# dependencia real del agente). Se limpian esas variables SOLO en el
# proceso de esta prueba -- no es un cambio al código del agente.
for _proxy_var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    os.environ.pop(_proxy_var, None)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import config as agent_config  # noqa: E402
import paths as agent_paths  # noqa: E402
from honeyfile_deployer import apply_honeyfile_policy  # noqa: E402
from honeyfile_monitor import HoneyfileMonitor  # noqa: E402
from honeyfile_sync import HoneyfileSyncThread  # noqa: E402
from watchdog.observers import Observer  # noqa: E402
from watchdog.events import FileSystemEventHandler  # noqa: E402

# --- carpetas de pruebas propias, nunca agent/honeyfiles/ ni
# agent/test_endpoint/ del repo real (2026-08-17: get_monitored_roots()
# ahora también resuelve/crea una carpeta de "resto del endpoint" en
# desarrollo -- se monkeypatchea también, para no ensuciar el repo). ---
TEST_HONEYFILES_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_honeyfiles_")
TEST_ENDPOINT_ROOT = tempfile.mkdtemp(prefix="alfa_sentinel_test_endpoint_")
agent_paths._DEV_HONEYFILES_DIR = TEST_HONEYFILES_DIR
agent_paths._DEV_ENDPOINT_ROOT = TEST_ENDPOINT_ROOT

# Con la nueva estructura (2026-08-17, ver PENDIENTES.md, "Honeyfiles +
# monitorización completa del endpoint..."), los honeyfiles ya no viven
# directo en la carpeta de desarrollo -- quedan anidados dentro de
# ALFA_ARCHIVOS (sección 17 de la especificación: "la carpeta debe
# crearse automáticamente... Solo UNA por endpoint/ruta lógica").
TEST_HONEYFILES_ALFA_DIR = os.path.join(TEST_HONEYFILES_DIR, agent_paths.ALFA_ARCHIVOS_FOLDER_NAME)

PGDATA_DIR = tempfile.mkdtemp(prefix="alfa_sentinel_test_pgdata_")
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

# La migración de template_id/FK/UNIQUE vive aparte (nunca se corre
# contra la base real del usuario -- ver PENDIENTES.md) pero schema.sql
# YA la incluye (sección 20B) para que una base nueva quede completa de
# una sola vez -- se confirma acá que ambas cosas quedaron coherentes.
check(
    "schema.sql ya trae 'honeyfiles.template_id' (sin necesitar la migración aparte en una base nueva)",
    conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name='honeyfiles' AND column_name='template_id';"
    ).fetchone() is not None,
)

sys.path.insert(0, os.path.join(REPO, "server"))
from security import hash_password  # noqa: E402

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


def make_agent(hostname, os_name="Windows"):
    ep = conn.execute(
        "INSERT INTO endpoints (hostname, os, os_version) VALUES (%s, %s, '11') RETURNING id;",
        (hostname, os_name),
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


agent_1, token_1 = make_agent("endpoint-1-honeyfiles", "Windows")
agent_2, token_2 = make_agent("endpoint-2-honeyfiles", "Windows")
agent_linux, token_linux = make_agent("endpoint-linux-honeyfiles", "Linux")

conn.close()

# --- levantar uvicorn real ---
env = os.environ.copy()
env["DATABASE_URL"] = DATABASE_URL
env["PYTHONPATH"] = os.path.join(REPO, "server")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8072"],
    cwd=os.path.join(REPO, "server"),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

BASE = "http://127.0.0.1:8072"

# El agente REAL (agent/client.py) lee estas constantes de config.py en
# cada llamada -- se apuntan al uvicorn de esta prueba, igual que hace
# agent/main.py::apply_cli_overrides() con --server.
agent_config.SERVER_URL = BASE
agent_config.HONEYFILE_POLICY_URL = f"{BASE}/agent/honeyfile-policy"
agent_config.HONEYFILE_POLICY_REPORT_URL = f"{BASE}/agent/honeyfile-policy/report"

try:
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

    def deploy_template(file_name, target_path="DESKTOP", platform="all", auto_deploy=False, agent_ids=None, file_type="txt"):
        body = {
            "file_name": file_name,
            "file_type": file_type,
            "target_path": target_path,
            "platform": platform,
            "auto_deploy": auto_deploy,
            "content": f"Contenido de prueba -- {file_name}",
            "agent_ids": agent_ids or [],
        }
        r = client.post("/api/honeyfiles/deploy", json=body)
        return r

    def db_conn():
        return psycopg.connect(DATABASE_URL)

    def honeyfiles_count(agent_id, template_id):
        c = db_conn()
        row = c.execute(
            "SELECT COUNT(*) FROM honeyfiles WHERE agent_id=%s AND template_id=%s;", (agent_id, template_id)
        ).fetchone()
        c.close()
        return row[0]

    def honeyfile_row(agent_id, template_id):
        c = db_conn()
        row = c.execute(
            "SELECT id, file_path, file_hash, status FROM honeyfiles WHERE agent_id=%s AND template_id=%s;",
            (agent_id, template_id),
        ).fetchone()
        c.close()
        return row

    def assignment_status(agent_id, template_id):
        c = db_conn()
        row = c.execute(
            "SELECT status FROM agent_honeyfile_templates WHERE agent_id=%s AND template_id=%s;",
            (agent_id, template_id),
        ).fetchone()
        c.close()
        return row[0] if row else None

    # ================================================================
    # Escenario 1: primer instalación (auto_deploy=TRUE, sin
    # asignación manual) -- el agente crea el honeyfile solo, sin
    # intervención manual, la primera vez que sincroniza.
    # ================================================================
    r = deploy_template("Presupuesto_2026", target_path="DOCUMENTS", platform="all", auto_deploy=True)
    check("1: plantilla auto_deploy creada (201/200)", r.status_code == 200, r.text[:200])
    template_1 = r.json()["template_id"]

    watched_1 = apply_honeyfile_policy(token_1)
    check("1: apply_honeyfile_policy devuelve 1 ruta vigilada", len(watched_1) == 1, str(watched_1))
    check("1: el archivo existe físicamente en disco", len(watched_1) == 1 and os.path.isfile(watched_1[0]))
    check("1: agent_honeyfile_templates pasó a CREATED", assignment_status(agent_1, template_1) == "CREATED")
    row_1 = honeyfile_row(agent_1, template_1)
    check("1: fila real en 'honeyfiles' con hash no vacío", row_1 is not None and bool(row_1[2]))

    # ================================================================
    # Escenario 2: reinicio no duplica -- una segunda sincronización
    # (equivalente a reiniciar el agente) sobre un honeyfile intacto no
    # debe crear una segunda fila ni reescribir el archivo.
    # ================================================================
    watched_1_again = apply_honeyfile_policy(token_1)
    check("2: segunda sincronización sigue vigilando la misma ruta", watched_1_again == watched_1, str(watched_1_again))
    check("2: sigue existiendo una sola fila en 'honeyfiles' para este agente+plantilla", honeyfiles_count(agent_1, template_1) == 1)
    row_1_again = honeyfile_row(agent_1, template_1)
    check("2: mismo id de fila (UPSERT, no INSERT duplicado)", row_1_again[0] == row_1[0])
    check("2: mismo hash (no se reescribió el contenido)", row_1_again[2] == row_1[2])

    # ================================================================
    # Escenario 3: asignación nueva mientras el agente sigue corriendo,
    # SIN reiniciar -- se ejercita el hilo real HoneyfileSyncThread
    # (mismo código que agent/main.py arranca), no una llamada directa
    # a apply_honeyfile_policy(), para probar el mecanismo completo:
    # detecta la ruta nueva y la suma a HoneyfileMonitor.known_paths y
    # al Observer, en caliente.
    # ================================================================
    # Raíz vigilada propia y vacía (no "." del repo -- evita depender
    # del límite de inotify de este sandbox al recorrer un checkout
    # completo, que no aporta nada a lo que esta prueba verifica).
    dummy_watched_root_dir = tempfile.mkdtemp(prefix="alfa_sentinel_test_watchroot_")
    observer = Observer()
    watched_root = os.path.abspath(dummy_watched_root_dir)
    observer.schedule(FileSystemEventHandler(), dummy_watched_root_dir, recursive=True)
    observer.start()
    honeyfile_monitor = HoneyfileMonitor(known_paths=watched_1)
    check("3 (previo): la ruta del escenario 1 ya es honeyfile conocido", honeyfile_monitor.is_honeyfile(watched_1[0]))

    sync_thread = HoneyfileSyncThread(
        token_1, honeyfile_monitor, observer, FileSystemEventHandler(), watched_root, set()
    )

    r = deploy_template("Notas_Reunion", target_path="DESKTOP", platform="all", auto_deploy=False, agent_ids=[agent_1])
    check("3: plantilla manual creada y asignada", r.status_code == 200, r.text[:200])
    template_3 = r.json()["template_id"]
    check("3: antes de sincronizar, el nuevo honeyfile NO es conocido todavía", not honeyfile_monitor.is_honeyfile(os.path.join(TEST_HONEYFILES_ALFA_DIR, "Notas_Reunion.txt")))

    sync_thread._sync_once()  # un solo ciclo manual, sin esperar SYNC_INTERVAL_SECONDS

    new_path = os.path.join(TEST_HONEYFILES_ALFA_DIR, "Notas_Reunion.txt")
    check("3: el archivo se creó en disco sin reiniciar el agente", os.path.isfile(new_path))
    check("3: HoneyfileMonitor.known_paths lo suma en caliente (add_known_path)", honeyfile_monitor.is_honeyfile(new_path))
    check("3: assignment pasó a CREATED", assignment_status(agent_1, template_3) == "CREATED")

    observer.stop()
    observer.join()
    shutil.rmtree(dummy_watched_root_dir, ignore_errors=True)

    # ================================================================
    # Escenario 4: el honeyfile desaparece del disco -> reconciliación
    # lo recrea (caso B, sección 22), sin duplicar la fila en 'honeyfiles'.
    # ================================================================
    os.remove(new_path)
    check("4 (previo): el archivo efectivamente ya no existe", not os.path.exists(new_path))
    row_before_4 = honeyfile_row(agent_1, template_3)

    watched_after_delete = apply_honeyfile_policy(token_1)
    check("4: el archivo se recreó en disco", os.path.isfile(new_path))
    check("4: sigue habiendo una sola fila en 'honeyfiles' (UPSERT, no duplicado)", honeyfiles_count(agent_1, template_3) == 1)
    row_after_4 = honeyfile_row(agent_1, template_3)
    check("4: mismo id de fila que antes de borrarlo (misma identidad, no una nueva)", row_after_4[0] == row_before_4[0])

    # ================================================================
    # Escenario 5: modificación detectada en reconciliación -- NUNCA
    # se restaura el contenido, solo se registra el hash nuevo (caso C).
    # ================================================================
    with open(new_path, "w", encoding="utf-8") as f:
        f.write("CONTENIDO ALTERADO -- esto simula que alguien/algo tocó el honeyfile")
    tampered_hash = hashlib.sha256(open(new_path, "rb").read()).hexdigest()

    apply_honeyfile_policy(token_1)

    with open(new_path, "r", encoding="utf-8") as f:
        content_after_sync = f.read()
    check("5: el contenido alterado NO se restauró (fuera de alcance restaurar)", "ALTERADO" in content_after_sync)
    row_after_5 = honeyfile_row(agent_1, template_3)
    check("5: el hash registrado en el servidor se actualizó al hash real (alterado)", row_after_5[2] == tampered_hash, f"db={row_after_5[2]} real={tampered_hash}")
    check("5: la asignación sigue en CREATED (no se invierte a PENDING/FAILED por una modificación)", assignment_status(agent_1, template_3) == "CREATED")

    # ================================================================
    # Escenario 6: auto_deploy=TRUE -- una plantilla nueva marcada así
    # se materializa sola para un endpoint SIN asignación manual previa.
    # (Reutiliza el mismo mecanismo que el escenario 1, sobre un agente
    # que nunca fue tocado a mano para esta plantilla puntual.)
    # ================================================================
    r = deploy_template("Politica_Seguridad", target_path="DOCUMENTS", platform="all", auto_deploy=True)
    template_6 = r.json()["template_id"]
    watched_2 = apply_honeyfile_policy(token_2)
    check("6: auto_deploy=TRUE alcanza también a un endpoint sin asignación manual (agent_2)", any("Politica_Seguridad" in p for p in watched_2), str(watched_2))
    check("6: agent_2 recibe assignment CREATED para esa plantilla", assignment_status(agent_2, template_6) == "CREATED")

    # ================================================================
    # Escenario 7: auto_deploy=FALSE -- una plantilla asignada a mano
    # SOLO a agent_1 nunca aparece para agent_2 (comprobado también,
    # con más detalle de aislamiento, en el escenario 9).
    # ================================================================
    r = deploy_template("Solo_Para_Agente1", target_path="DESKTOP", platform="all", auto_deploy=False, agent_ids=[agent_1])
    template_7 = r.json()["template_id"]
    apply_honeyfile_policy(token_1)
    check("7: auto_deploy=FALSE -- agent_1 (asignado a mano) SÍ la recibe", assignment_status(agent_1, template_7) == "CREATED")
    check("7: auto_deploy=FALSE -- agent_2 (no asignado) nunca la ve", assignment_status(agent_2, template_7) is None)

    # ================================================================
    # Escenario 8: plantilla incompatible por SO, en ambos sentidos --
    # auto_deploy=TRUE con operating_system fijo no cruza de SO.
    # ================================================================
    r = deploy_template("Solo_Linux", target_path="DOCUMENTS", platform="linux", auto_deploy=True)
    template_linux_only = r.json()["template_id"]
    apply_honeyfile_policy(token_1)  # agent_1 es Windows
    check("8: plantilla LINUX auto_deploy no se asigna a un agente Windows", assignment_status(agent_1, template_linux_only) is None)

    r = deploy_template("Solo_Windows", target_path="DOCUMENTS", platform="windows", auto_deploy=True)
    template_windows_only = r.json()["template_id"]
    apply_honeyfile_policy(token_linux)  # agent_linux es Linux
    check("8: plantilla WINDOWS auto_deploy no se asigna a un agente Linux", assignment_status(agent_linux, template_windows_only) is None)

    # Confirmación positiva de que SÍ cruza cuando corresponde (Linux -> Linux):
    apply_honeyfile_policy(token_linux)
    check("8: plantilla LINUX auto_deploy SÍ se asigna a un agente Linux", assignment_status(agent_linux, template_linux_only) == "CREATED")

    # ================================================================
    # Escenario 9: dos endpoints, cada uno recibe SOLO su propia
    # asignación (ni la del otro, ni las auto_deploy=FALSE ajenas).
    # ================================================================
    r = deploy_template("Solo_Para_Agente2", target_path="DOWNLOADS", platform="all", auto_deploy=False, agent_ids=[agent_2])
    template_9 = r.json()["template_id"]
    apply_honeyfile_policy(token_2)
    check("9: agent_2 recibe SU plantilla", assignment_status(agent_2, template_9) == "CREATED")
    check("9: agent_1 NUNCA ve la plantilla asignada solo a agent_2", assignment_status(agent_1, template_9) is None)
    check("9 (cruzado, del escenario 7): agent_2 tampoco ve la de agent_1", assignment_status(agent_2, template_7) is None)

    # ================================================================
    # Escenario 10: fallo real de creación -> FAILED + motivo, y
    # reintento exitoso en la siguiente sincronización una vez resuelto
    # el problema. Se fuerza un PermissionError REAL (no simulado):
    # carpeta de pruebas propia, sin permiso de escritura.
    # ================================================================
    fail_dir = tempfile.mkdtemp(prefix="alfa_sentinel_test_honeyfiles_fail_")
    original_dev_dir = agent_paths._DEV_HONEYFILES_DIR
    agent_paths._DEV_HONEYFILES_DIR = fail_dir
    os.chmod(fail_dir, stat.S_IRUSR | stat.S_IXUSR)  # r-x, sin escritura

    try:
        r = deploy_template("Reporte_Financiero", target_path="DOCUMENTS", platform="all", auto_deploy=False, agent_ids=[agent_1])
        template_10 = r.json()["template_id"]

        apply_honeyfile_policy(token_1)
        check("10: la asignación quedó en FAILED tras el error real de escritura", assignment_status(agent_1, template_10) == "FAILED")

        c = db_conn()
        # El servidor no persiste el motivo del fallo en una columna
        # propia (sección 25: "no inventar estados nuevos que la BD no
        # soporte") -- el detalle del error se imprime en consola del
        # agente (ver honeyfile_deployer.py, rama OSError) y se manda
        # en el reporte HTTP; lo verificable en BD es el estado FAILED.
        c.close()

    finally:
        os.chmod(fail_dir, stat.S_IRWXU)
        agent_paths._DEV_HONEYFILES_DIR = original_dev_dir
        shutil.rmtree(fail_dir, ignore_errors=True)

    # Reintento: con el directorio real (con permisos) restaurado, la
    # próxima sincronización vuelve a ofrecerlo como pendiente (WHERE
    # status IN ('PENDING','FAILED')) y esta vez sí puede escribirlo.
    watched_retry = apply_honeyfile_policy(token_1)
    check("10: reintento posterior tiene éxito -- pasa a CREATED", assignment_status(agent_1, template_10) == "CREATED")
    check("10: el archivo existe de verdad en disco tras el reintento", any("Reporte_Financiero" in p and os.path.isfile(p) for p in watched_retry), str(watched_retry))

finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    pg.cleanup()
    shutil.rmtree(PGDATA_DIR, ignore_errors=True)
    shutil.rmtree(TEST_HONEYFILES_DIR, ignore_errors=True)
    shutil.rmtree(TEST_ENDPOINT_ROOT, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_honeyfiles_e2e.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
