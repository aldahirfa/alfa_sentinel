import sys
p = sys.argv[1]
raw = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")

def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:90])
    s = s.replace(old, new)

# 1. Helpers + barrido periódico, justo después de get_agent_stale_seconds
rep('''    return get_system_setting(cursor, "agent_stale_seconds", default=AGENT_STALE_SECONDS_DEFAULT, cast=int)
''', '''    return get_system_setting(cursor, "agent_stale_seconds", default=AGENT_STALE_SECONDS_DEFAULT, cast=int)


# --- Estado de comunicación del endpoint (regla única, 2026-09-24) ---
#
# El servidor solo sabe de un endpoint por los heartbeats de su agente,
# así que hay UN solo estado de conexión, definido por una sola regla:
#
#   En línea          -> último heartbeat hace menos de agent_stale_seconds
#   Sin comunicación  -> heartbeat más viejo que el umbral (o nunca llegó)
#   Aislado           -> hay un aislamiento ejecutado (prioridad, se
#                        calcula aparte con _agent_is_isolated_sql)
#
# "Sin comunicación" no presupone la causa: puede ser un apagado normal,
# una caída de red o un agente neutralizado por un ataque.
#
# agents.status se mantiene coherente con esa regla: el heartbeat lo
# pone en ONLINE y mark_stale_agents_offline() lo baja a OFFLINE cuando
# vence el umbral (hilo de fondo cada PRESENCE_SWEEP_SECONDS). Las
# consultas usan además agent_online_sql()/is_agent_online(), que
# aplican la regla completa, para no depender del retraso del barrido.

PRESENCE_SWEEP_SECONDS = 10


def agent_online_sql(stale_seconds, table="agents"):
    """Expresión SQL booleana: el agente está en línea."""

    return (
        f"({table}.status = 'ONLINE' AND {table}.last_seen_at IS NOT NULL "
        f"AND {table}.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{int(stale_seconds)} seconds')"
    )


def is_agent_online(status, last_seen_at, stale_seconds):
    """Misma regla que agent_online_sql(), para filas ya leídas."""

    if status != "ONLINE" or last_seen_at is None:
        return False
    return (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() < stale_seconds


def mark_stale_agents_offline(cursor, stale_seconds=None):
    """Pasa a OFFLINE los agentes cuyo último heartbeat venció.
    Devuelve cuántos cambiaron."""

    if stale_seconds is None:
        stale_seconds = get_agent_stale_seconds(cursor)
    cursor.execute(
        f"""
        UPDATE agents
        SET status = 'OFFLINE', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'ONLINE'
          AND (last_seen_at IS NULL
               OR last_seen_at < CURRENT_TIMESTAMP - INTERVAL '{int(stale_seconds)} seconds');
        """
    )
    return cursor.rowcount


def _presence_sweeper_loop(stop_event):
    while not stop_event.wait(PRESENCE_SWEEP_SECONDS):
        try:
            connection = get_connection()
            try:
                with connection.cursor() as cursor:
                    changed = mark_stale_agents_offline(cursor)
                    connection.commit()
                if changed:
                    print(f"[presencia] {changed} endpoint(s) pasaron a 'Sin comunicación'")
            finally:
                connection.close()
        except Exception as error:  # la base puede no estar lista todavía
            print(f"[presencia] no se pudo actualizar el estado: {error}")


_presence_stop = threading.Event()


@app.on_event("startup")
def _start_presence_sweeper():
    threading.Thread(
        target=_presence_sweeper_loop,
        args=(_presence_stop,),
        name="alfa-presence-sweeper",
        daemon=True,
    ).start()


@app.on_event("shutdown")
def _stop_presence_sweeper():
    _presence_stop.set()
''')
rep("import secrets\nimport hashlib\n", "import secrets\nimport hashlib\nimport threading\n")

# 2. _endpoint_cte: status_bucket = 'ok' / 'offline' con la regla única
rep('''               CASE
                   WHEN agents.status != 'ONLINE' THEN 'offline'
                   WHEN agents.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds' THEN 'ok'
                   ELSE 'attention'
               END AS status_bucket,''',
'''               CASE
                   WHEN {online_sql} THEN 'ok'
                   ELSE 'offline'
               END AS status_bucket,''')
rep('''""".format(stale_seconds=stale_seconds)
''', '''""".format(online_sql=agent_online_sql(stale_seconds))
''')

# 3. Drawer de endpoint: conn_status en vez de agent_health
rep('''            # Mismo cálculo que _endpoint_cte()/api_endpoints() (lista de
            # Endpoints en React) -- Healthy/Warning/Offline según el
            # último heartbeat contra el umbral configurado. No es un
            # dato nuevo, es la misma fórmula real aplicada acá para
            # que el drawer y la lista digan lo mismo.
            if row[6] != "ONLINE":
                agent_health = "OFFLINE"
            elif row[7] and (datetime.now(row[7].tzinfo) - row[7]).total_seconds() <= stale_seconds:
                agent_health = "HEALTHY"
            else:
                agent_health = "WARNING"
''', '''            # Regla única de estado (ver agent_online_sql): la misma que
            # la lista de Endpoints, para que el drawer y la lista digan
            # lo mismo. "ISOLATED" se resuelve más abajo, con is_isolated.
            conn_status = "ONLINE" if is_agent_online(row[6], row[7], stale_seconds) else "OFFLINE"
''')

# 4. Honeyfiles: umbral fijo de 30 s -> regla única
rep('''            cursor.execute("SELECT DISTINCT os FROM endpoints ORDER BY os;")
            distinct_os = [r[0] for r in cursor.fetchall()]
''', '''            cursor.execute("SELECT DISTINCT os FROM endpoints ORDER BY os;")
            distinct_os = [r[0] for r in cursor.fetchall()]

            stale_seconds = get_agent_stale_seconds(cursor)
''')
rep('''                    "is_live": (r[5] == "ONLINE" and r[6] is not None and (datetime.now(r[6].tzinfo) - r[6]).total_seconds() < 30) if r[6] else False''',
    '''                    "is_live": is_agent_online(r[5], r[6], stale_seconds)''')
rep('''        is_agent_live = (r[13] == "ONLINE" and last_seen is not None and (datetime.now(last_seen.tzinfo) - last_seen).total_seconds() < 30) if last_seen else False''',
    '''        is_agent_live = is_agent_online(r[13], last_seen, stale_seconds)''')
rep('''            is_online = (r[14] == "ONLINE" and r[15] is not None and (datetime.now(r[15].tzinfo) - r[15]).total_seconds() < 30) if r[15] else False''',
    '''            is_online = is_agent_online(r[14], r[15], get_agent_stale_seconds(cursor))''')

# 5. Dashboard: en línea = regla única y NO aislado (antes un aislado
#    contaba como online y además se restaba de nuevo en offline).
rep('''            cursor.execute("SELECT COUNT(*) FROM agents WHERE status = 'ONLINE';")
            endpoints_online = cursor.fetchone()[0]
''', '''            stale_seconds = get_agent_stale_seconds(cursor)
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM agents
                WHERE {agent_online_sql(stale_seconds)}
                  AND NOT {_agent_is_isolated_sql("agents.id")};
                """
            )
            endpoints_online = cursor.fetchone()[0]
''')

# 6. Drawer de incidente: misma regla
rep('''            is_online = (
                agent_status == "ONLINE" and last_seen_at is not None
                and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() < stale_seconds
            ) if last_seen_at else False
''', '''            is_online = is_agent_online(agent_status, last_seen_at, stale_seconds)
''')

# 7. Reporte: misma regla y etiquetas unificadas
rep('''               (
                   agents.status = 'ONLINE'
                   AND agents.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds'
               ) AS is_online,''', '''               {agent_online_sql(stale_seconds)} AS is_online,''')
rep('''        status_label = "En línea" if is_online else ("Sin señal reciente" if status == "ONLINE" else "Desconectado")''',
    '''        status_label = "En línea" if is_online else "Sin comunicación"''')

# 8. Drawer de endpoint: devolver conn_status (con Aislado) en vez de agent_health
rep("""                "agent_health": agent_health,
""", """                "conn_status": "ISOLATED" if is_isolated else conn_status,
""")

# 9. Lista de endpoints: estado desde la regla única; sin agent_health
rep("""                        WHEN status = 'ONLINE' THEN 'ONLINE'
""", """                        WHEN status_bucket = 'ok' THEN 'ONLINE'
""")
rep("""    agent_health_map = {"ok": "HEALTHY", "attention": "WARNING", "offline": "OFFLINE"}

""", "")
rep("""            "agent_health": agent_health_map[r[7]],
""", "")
rep("""    Diferencia real a propósito: acá "Estado" tiene un solo valor de
    cara al usuario (ONLINE/OFFLINE/ISOLATED, con ISOLATED con
    prioridad sobre el estado de conexión crudo), en vez de las tres
    categorías ok/attention/offline de /endpoints -- así se pidió esta
    pantalla. El estado de conexión más fino (Healthy/Warning/Offline)
    se conserva aparte como "agent_health", derivado de status_bucket
    (ok->HEALTHY, attention->WARNING, offline->OFFLINE). Riesgo sigue
    siendo un eje aparte (Normal/Sospechoso/Alto/Crítico) -- nunca se
    mezcla con conectividad, igual que en el resto del sistema.
""", """    "Estado" (conn_status) tiene un solo valor por endpoint, con la
    regla única de agent_online_sql(): ONLINE (En línea), OFFLINE (Sin
    comunicación) o ISOLATED (Aislado, con prioridad). La antigua
    columna "Agente" (Healthy/Warning/Offline) se eliminó: medía la
    misma señal (el heartbeat) con otra regla y confundía. Riesgo sigue
    siendo un eje aparte -- nunca se mezcla con conectividad.
""")

out = s.replace("\n", "\r\n") if crlf else s
open(p, "w", encoding="utf-8", newline="").write(out)
print("patch aplicado a", p)
