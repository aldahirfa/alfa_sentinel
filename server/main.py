import os

from fastapi import FastAPI, HTTPException, Header, Request, Depends, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from database import get_connection
from security import verify_password, hash_password

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

load_dotenv()

app = FastAPI()

# SessionMiddleware es lo que nos da la "pulsera de concierto": firma
# una cookie con itsdangerous para que el navegador la pueda guardar,
# y el servidor pueda confiar en ella sin volver a pedir contraseña
# en cada clic. SESSION_SECRET tiene que ser secreto y estable -- si
# cambia, todas las sesiones abiertas se invalidan de golpe.
SESSION_SECRET = os.getenv("SESSION_SECRET", "cambia-esto-en-produccion")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

templates = Jinja2Templates(directory="templates")


def time_ago(value):
    """Filtro de Jinja2 para 'hace X minutos' -- lo usa el dashboard
    en varios lugares (alertas recientes, actividad reciente,
    honeyfiles) en vez de mostrar la fecha completa cada vez."""

    if value is None:
        return "—"

    seconds = int((datetime.now() - value).total_seconds())

    if seconds < 0:
        seconds = 0

    if seconds < 60:
        return f"hace {seconds}s"

    minutes = seconds // 60

    if minutes < 60:
        return f"hace {minutes} min"

    hours = minutes // 60

    if hours < 24:
        return f"hace {hours} h"

    days = hours // 24

    return f"hace {days} d"


templates.env.filters["timeago"] = time_ago

# Para pasarle datos reales (ya calculados en Python) a Chart.js del
# lado del cliente sin reescribir la consulta en JS -- json.dumps
# normal, nada de HTML-escaping raro (default=str por si se cuela un
# tipo no serializable como Decimal).
templates.env.filters["tojson"] = lambda obj: json.dumps(obj, default=str)

# Umbral para considerar que un agente ONLINE está "al día": si su
# último heartbeat es más viejo que esto, lo marcamos como "requiere
# atención" en vez de "funcionando", aunque la BD todavía diga
# ONLINE. Es una aproximación -- hoy el agente manda heartbeat solo
# cuando se lo pide algo puntual (no hay bucle automático todavía,
# tarea pendiente #3), así que este umbral es generoso a propósito.
AGENT_STALE_SECONDS = 120

# Sirve server/static/* en /static/* -- ahí vive el logo (logo-icon.png,
# logo-full.png).
app.mount("/static", StaticFiles(directory="static"), name="static")


class AgentCreate(BaseModel):
    hostname: str
    operating_system: str
    os_version: str | None = None
    architecture: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None

class EnrollmentRequest(BaseModel):
    token: str
    hostname: str
    operating_system: str
    os_version: str | None = None
    architecture: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None


class EventCreate(BaseModel):
    event_type: str
    description: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    metadata: dict | None = None


class AlertCreate(BaseModel):
    severity: str
    title: str
    description: str | None = None
    risk_score: int | None = None
    rule_name: str | None = None
    details: dict | None = None
    event_ids: list[int] | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str | None = None
    role: str = "admin"


class IncidentCreate(BaseModel):
    alert_id: int
    classification: str | None = None


class AlertStatusUpdate(BaseModel):
    status: str


class AlertNoteCreate(BaseModel):
    note: str


class IncidentAlertLink(BaseModel):
    alert_id: int


class IncidentStatusUpdate(BaseModel):
    status: str


class IncidentClassify(BaseModel):
    classification: str


class IncidentAssign(BaseModel):
    user_id: int


class IncidentDescriptionUpdate(BaseModel):
    description: str


class IncidentNoteCreate(BaseModel):
    note: str


class ProfileUpdate(BaseModel):
    full_name: str
    email: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def resolve_agent_id(cursor, x_agent_credential: str) -> int:
    """Traduce la credencial que manda el agente en el header a su
    agent_id. Centraliza lo que antes estaba repetido en cada endpoint
    que necesita saber "qué agente me está hablando"."""

    credential_hash = hashlib.sha256(
        x_agent_credential.encode()
    ).hexdigest()

    cursor.execute(
        """
        SELECT agent_id
        FROM agent_credentials
        WHERE credential_hash = %s
          AND is_active = TRUE;
        """,
        (credential_hash,)
    )

    result = cursor.fetchone()

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Credencial inválida"
        )

    return result[0]


def get_current_user(request: Request) -> dict:
    """El 'portero': lee la sesión (la pulsera) y devuelve quién es la
    persona logueada. Si no hay sesión válida, corta con 401 antes de
    que la ruta protegida llegue a ejecutarse."""

    user = request.session.get("user")

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="No has iniciado sesión"
        )

    return user


def require_role(role_name: str):
    """Fábrica de dependencias: require_role('admin') exige sesión
    válida Y que el rol coincida. Se usa así en una ruta:
        Depends(require_role('admin'))
    """

    def dependency(user: dict = Depends(get_current_user)) -> dict:

        if role_name not in user.get("roles", []):
            raise HTTPException(
                status_code=403,
                detail=f"Se requiere el rol '{role_name}'"
            )

        return user

    return dependency


@app.post("/login")
def login(credentials: LoginRequest, request: Request):

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT id, password_hash, full_name, is_active
                FROM users
                WHERE username = %s;
                """,
                (credentials.username,)
            )

            row = cursor.fetchone()

            # Mismo mensaje de error tanto si el usuario no existe
            # como si la contraseña está mal -- así no le confirmamos
            # a quien intenta entrar si el usuario es válido o no.
            if row is None:
                raise HTTPException(
                    status_code=401,
                    detail="Usuario o contraseña incorrectos"
                )

            user_id, password_hash, full_name, is_active = row

            if not is_active:
                raise HTTPException(
                    status_code=401,
                    detail="Usuario deshabilitado"
                )

            if not verify_password(credentials.password, password_hash):
                raise HTTPException(
                    status_code=401,
                    detail="Usuario o contraseña incorrectos"
                )

            cursor.execute(
                """
                SELECT roles.name
                FROM roles
                JOIN user_roles ON user_roles.role_id = roles.id
                WHERE user_roles.user_id = %s;
                """,
                (user_id,)
            )

            roles = [role_row[0] for role_row in cursor.fetchall()]

            cursor.execute(
                """
                UPDATE users
                SET last_login_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (user_id,)
            )

            connection.commit()

        request.session["user"] = {
            "id": user_id,
            "username": credentials.username,
            "full_name": full_name,
            "roles": roles
        }

        return {
            "message": "Sesión iniciada",
            "username": credentials.username,
            "roles": roles
        }

    finally:
        connection.close()


@app.post("/logout")
def logout(request: Request):

    request.session.clear()

    return {
        "message": "Sesión cerrada"
    }


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Para probar rápido si la sesión está activa y qué rol tiene."""

    return user


@app.put("/me")
def update_profile(
    profile: ProfileUpdate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Cada persona edita su propio nombre/correo -- no hay 'user_id'
    en el body, siempre se actualiza a quien está logueado (sale de
    la sesión), para que nadie pueda editar el perfil de otro solo
    cambiando un número."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if profile.email:

                cursor.execute(
                    "SELECT id FROM users WHERE email = %s AND id != %s;",
                    (profile.email, user["id"])
                )

                if cursor.fetchone():
                    raise HTTPException(
                        status_code=409,
                        detail="Ese correo ya está en uso por otra cuenta"
                    )

            cursor.execute(
                """
                UPDATE users
                SET full_name = %s, email = %s
                WHERE id = %s;
                """,
                (profile.full_name, profile.email, user["id"])
            )

            connection.commit()

    finally:
        connection.close()

    # La sesión guarda una copia de full_name para no consultar la BD
    # en cada página (por eso el nombre aparece en la barra superior
    # sin una query extra) -- hay que refrescarla aquí o el cambio no
    # se vería hasta la próxima vez que la persona inicie sesión.
    request.session["user"] = {**user, "full_name": profile.full_name}

    return {
        "message": "Perfil actualizado",
        "full_name": profile.full_name,
        "email": profile.email
    }


@app.post("/me/password")
def change_password(
    change: PasswordChange,
    user: dict = Depends(get_current_user)
):

    if len(change.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 8 caracteres"
        )

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s;",
                (user["id"],)
            )

            row = cursor.fetchone()

            if row is None or not verify_password(change.current_password, row[0]):
                raise HTTPException(
                    status_code=401,
                    detail="La contraseña actual no es correcta"
                )

            new_hash = hash_password(change.new_password)

            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s;",
                (new_hash, user["id"])
            )

            connection.commit()

    finally:
        connection.close()

    return {"message": "Contraseña actualizada"}


@app.get("/perfil")
def perfil_page(request: Request):

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT username, full_name, email, created_at, last_login_at
                FROM users
                WHERE id = %s;
                """,
                (user["id"],)
            )

            row = cursor.fetchone()

    finally:
        connection.close()

    account = {
        "username": row[0],
        "full_name": row[1],
        "email": row[2],
        "created_at": row[3],
        "last_login_at": row[4]
    }

    return templates.TemplateResponse(
        request,
        "perfil.html",
        {"user": user, "active_page": None, "account": account}
    )


@app.post("/users")
def create_user(
    new_user: UserCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Reemplaza a bootstrap_admin.py para el uso diario: ahora un
    admin ya logueado puede dar de alta a otras personas desde el
    propio sistema, en vez de correr un script a mano cada vez."""

    if len(new_user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La contraseña debe tener al menos 8 caracteres"
        )

    password_hash = hash_password(new_user.password)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id FROM users WHERE username = %s;",
                (new_user.username,)
            )

            if cursor.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un usuario '{new_user.username}'"
                )

            # Busca el rol pedido; si todavía no existe, lo crea
            # (mismo patrón que usaba bootstrap_admin.py).
            cursor.execute(
                "SELECT id FROM roles WHERE name = %s;",
                (new_user.role,)
            )

            role_row = cursor.fetchone()

            if role_row:
                role_id = role_row[0]
            else:
                cursor.execute(
                    """
                    INSERT INTO roles (name, description)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (new_user.role, f"Rol '{new_user.role}'")
                )
                role_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, full_name, email)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    new_user.username,
                    password_hash,
                    new_user.full_name,
                    new_user.email
                )
            )

            user_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES (%s, %s);
                """,
                (user_id, role_id)
            )

            connection.commit()

        return {
            "message": "Usuario creado correctamente",
            "user_id": user_id,
            "username": new_user.username,
            "role": new_user.role
        }

    finally:
        connection.close()


@app.get("/")
def root():
    return {
        "message": "Servidor funcionando"
    }


@app.get("/login")
def login_page(request: Request):
    """La página con el formulario. Distinta de POST /login, que es
    la que de verdad procesa usuario+contraseña -- esta solo sirve el
    HTML."""

    return templates.TemplateResponse(request, "login.html")


def require_session_user(request: Request):
    """Versión 'de página' de get_current_user: en vez de devolver 401
    en JSON, devuelve None para que la ruta que llama decida mandar al
    navegador a /login. Evita repetir las mismas dos líneas en cada
    página protegida."""

    return request.session.get("user")


def render_placeholder(request: Request, active_page: str, title: str, description: str):
    """Páginas del menú que todavía no tienen funcionalidad real detrás
    (la tabla existe en la BD pero nada la llena todavía, o la
    funcionalidad ni siquiera está construida). Se ven consistentes con
    el resto de la consola y son honestas sobre qué falta, en vez de
    simular datos que no existen."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        request,
        "placeholder.html",
        {
            "user": user,
            "active_page": active_page,
            "title": title,
            "description": description
        }
    )


@app.get("/dashboard")
def dashboard_page(request: Request):
    """Página protegida. A diferencia de las rutas de API (que
    devuelven 401 en JSON), aquí si no hay sesión mandamos al
    navegador de vuelta al login -- es lo que espera un humano
    navegando, no un programa consumiendo la API.

    Si la base de datos no responde, la página igual se renderiza
    (con un aviso arriba) en vez de devolver un error 500 en blanco --
    en una consola de seguridad, que el dashboard se caiga cuando la
    BD falla es peor que mostrar "no disponible" con claridad."""

    user = request.session.get("user")

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    try:
        connection = get_connection()
    except Exception:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "active_page": "dashboard",
                "db_ok": False,
                "summary": None
            }
        )

    try:
        with connection.cursor() as cursor:

            # --- Tarjetas de resumen ---

            cursor.execute("SELECT COUNT(*) FROM agents;")
            total_endpoints = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM agents WHERE status = 'ONLINE';")
            connected_endpoints = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
                """
            )
            detections_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM incidents WHERE status = 'OPEN';"
            )
            incidents_active = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM incidents WHERE status = 'IN_PROGRESS';"
            )
            incidents_investigating = cursor.fetchone()[0]

            # Distribución de riesgo: severidad de las alertas TODAVÍA
            # abiertas (status = 'NEW'). "Normal" no es una severidad
            # que el agente reporte -- se calcula acá como "endpoints
            # sin ninguna alerta abierta".
            cursor.execute(
                """
                SELECT alerts.severity, COUNT(DISTINCT alerts.agent_id) AS n
                FROM alerts
                WHERE alerts.status = 'NEW'
                GROUP BY alerts.severity;
                """
            )
            severity_rows = dict(cursor.fetchall())

            critical_n = severity_rows.get("CRITICAL", 0)
            high_n = severity_rows.get("HIGH", 0)
            suspicious_n = severity_rows.get("SUSPICIOUS", 0)

            cursor.execute(
                "SELECT COUNT(DISTINCT agent_id) FROM alerts WHERE status = 'NEW';"
            )
            agents_with_open_alerts = cursor.fetchone()[0]

            normal_n = max(total_endpoints - agents_with_open_alerts, 0)

            # Riesgo actual: por el peor caso presente, no por volumen
            # -- un solo CRÍTICO pesa más que diez SOSPECHOSAS. Es una
            # regla simple a propósito; si más adelante definimos un
            # modelo de riesgo con pesos, este es el lugar donde iría.
            if critical_n > 0:
                overall_risk = "CRÍTICO"
            elif high_n > 0:
                overall_risk = "ALTO"
            elif suspicious_n > 0:
                overall_risk = "SOSPECHOSO"
            else:
                overall_risk = "NORMAL"

            # Colores fijados acá (no en el template) para que Chart.js
            # los reciba como hex literal -- un <canvas> no resuelve
            # var(--css-var) como sí lo hace un <svg style="...">, así
            # que se calculan del lado del servidor, en el mismo lugar
            # que ya es la fuente de verdad del mapeo de severidad
            # (Normal=verde, Sospechoso=amarillo, Alto=naranja, Crítico=rojo).
            risk_distribution = [
                {"label": "Crítico", "key": "CRITICAL", "count": critical_n, "color": "#dc2626"},
                {"label": "Alto", "key": "HIGH", "count": high_n, "color": "#ea580c"},
                {"label": "Sospechoso", "key": "SUSPICIOUS", "count": suspicious_n, "color": "#ca8a04"},
                {"label": "Normal", "key": "NORMAL", "count": normal_n, "color": "#16a34a"},
            ]
            risk_max = max((r["count"] for r in risk_distribution), default=0) or 1

            # Para el donut de "Distribución de riesgo": porcentaje de
            # cada franja + dónde empieza su arco. Con pathLength="100"
            # en el <circle> del SVG, estos números se pueden usar
            # directo como stroke-dasharray/stroke-dashoffset sin tener
            # que calcular circunferencias.
            risk_total = sum(r["count"] for r in risk_distribution)
            cumulative_pct = 0.0

            for r in risk_distribution:
                r["pct"] = round((r["count"] / risk_total * 100), 2) if risk_total else 0
                r["dash_offset"] = round(-cumulative_pct, 2)
                cumulative_pct += r["pct"]

            # --- Alertas recientes (solo las que siguen sin revisar) ---

            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title,
                       agents.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                WHERE alerts.status = 'NEW'
                ORDER BY alerts.created_at DESC
                LIMIT 6;
                """
            )
            recent_alerts = cursor.fetchall()

            # --- Endpoints con mayor riesgo ---

            cursor.execute(
                """
                SELECT agents.id, agents.hostname, agents.status, agents.ip_address,
                       MAX(
                           CASE alerts.severity
                               WHEN 'CRITICAL' THEN 4
                               WHEN 'HIGH' THEN 3
                               WHEN 'SUSPICIOUS' THEN 2
                               ELSE 1
                           END
                       ) AS risk_rank,
                       COUNT(*) AS detection_count
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                WHERE alerts.status = 'NEW'
                GROUP BY agents.id, agents.hostname, agents.status, agents.ip_address
                ORDER BY risk_rank DESC, detection_count DESC
                LIMIT 5;
                """
            )
            rank_labels = {4: "CRITICAL", 3: "HIGH", 2: "SUSPICIOUS", 1: "NORMAL"}
            top_risk_endpoints = [
                {
                    "agent_id": row[0],
                    "hostname": row[1],
                    "status": row[2],
                    "ip_address": row[3],
                    "severity": rank_labels[row[4]],
                    "detection_count": row[5]
                }
                for row in cursor.fetchall()
            ]

            # --- Estado de agentes (3 estados, a partir de status +
            # antigüedad del último heartbeat) ---

            cursor.execute("SELECT status, last_seen_at FROM agents;")
            agent_rows = cursor.fetchall()

            agents_ok = 0
            agents_attention = 0
            agents_offline = 0
            last_heartbeat = None

            for status, last_seen_at in agent_rows:

                if last_seen_at and (last_heartbeat is None or last_seen_at > last_heartbeat):
                    last_heartbeat = last_seen_at

                if status != "ONLINE":
                    agents_offline += 1
                elif last_seen_at and (datetime.now() - last_seen_at).total_seconds() <= AGENT_STALE_SECONDS:
                    agents_ok += 1
                else:
                    agents_attention += 1

            # --- Honeyfiles: resumen ---

            cursor.execute("SELECT COUNT(*) FROM honeyfiles;")
            honeyfiles_total = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM alerts
                JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                WHERE heuristic_rules.name = 'honeyfile_access'
                  AND alerts.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
                """
            )
            honeyfile_activations_24h = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT agents.hostname, alerts.created_at
                FROM alerts
                JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                JOIN agents ON agents.id = alerts.agent_id
                WHERE heuristic_rules.name = 'honeyfile_access'
                ORDER BY alerts.created_at DESC
                LIMIT 1;
                """
            )
            last_honeyfile_row = cursor.fetchone()
            last_honeyfile = (
                {"hostname": last_honeyfile_row[0], "created_at": last_honeyfile_row[1]}
                if last_honeyfile_row else None
            )

            # --- Incidentes: resumen por severidad (de la alerta que
            # los originó), solo los abiertos ---

            cursor.execute(
                """
                SELECT alerts.severity, COUNT(*)
                FROM incidents
                JOIN alerts ON alerts.id = incidents.alert_id
                WHERE incidents.status = 'OPEN'
                GROUP BY alerts.severity;
                """
            )
            incident_severity = dict(cursor.fetchall())

            # --- Respuesta: acciones de aislamiento de host. Hoy no
            # hay ningún endpoint que escriba en 'host_isolations', así
            # que esto va a mostrar 0/0/0 -- y eso es correcto: es el
            # dato real, no un placeholder. Cuando el módulo de
            # Respuesta exista, esta misma consulta ya lo va a reflejar
            # sin tocar nada acá. ---

            cursor.execute(
                "SELECT status, COUNT(*) FROM host_isolations GROUP BY status;"
            )
            isolation_status = dict(cursor.fetchall())

            response_pending = isolation_status.get("REQUESTED", 0)
            response_executed = isolation_status.get("EXECUTED", 0)
            response_failed = isolation_status.get("FAILED", 0)

            # --- Actividad reciente del sistema: alertas + eventos
            # crudos mezclados, lo más nuevo primero. Distinto de
            # "Alertas recientes": esto es un feed general, no solo lo
            # que requiere atención. ---

            cursor.execute(
                """
                (
                    SELECT 'alert' AS kind, alerts.severity AS sev,
                           alerts.title AS label, agents.hostname AS hostname,
                           alerts.created_at AS ts,
                           alerts.details->>'last_file' AS file_path
                    FROM alerts
                    JOIN agents ON agents.id = alerts.agent_id
                    ORDER BY alerts.created_at DESC
                    LIMIT 15
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           events.event_type AS label, agents.hostname AS hostname,
                           events.detected_at AS ts,
                           events.metadata->>'file_path' AS file_path
                    FROM events
                    JOIN agents ON agents.id = events.agent_id
                    ORDER BY events.detected_at DESC
                    LIMIT 15
                )
                ORDER BY ts DESC
                LIMIT 15;
                """
            )

            # Los tipos de evento que manda el agente son nombres de
            # código (file_modified, etc.) -- se traducen acá para que
            # la columna "Tipo" diga algo entendible sin tener que
            # adivinar. Para las detecciones, el "tipo" específico es
            # la severidad -- eso es lo que distingue una alerta de
            # otra, no el hecho genérico de que sea una "detección".
            EVENT_LABELS = {
                "file_created": "Archivo creado",
                "file_modified": "Archivo modificado",
                "file_deleted": "Archivo eliminado",
                "file_renamed": "Archivo renombrado / movido",
            }

            SEVERITY_TYPE_LABELS = {
                "CRITICAL": "Detección crítica",
                "HIGH": "Detección alta",
                "SUSPICIOUS": "Detección sospechosa",
            }

            activity_feed = []

            for row in cursor.fetchall():

                kind, sev, raw_label, hostname, ts, file_path = row

                if kind == "alert":
                    type_label = SEVERITY_TYPE_LABELS.get(sev, "Detección")
                    description = raw_label  # el título de la alerta
                else:
                    type_label = EVENT_LABELS.get(raw_label, raw_label)
                    # Para eventos, el "tipo" ya dice qué pasó (p. ej.
                    # "Archivo modificado") -- la descripción entonces
                    # es dónde pasó, no repetir qué pasó.
                    description = file_path or type_label

                activity_feed.append({
                    "kind": kind,
                    "severity": sev,
                    "type_label": type_label,
                    "description": description,
                    "hostname": hostname,
                    "ts": ts,
                    "file_path": file_path
                })

            # --- Estado del servidor: la comunicación con agentes se
            # infiere de si alguno mandó heartbeat hace poco. La BD y
            # la API ya están "probadas" con solo haber llegado hasta
            # acá sin excepción. No reportamos "motor de detección"
            # porque ese corre en el agente, no en el servidor -- no
            # tenemos forma honesta de verlo desde acá. ---

            cursor.execute(
                """
                SELECT COUNT(*) FROM agents
                WHERE last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes';
                """
            )
            agents_communicating = cursor.fetchone()[0]

            # --- Riesgo global numérico: el peor risk_score entre las
            # alertas todavía abiertas. Es un dato real (lo calcula
            # agent/heuristic_engine.py -- calculate_score(), combos
            # posibles 0/30/60/90), a diferencia de 'overall_risk' que
            # es la etiqueta categórica (CRÍTICO/ALTO/...). Mostramos
            # las dos: la etiqueta para el color, el número para el
            # detalle. ---

            cursor.execute(
                "SELECT COALESCE(MAX(risk_score), 0) FROM alerts WHERE status = 'NEW';"
            )
            global_risk_score = cursor.fetchone()[0]

            # --- Motor heurístico: estado real de cada regla. No hay
            # motor de umbrales ni ejecución automática todavía --
            # 'auto_isolate' se muestra tal cual está en la base (hoy
            # FALSE en las dos), sin insinuar que algo lo ejecuta. ---

            cursor.execute(
                """
                SELECT name, threshold, window_seconds, severity,
                       auto_isolate, is_active
                FROM heuristic_rules
                ORDER BY id;
                """
            )
            heuristic_rule_rows = cursor.fetchall()

            # --- Vectores de amenaza: desglose por regla de las
            # alertas abiertas (mismo criterio de "abiertas" que el
            # resto del dashboard). Reutiliza el mismo cálculo de
            # pct/dash_offset que la dona de riesgo. ---

            cursor.execute(
                """
                SELECT heuristic_rules.name, COUNT(*) AS n
                FROM alerts
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                WHERE alerts.status = 'NEW'
                GROUP BY heuristic_rules.name
                ORDER BY n DESC;
                """
            )
            vector_rows = cursor.fetchall()

            # --- Telemetría últimas 24h: volumen de eventos por hora.
            # Se completan las horas sin actividad con 0 -- si no, el
            # gráfico saltearía huecos y parecería que el tiempo no
            # pasó. ---

            cursor.execute(
                """
                SELECT date_trunc('hour', detected_at) AS hour, COUNT(*)
                FROM events
                WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour;
                """
            )
            telemetry_rows = dict(cursor.fetchall())

    finally:
        connection.close()

    vector_total = sum(n for _, n in vector_rows) if vector_rows else 0
    vector_cumulative = 0.0
    threat_vectors = []

    for rule_name, n in vector_rows:
        if rule_name is None:
            continue
        pct = round((n / vector_total * 100), 2) if vector_total else 0
        threat_vectors.append({
            "rule_name": rule_name,
            "rule_label": ALERT_RULE_LABELS_ES.get(rule_name, rule_name),
            "count": n,
            "pct": pct,
            "dash_offset": round(-vector_cumulative, 2),
            "color": "#3059d6" if rule_name == "mass_file_activity" else "#0d9488"
        })
        vector_cumulative += pct

    heuristic_rules_status = [
        {
            "name": row[0],
            "rule_label": ALERT_RULE_LABELS_ES.get(row[0], row[0]),
            "threshold": row[1],
            "window_seconds": row[2],
            "severity": row[3],
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(row[3], row[3]),
            "auto_isolate": row[4],
            "is_active": row[5]
        }
        for row in heuristic_rule_rows
    ]

    # Buckets de las últimas 24h, más viejo primero, para dibujar de
    # izquierda a derecha. 'now' se trunca a la hora para que el
    # bucket más nuevo coincida con lo que Postgres devolvió.
    now_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
    telemetry_buckets = []
    for i in range(23, -1, -1):
        bucket_time = now_hour - timedelta(hours=i)
        count = 0
        for ts, n in telemetry_rows.items():
            if ts.replace(minute=0, second=0, microsecond=0) == bucket_time:
                count = n
                break
        telemetry_buckets.append({"hour": bucket_time.strftime("%H:00"), "count": count})
    telemetry_max = max((b["count"] for b in telemetry_buckets), default=0) or 1

    summary = {
        "total_endpoints": total_endpoints,
        "connected_endpoints": connected_endpoints,
        "disconnected_endpoints": total_endpoints - connected_endpoints,
        "detections_24h": detections_24h,
        "incidents_active": incidents_active,
        "overall_risk": overall_risk,
        "critical_n": critical_n,
        "high_n": high_n,
        "suspicious_n": suspicious_n,
        "global_risk_score": global_risk_score,
        "incidents_investigating": incidents_investigating,
        "updated_at": datetime.now().strftime("%H:%M")
    }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "active_page": "dashboard",
            "db_ok": True,
            "summary": summary,
            "risk_distribution": risk_distribution,
            "risk_max": risk_max,
            "recent_alerts": recent_alerts,
            "top_risk_endpoints": top_risk_endpoints,
            "agents_ok": agents_ok,
            "agents_attention": agents_attention,
            "agents_offline": agents_offline,
            "last_heartbeat": last_heartbeat,
            "honeyfiles_total": honeyfiles_total,
            "honeyfile_activations_24h": honeyfile_activations_24h,
            "last_honeyfile": last_honeyfile,
            "incidents_active_count": incidents_active,
            "incident_severity": incident_severity,
            "response_pending": response_pending,
            "response_executed": response_executed,
            "response_failed": response_failed,
            "activity_feed": activity_feed,
            "agents_communicating": agents_communicating,
            "heuristic_rules_status": heuristic_rules_status,
            "threat_vectors": threat_vectors,
            "telemetry_buckets": telemetry_buckets,
            "telemetry_max": telemetry_max
        }
    )


ENDPOINT_CTE = """
    WITH endpoint_risk AS (
        SELECT alerts.agent_id,
               MAX(
                   CASE alerts.severity
                       WHEN 'CRITICAL' THEN 4
                       WHEN 'HIGH' THEN 3
                       WHEN 'SUSPICIOUS' THEN 2
                       ELSE 1
                   END
               ) AS risk_rank
        FROM alerts
        WHERE alerts.status = 'NEW'
        GROUP BY alerts.agent_id
    ),
    endpoint_data AS (
        SELECT agents.id, agents.hostname, agents.operating_system, agents.os_version,
               agents.architecture, agents.ip_address, agents.agent_version,
               agents.status, agents.last_seen_at, agents.enrolled_at,
               CASE
                   WHEN agents.status != 'ONLINE' THEN 'offline'
                   WHEN agents.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds' THEN 'ok'
                   ELSE 'attention'
               END AS status_bucket,
               CASE COALESCE(endpoint_risk.risk_rank, 1)
                   WHEN 4 THEN 'CRITICAL'
                   WHEN 3 THEN 'HIGH'
                   WHEN 2 THEN 'SUSPICIOUS'
                   ELSE 'NORMAL'
               END AS risk_bucket
        FROM agents
        LEFT JOIN endpoint_risk ON endpoint_risk.agent_id = agents.id
    )
""".format(stale_seconds=AGENT_STALE_SECONDS)

ENDPOINTS_PAGE_SIZE = 25

RISK_LABELS_ES = {"NORMAL": "Normal", "SUSPICIOUS": "Sospechoso", "HIGH": "Alto", "CRITICAL": "Crítico"}

# Únicos 4 tipos de evento que el agente realmente reporta hoy (vienen
# de watchdog: on_created/on_modified/on_deleted/on_moved). No existe
# "READ" -- watchdog no expone lectura de archivos, así que no lo
# ofrecemos como filtro para no sugerir un dato que no recolectamos.
EVENT_TYPE_LABELS_ES = {
    "file_created": "Archivo creado",
    "file_modified": "Archivo modificado",
    "file_deleted": "Archivo eliminado",
    "file_renamed": "Archivo renombrado / movido",
}

# Severidad real de 'alerts' -- LOW existe en el CHECK constraint pero
# el motor heurístico nunca lo produce (get_risk_level() solo devuelve
# NORMAL/SUSPICIOUS/HIGH/CRITICAL, y NORMAL nunca genera alerta). En
# la práctica solo aparecen estos 3.
ALERT_SEVERITY_LABELS_ES = {"SUSPICIOUS": "Sospechosa", "HIGH": "Alta", "CRITICAL": "Crítica"}

# Único par de reglas que el motor heurístico del agente implementa
# hoy (sembradas en schema_updates.sql sección 4).
ALERT_RULE_LABELS_ES = {
    "mass_file_activity": "Modificación masiva de archivos",
    "honeyfile_access": "Honeyfile activado",
}

# Los 5 valores reales del CHECK constraint chk_alerts_status. El
# mapeo a "estado gestionable" (Nueva/En investigación/Confirmada/
# Cerrada/Falso positivo) es una decisión de producto, no algo que
# venga dado -- se ancla a estos 5 nombres para no inventar un sexto.
ALERT_STATUS_LABELS_ES = {
    "NEW": "Nueva",
    "ACKNOWLEDGED": "En investigación",
    "ESCALATED": "Confirmada",
    "CLOSED": "Cerrada",
    "FALSE_POSITIVE": "Falso positivo",
}

# Los 4 valores reales del CHECK constraint chk_incidents_status.
# "CONTAINED" significa que ya se tomaron las acciones necesarias y el
# incidente está bajo control -- no que se confirmó que era
# ransomware. Esa determinación es aparte (ver INCIDENT_CLASSIFICATION_LABELS_ES).
INCIDENT_STATUS_LABELS_ES = {
    "OPEN": "Abierto",
    "IN_PROGRESS": "En investigación",
    "CONTAINED": "Contenido",
    "CLOSED": "Cerrado",
}

# Clasificación del resultado de la investigación -- separada del
# estado a propósito, para no mezclar "en qué etapa del ciclo de vida
# está" con "qué se determinó que era". Valores fijados por el CHECK
# constraint chk_incidents_classification (schema_updates.sql sección 8).
INCIDENT_CLASSIFICATION_LABELS_ES = {
    "CONFIRMED": "Confirmado",
    "POSSIBLE_THREAT": "Posible amenaza",
    "FALSE_POSITIVE": "Falso positivo",
    "LEGITIMATE_ACTIVITY": "Actividad legítima",
    "UNDETERMINED": "No determinado",
}

# A diferencia de Eventos/Detecciones (15m/1h/24h, pensado para
# actividad reciente), acá se usan ventanas más largas porque un
# incidente puede seguir abierto días. Son intervalos relativos a
# AHORA, no días de calendario -- "Hoy" sería engañoso si en realidad
# filtra "últimas 24 horas" contadas desde este instante.
INCIDENTES_SINCE_OPTIONS = {
    "24h": ("Últimas 24 horas", "24 hours"),
    "7d": ("Últimos 7 días", "7 days"),
    "30d": ("Últimos 30 días", "30 days"),
}


@app.get("/endpoints")
def endpoints_page(
    request: Request,
    status: str = Query(""),
    risk: str = Query(""),
    search: str = Query(""),
    os_filter: str = Query("", alias="os"),
    page: int = Query(1, ge=1)
):
    """Inventario operativo de endpoints -- a propósito, esta vista NO
    mezcla severidad de amenazas con el estado de conexión (por eso
    conectividad usa En línea/Advertencia/Desconectado, en azul, y
    riesgo usa Normal/Sospechoso/Alto/Crítico, en su propia paleta).
    Son dos preguntas distintas: ¿está funcionando el agente? y
    ¿tiene este endpoint algo de qué preocuparse ahora mismo?"""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    status = status if status in ("ok", "attention", "offline") else ""
    risk = risk if risk in ("NORMAL", "SUSPICIOUS", "HIGH", "CRITICAL") else ""

    where_clauses = []
    params = {}

    if status:
        where_clauses.append("status_bucket = %(status)s")
        params["status"] = status

    if risk:
        where_clauses.append("risk_bucket = %(risk)s")
        params["risk"] = risk

    if search:
        where_clauses.append(
            "(hostname ILIKE %(search)s OR host(ip_address) ILIKE %(search)s OR CAST(id AS TEXT) ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    if os_filter:
        where_clauses.append("operating_system = %(os)s")
        params["os"] = os_filter

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Totales globales -- sin filtrar, para las 4 tarjetas de
            # resumen. Si filtráramos esto también, las tarjetas
            # cambiarían con la búsqueda y dejarían de responder
            # "¿cuántos endpoints hay en total?".
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'ONLINE' AND last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds') AS ok_n,
                    COUNT(*) FILTER (WHERE status = 'ONLINE' AND (last_seen_at IS NULL OR last_seen_at < CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds')) AS attention_n,
                    COUNT(*) FILTER (WHERE status != 'ONLINE') AS offline_n,
                    COUNT(*) AS total_n
                FROM agents;
                """.format(stale_seconds=AGENT_STALE_SECONDS)
            )
            endpoints_ok, endpoints_attention, endpoints_offline, total_endpoints = cursor.fetchone()

            cursor.execute(
                "SELECT COUNT(DISTINCT agent_id) FROM alerts WHERE status = 'NEW';"
            )
            endpoints_with_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT DISTINCT operating_system FROM agents ORDER BY operating_system;")
            distinct_os = [row[0] for row in cursor.fetchall()]

            count_params = dict(params)
            cursor.execute(ENDPOINT_CTE + f"SELECT COUNT(*) FROM endpoint_data {where_sql};", count_params)
            filtered_total = cursor.fetchone()[0]

            total_pages = max(1, -(-filtered_total // ENDPOINTS_PAGE_SIZE))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * ENDPOINTS_PAGE_SIZE

            page_params = dict(params)
            page_params["limit"] = ENDPOINTS_PAGE_SIZE
            page_params["offset"] = offset

            cursor.execute(
                ENDPOINT_CTE + f"""
                SELECT * FROM endpoint_data
                {where_sql}
                ORDER BY id DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            rows = cursor.fetchall()

    finally:
        connection.close()

    endpoints = [
        {
            "id": row[0],
            "agent_code": f"AGT-{row[0]:06d}",
            "hostname": row[1],
            "operating_system": row[2],
            "os_version": row[3],
            "architecture": row[4],
            "ip_address": row[5],
            "agent_version": row[6],
            "status": row[7],
            "last_seen_at": row[8],
            "enrolled_at": row[9],
            "status_bucket": row[10],
            "risk_bucket": row[11],
            "risk_label": RISK_LABELS_ES[row[11]]
        }
        for row in rows
    ]

    # Query strings ya armados para no hacer concatenación de texto en
    # la plantilla -- cada link (chips de estado, paginación) sale de
    # acá, listo para usar.
    base_filters = {k: v for k, v in {"search": search, "os": os_filter, "risk": risk}.items() if v}

    filter_qs = urlencode({**base_filters, **({"status": status} if status else {})})
    qs_all = urlencode(base_filters)
    qs_ok = urlencode({**base_filters, "status": "ok"})
    qs_attention = urlencode({**base_filters, "status": "attention"})
    qs_offline = urlencode({**base_filters, "status": "offline"})

    return templates.TemplateResponse(
        request,
        "endpoints.html",
        {
            "user": user,
            "active_page": "endpoints",
            "endpoints": endpoints,
            "total_endpoints": total_endpoints,
            "endpoints_ok": endpoints_ok,
            "endpoints_attention": endpoints_attention,
            "endpoints_offline": endpoints_offline,
            "endpoints_with_alerts": endpoints_with_alerts,
            "distinct_os": distinct_os,
            "risk_options": [("NORMAL", "Normal"), ("SUSPICIOUS", "Sospechoso"), ("HIGH", "Alto"), ("CRITICAL", "Crítico")],
            "current_status": status,
            "current_risk": risk,
            "current_search": search,
            "current_os": os_filter,
            "filter_qs": filter_qs,
            "qs_all": qs_all,
            "qs_ok": qs_ok,
            "qs_attention": qs_attention,
            "qs_offline": qs_offline,
            "current_page": current_page,
            "total_pages": total_pages,
            "filtered_total": filtered_total
        }
    )


@app.get("/endpoints/{agent_id}")
def endpoint_detail_page(agent_id: int, request: Request):
    """Detalle de un endpoint puntual. Todo lo que se muestra acá sale
    de datos reales -- donde el agente todavía no reporta algo (p. ej.
    monitoreo de procesos), se dice explícitamente en vez de simular
    un estado 'funcionando' que no podemos verificar."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT id, hostname, operating_system, os_version, architecture,
                       ip_address, agent_version, status, last_seen_at, enrolled_at
                FROM agents
                WHERE id = %s;
                """,
                (agent_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Endpoint no encontrado")

            (endpoint_id, hostname, operating_system, os_version, architecture,
             ip_address, agent_version, status, last_seen_at, enrolled_at) = row

            if status != "ONLINE":
                status_bucket = "offline"
            elif last_seen_at and (datetime.now() - last_seen_at).total_seconds() <= AGENT_STALE_SECONDS:
                status_bucket = "ok"
            else:
                status_bucket = "attention"

            # Monitoreo de archivos: no tenemos un "heartbeat" propio
            # del watcher de archivos, así que la mejor señal honesta
            # es si alguna vez llegó un evento de este agente.
            cursor.execute(
                "SELECT MAX(detected_at) FROM events WHERE agent_id = %s;",
                (agent_id,)
            )
            last_file_event = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM honeyfiles WHERE agent_id = %s;",
                (agent_id,)
            )
            honeyfiles_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE agent_id = %s AND status = 'NEW';",
                (agent_id,)
            )
            active_detections = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM incidents WHERE agent_id = %s;",
                (agent_id,)
            )
            associated_incidents = cursor.fetchone()[0]

            # Riesgo actual del endpoint -- misma regla que la lista de
            # Endpoints y que "Endpoints con mayor riesgo" del dashboard:
            # el nivel más alto entre sus alertas abiertas, o Normal si
            # no tiene ninguna.
            cursor.execute(
                """
                SELECT MAX(
                    CASE severity
                        WHEN 'CRITICAL' THEN 4
                        WHEN 'HIGH' THEN 3
                        WHEN 'SUSPICIOUS' THEN 2
                        ELSE 1
                    END
                )
                FROM alerts
                WHERE agent_id = %s AND status = 'NEW';
                """,
                (agent_id,)
            )
            risk_rank_row = cursor.fetchone()[0]
            risk_bucket = {4: "CRITICAL", 3: "HIGH", 2: "SUSPICIOUS"}.get(risk_rank_row, "NORMAL")

            cursor.execute(
                """
                SELECT severity, title, created_at
                FROM alerts
                WHERE agent_id = %s
                ORDER BY created_at DESC
                LIMIT 5;
                """,
                (agent_id,)
            )
            latest_detections = [
                {"severity": sev, "title": title, "created_at": ts}
                for sev, title, ts in cursor.fetchall()
            ]

            # Credencial del agente -- si nunca completó enrollment (no
            # debería pasar, pero por las dudas) is_active queda None y
            # lo mostramos como "Sin credencial" en vez de asumir activa.
            cursor.execute(
                "SELECT is_active FROM agent_credentials WHERE agent_id = %s;",
                (agent_id,)
            )
            credential_row = cursor.fetchone()
            credential_active = credential_row[0] if credential_row else None

            cursor.execute(
                """
                (
                    SELECT 'alert' AS kind, alerts.severity AS sev,
                           alerts.title AS label, alerts.created_at AS ts
                    FROM alerts
                    WHERE alerts.agent_id = %(agent_id)s
                    ORDER BY alerts.created_at DESC
                    LIMIT 8
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           events.event_type AS label, events.detected_at AS ts
                    FROM events
                    WHERE events.agent_id = %(agent_id)s
                    ORDER BY events.detected_at DESC
                    LIMIT 8
                )
                ORDER BY ts DESC
                LIMIT 8;
                """,
                {"agent_id": agent_id}
            )

            SEVERITY_TYPE_LABELS_LOCAL = {
                "CRITICAL": "Detección crítica",
                "HIGH": "Detección alta",
                "SUSPICIOUS": "Detección sospechosa",
            }

            recent_activity = []

            for kind, sev, raw_label, ts in cursor.fetchall():
                if kind == "alert":
                    type_label = SEVERITY_TYPE_LABELS_LOCAL.get(sev, "Detección")
                else:
                    type_label = EVENT_TYPE_LABELS_ES.get(raw_label, raw_label)
                recent_activity.append({
                    "kind": kind, "severity": sev, "type_label": type_label,
                    "label": raw_label if kind == "alert" else type_label, "ts": ts
                })

    finally:
        connection.close()

    monitoring = [
        {
            "label": "Comunicación con el servidor (heartbeat)",
            "state": status_bucket,
            "detail": (
                f"Último heartbeat {time_ago(last_seen_at)}" if last_seen_at
                else "Todavía no se ha recibido un heartbeat"
            )
        },
        {
            "label": "Monitoreo de archivos",
            "state": "ok" if last_file_event else "unknown",
            "detail": (
                f"Última actividad {time_ago(last_file_event)}" if last_file_event
                else "Sin actividad registrada todavía"
            )
        },
        {
            "label": "Honeyfiles",
            "state": "ok" if honeyfiles_count > 0 else "unknown",
            "detail": (
                f"{honeyfiles_count} honeyfile(s) registrados" if honeyfiles_count > 0
                else "Sin honeyfiles registrados para este endpoint"
            )
        },
        {
            "label": "Monitoreo de procesos",
            "state": "not_implemented",
            "detail": "El agente todavía no envía esta información al servidor"
        },
    ]

    endpoint = {
        "id": endpoint_id,
        "agent_code": f"AGT-{endpoint_id:06d}",
        "hostname": hostname,
        "operating_system": operating_system,
        "os_version": os_version,
        "architecture": architecture,
        "ip_address": ip_address,
        "agent_version": agent_version,
        "status": status,
        "status_bucket": status_bucket,
        "last_seen_at": last_seen_at,
        "enrolled_at": enrolled_at,
        "risk_bucket": risk_bucket,
        "risk_label": RISK_LABELS_ES[risk_bucket],
        "credential_active": credential_active
    }

    return templates.TemplateResponse(
        request,
        "endpoint_detail.html",
        {
            "user": user,
            "active_page": "endpoints",
            "e": endpoint,
            "monitoring": monitoring,
            "active_detections": active_detections,
            "associated_incidents": associated_incidents,
            "honeyfiles_count": honeyfiles_count,
            "latest_detections": latest_detections,
            "recent_activity": recent_activity
        }
    )


EVENTOS_PAGE_SIZE = 50

EVENTOS_SINCE_OPTIONS = {
    "15m": ("Últimos 15 minutos", "15 minutes"),
    "1h": ("Última hora", "1 hour"),
    "24h": ("Últimas 24 horas", "24 hours"),
}


def _event_file_path(metadata):
    """metadata es el JSONB de la tabla events -- hoy solo lo llena
    file_monitor.py con {file_path, extension}. Puede venir como dict
    (psycopg lo adapta solo) o, si algún día cambia el driver, como
    string -- por las dudas lo manejamos de las dos formas en vez de
    asumir."""
    if not metadata:
        return None
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return None
    return metadata.get("file_path") if isinstance(metadata, dict) else None


@app.get("/eventos")
def eventos_page(
    request: Request,
    agent_id: int | None = Query(None),
    type_filter: str = Query("", alias="type"),
    since: str = Query(""),
    search: str = Query(""),
    alert_id: int | None = Query(None),
    page: int = Query(1, ge=1)
):
    """Registro técnico de lo que reportan los agentes -- 'ocurrió
    esto, acá, a esta hora'. A propósito NO incluye proceso/PID (el
    agente todavía no los reporta -- ver file_monitor.py) ni un juicio
    de severidad (eso es trabajo de Detecciones)."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    type_filter = type_filter if type_filter in EVENT_TYPE_LABELS_ES else ""
    since = since if since in EVENTOS_SINCE_OPTIONS else ""

    where_clauses = []
    params = {}

    if agent_id:
        where_clauses.append("events.agent_id = %(agent_id)s")
        params["agent_id"] = agent_id

    if alert_id:
        where_clauses.append(
            "events.id IN (SELECT event_id FROM alert_events WHERE alert_id = %(alert_id)s)"
        )
        params["alert_id"] = alert_id

    if type_filter:
        where_clauses.append("events.event_type = %(type)s")
        params["type"] = type_filter

    if since:
        where_clauses.append(
            "events.detected_at >= CURRENT_TIMESTAMP - INTERVAL %(since_interval)s"
        )
        params["since_interval"] = EVENTOS_SINCE_OPTIONS[since][1]

    if search:
        where_clauses.append(
            "(events.description ILIKE %(search)s OR agents.hostname ILIKE %(search)s "
            "OR (events.metadata->>'file_path') ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Tarjetas de resumen -- siempre globales (sin filtrar),
            # igual criterio que Endpoints: si cambiaran con la
            # búsqueda dejarían de responder "cuánto hay en total".
            cursor.execute("SELECT COUNT(*) FROM events;")
            total_events = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes';"
            )
            events_last_5min = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT agent_id) FROM events;")
            endpoints_with_activity = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE event_type = 'file_renamed' "
                "AND detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';"
            )
            renamed_24h = cursor.fetchone()[0]

            cursor.execute("SELECT id, hostname FROM agents ORDER BY hostname;")
            endpoint_options = cursor.fetchall()

            count_params = dict(params)
            cursor.execute(
                f"SELECT COUNT(*) FROM events JOIN agents ON agents.id = events.agent_id {where_sql};",
                count_params
            )
            filtered_total = cursor.fetchone()[0]

            total_pages = max(1, -(-filtered_total // EVENTOS_PAGE_SIZE))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * EVENTOS_PAGE_SIZE

            page_params = dict(params)
            page_params["limit"] = EVENTOS_PAGE_SIZE
            page_params["offset"] = offset

            cursor.execute(
                f"""
                SELECT events.id, events.event_type, events.description,
                       events.metadata, agents.hostname, events.agent_id,
                       events.detected_at
                FROM events
                JOIN agents ON agents.id = events.agent_id
                {where_sql}
                ORDER BY events.id DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            rows = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute("SELECT hostname FROM agents WHERE id = %s;", (agent_id,))
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    events = [
        {
            "id": row[0],
            "event_code": f"EVT-{row[0]:06d}",
            "event_type": row[1],
            "type_label": EVENT_TYPE_LABELS_ES.get(row[1], row[1]),
            "description": row[2],
            "file_path": _event_file_path(row[3]),
            "hostname": row[4],
            "agent_id": row[5],
            "detected_at": row[6]
        }
        for row in rows
    ]

    base_filters = {k: v for k, v in {
        "agent_id": agent_id, "type": type_filter, "since": since, "search": search, "alert_id": alert_id
    }.items() if v}
    filter_qs = urlencode(base_filters)

    return templates.TemplateResponse(
        request,
        "eventos.html",
        {
            "user": user,
            "active_page": "eventos",
            "events": events,
            "total_events": total_events,
            "events_last_5min": events_last_5min,
            "endpoints_with_activity": endpoints_with_activity,
            "renamed_24h": renamed_24h,
            "endpoint_options": endpoint_options,
            "event_type_options": EVENT_TYPE_LABELS_ES,
            "since_options": EVENTOS_SINCE_OPTIONS,
            "current_type": type_filter,
            "current_since": since,
            "current_search": search,
            "filter_qs": filter_qs,
            "current_page": current_page,
            "total_pages": total_pages,
            "filtered_total": filtered_total,
            "filtered_agent_id": agent_id,
            "filtered_hostname": filtered_hostname
        }
    )


@app.get("/eventos/{event_id}")
def evento_detail_page(event_id: int, request: Request):

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT events.id, events.event_type, events.description,
                       events.metadata, agents.id, agents.hostname,
                       agents.operating_system, agents.status, agents.last_seen_at,
                       events.detected_at
                FROM events
                JOIN agents ON agents.id = events.agent_id
                WHERE events.id = %s;
                """,
                (event_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Evento no encontrado")

            (evt_id, event_type, description, metadata, agent_id, hostname,
             operating_system, agent_status, last_seen_at, detected_at) = row

            if agent_status != "ONLINE":
                agent_status_bucket = "offline"
            elif last_seen_at and (datetime.now() - last_seen_at).total_seconds() <= AGENT_STALE_SECONDS:
                agent_status_bucket = "ok"
            else:
                agent_status_bucket = "attention"

            # Lookup inverso: ¿este evento participó en alguna alerta?
            # Un evento puede en teoría estar en más de una (dos
            # ventanas de análisis distintas se lo pisan), pero
            # mostramos la más reciente -- es la que importa para
            # investigar.
            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title, alerts.status
                FROM alert_events
                JOIN alerts ON alerts.id = alert_events.alert_id
                WHERE alert_events.event_id = %s
                ORDER BY alerts.created_at DESC
                LIMIT 1;
                """,
                (event_id,)
            )

            related_alert_row = cursor.fetchone()

    finally:
        connection.close()

    related_alert = None
    if related_alert_row:
        related_alert = {
            "id": related_alert_row[0],
            "severity": related_alert_row[1],
            "title": related_alert_row[2],
            "status": related_alert_row[3]
        }

    metadata_parsed = metadata if isinstance(metadata, dict) else {}

    event = {
        "id": evt_id,
        "event_code": f"EVT-{evt_id:06d}",
        "event_type": event_type,
        "type_label": EVENT_TYPE_LABELS_ES.get(event_type, event_type),
        "description": description,
        "file_path": metadata_parsed.get("file_path"),
        "extension": metadata_parsed.get("extension"),
        "detected_at": detected_at,
        "agent_id": agent_id,
        "agent_code": f"AGT-{agent_id:06d}",
        "hostname": hostname,
        "operating_system": operating_system,
        "agent_status_bucket": agent_status_bucket
    }

    return templates.TemplateResponse(
        request,
        "evento_detail.html",
        {
            "user": user,
            "active_page": "eventos",
            "evt": event,
            "related_alert": related_alert
        }
    )


@app.get("/honeyfiles")
def honeyfiles_page(request: Request, agent_id: int | None = Query(None)):

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if agent_id:
                cursor.execute(
                    """
                    SELECT honeyfiles.id, honeyfiles.file_name, honeyfiles.file_path,
                           honeyfiles.file_type, agents.hostname, honeyfiles.status,
                           honeyfiles.last_checked_at
                    FROM honeyfiles
                    JOIN agents ON agents.id = honeyfiles.agent_id
                    WHERE honeyfiles.agent_id = %s
                    ORDER BY honeyfiles.id DESC;
                    """,
                    (agent_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT honeyfiles.id, honeyfiles.file_name, honeyfiles.file_path,
                           honeyfiles.file_type, agents.hostname, honeyfiles.status,
                           honeyfiles.last_checked_at
                    FROM honeyfiles
                    JOIN agents ON agents.id = honeyfiles.agent_id
                    ORDER BY honeyfiles.id DESC;
                    """
                )

            honeyfiles = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute("SELECT hostname FROM agents WHERE id = %s;", (agent_id,))
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    return templates.TemplateResponse(
        request,
        "honeyfiles.html",
        {
            "user": user,
            "active_page": "honeyfiles",
            "honeyfiles": honeyfiles,
            "filtered_agent_id": agent_id,
            "filtered_hostname": filtered_hostname
        }
    )


DETECCIONES_PAGE_SIZE = 50


@app.get("/detecciones")
def detecciones_page(
    request: Request,
    agent_id: int | None = Query(None),
    severity: str = Query(""),
    status: str = Query(""),
    rule: str = Query(""),
    since: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1)
):
    """Lista de detecciones (alertas). Los filtros de severidad/regla
    solo ofrecen los valores que el motor heurístico realmente puede
    producir hoy -- 3 severidades, 2 reglas -- para no sugerir
    categorías que no existen."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    severity = severity if severity in ALERT_SEVERITY_LABELS_ES else ""
    status = status if status in ALERT_STATUS_LABELS_ES else ""
    rule = rule if rule in ALERT_RULE_LABELS_ES else ""
    since = since if since in EVENTOS_SINCE_OPTIONS else ""

    where_clauses = []
    params = {}

    if agent_id:
        where_clauses.append("alerts.agent_id = %(agent_id)s")
        params["agent_id"] = agent_id

    if severity:
        where_clauses.append("alerts.severity = %(severity)s")
        params["severity"] = severity

    if status:
        where_clauses.append("alerts.status = %(status)s")
        params["status"] = status

    if rule:
        where_clauses.append("heuristic_rules.name = %(rule)s")
        params["rule"] = rule

    if since:
        where_clauses.append(
            "alerts.created_at >= CURRENT_TIMESTAMP - INTERVAL %(since_interval)s"
        )
        params["since_interval"] = EVENTOS_SINCE_OPTIONS[since][1]

    if search:
        where_clauses.append(
            "(alerts.title ILIKE %(search)s OR agents.hostname ILIKE %(search)s "
            "OR CAST(alerts.id AS TEXT) ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Tarjetas de resumen -- globales, sin filtrar (mismo
            # criterio que Endpoints/Eventos).
            cursor.execute("SELECT COUNT(*) FROM alerts;")
            total_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'CRITICAL';")
            critical_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'HIGH';")
            high_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'NEW';")
            pending_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT id, hostname FROM agents ORDER BY hostname;")
            endpoint_options = cursor.fetchall()

            count_params = dict(params)
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                {where_sql};
                """,
                count_params
            )
            filtered_total = cursor.fetchone()[0]

            total_pages = max(1, -(-filtered_total // DETECCIONES_PAGE_SIZE))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * DETECCIONES_PAGE_SIZE

            page_params = dict(params)
            page_params["limit"] = DETECCIONES_PAGE_SIZE
            page_params["offset"] = offset

            cursor.execute(
                f"""
                SELECT alerts.id, alerts.severity, alerts.title, alerts.risk_score,
                       heuristic_rules.name, agents.hostname, alerts.status,
                       alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                {where_sql}
                ORDER BY alerts.id DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            alert_rows = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute("SELECT hostname FROM agents WHERE id = %s;", (agent_id,))
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    alerts = [
        {
            "id": row[0],
            "severity": row[1],
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(row[1], row[1]),
            "title": row[2],
            "risk_score": row[3],
            "rule_name": row[4],
            "rule_label": ALERT_RULE_LABELS_ES.get(row[4], row[4] or "—"),
            "hostname": row[5],
            "status": row[6],
            "status_label": ALERT_STATUS_LABELS_ES.get(row[6], row[6]),
            "created_at": row[7]
        }
        for row in alert_rows
    ]

    base_filters = {k: v for k, v in {
        "agent_id": agent_id, "severity": severity, "status": status,
        "rule": rule, "since": since, "search": search
    }.items() if v}
    filter_qs = urlencode(base_filters)

    return templates.TemplateResponse(
        request,
        "detecciones.html",
        {
            "user": user,
            "active_page": "detecciones",
            "alerts": alerts,
            "total_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "high_alerts": high_alerts,
            "pending_alerts": pending_alerts,
            "endpoint_options": endpoint_options,
            "severity_options": ALERT_SEVERITY_LABELS_ES,
            "status_options": ALERT_STATUS_LABELS_ES,
            "rule_options": ALERT_RULE_LABELS_ES,
            "since_options": EVENTOS_SINCE_OPTIONS,
            "current_severity": severity,
            "current_status": status,
            "current_rule": rule,
            "current_since": since,
            "current_search": search,
            "filter_qs": filter_qs,
            "current_page": current_page,
            "total_pages": total_pages,
            "filtered_total": filtered_total,
            "filtered_agent_id": agent_id,
            "filtered_hostname": filtered_hostname
        }
    )


@app.get("/usuarios")
def usuarios_page(request: Request):

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT users.id, users.username, users.full_name, users.email,
                       STRING_AGG(roles.name, ', ' ORDER BY roles.name) AS roles,
                       users.is_active, users.last_login_at, users.created_at
                FROM users
                LEFT JOIN user_roles ON user_roles.user_id = users.id
                LEFT JOIN roles ON roles.id = user_roles.role_id
                GROUP BY users.id
                ORDER BY users.id;
                """
            )

            users = cursor.fetchall()

    finally:
        connection.close()

    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {"user": user, "active_page": "usuarios", "users": users}
    )


@app.get("/alerts/open")
def alerts_open(user: dict = Depends(get_current_user)):
    """JSON liviano para la campanita de notificaciones -- se consulta
    solo, sin pasar por cada ruta de página. Trae las alertas todavía
    sin revisar (status = 'NEW'), sin importar la severidad: hasta las
    NORMAL/LOW quedan fuera porque esas ni siquiera generan alerta
    (el agente solo llama a send_alert cuando is_suspicious() es
    True)."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title,
                       agents.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                WHERE alerts.status = 'NEW'
                ORDER BY alerts.created_at DESC
                LIMIT 10;
                """
            )

            rows = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE status = 'NEW';"
            )

            total = cursor.fetchone()[0]

    finally:
        connection.close()

    return {
        "count": total,
        "alerts": [
            {
                "id": row[0],
                "severity": row[1],
                "title": row[2],
                "hostname": row[3],
                "created_at": row[4].strftime("%d/%m %H:%M")
            }
            for row in rows
        ]
    }


@app.get("/dashboard/live")
def dashboard_live(user: dict = Depends(get_current_user)):
    """JSON liviano para el polling del dashboard (cada 15s, ver
    dashboard.html). No es tiempo real de verdad -- no hay websockets
    ni push desde el agente -- es el navegador volviendo a preguntar
    cada tantos segundos. Solo trae lo que tiene sentido que cambie
    seguido (tarjetas de resumen + feed); el motor heurístico y la
    lista de endpoints son más de configuración/inventario y se
    quedan como estaban hasta que se recargue la página entera."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT COUNT(*) FROM agents WHERE status = 'ONLINE';")
            connected_endpoints = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';"
            )
            detections_24h = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'OPEN';")
            incidents_active = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT alerts.severity, COUNT(DISTINCT alerts.agent_id)
                FROM alerts WHERE alerts.status = 'NEW'
                GROUP BY alerts.severity;
                """
            )
            severity_rows = dict(cursor.fetchall())
            critical_n = severity_rows.get("CRITICAL", 0)
            high_n = severity_rows.get("HIGH", 0)
            suspicious_n = severity_rows.get("SUSPICIOUS", 0)

            if critical_n > 0:
                overall_risk = "CRÍTICO"
            elif high_n > 0:
                overall_risk = "ALTO"
            elif suspicious_n > 0:
                overall_risk = "SOSPECHOSO"
            else:
                overall_risk = "NORMAL"

            cursor.execute("SELECT COALESCE(MAX(risk_score), 0) FROM alerts WHERE status = 'NEW';")
            global_risk_score = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title,
                       agents.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                WHERE alerts.status = 'NEW'
                ORDER BY alerts.created_at DESC
                LIMIT 6;
                """
            )
            recent_alerts = [
                {
                    "id": r[0], "severity": r[1], "title": r[2],
                    "hostname": r[3], "created_at": r[4].strftime("%d/%m %H:%M"),
                    "ago": time_ago(r[4])
                }
                for r in cursor.fetchall()
            ]

            cursor.execute(
                """
                (
                    SELECT 'alert' AS kind, alerts.severity AS sev,
                           alerts.title AS label, agents.hostname AS hostname,
                           alerts.created_at AS ts,
                           alerts.details->>'last_file' AS file_path
                    FROM alerts
                    JOIN agents ON agents.id = alerts.agent_id
                    ORDER BY alerts.created_at DESC
                    LIMIT 15
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           events.event_type AS label, agents.hostname AS hostname,
                           events.detected_at AS ts,
                           events.metadata->>'file_path' AS file_path
                    FROM events
                    JOIN agents ON agents.id = events.agent_id
                    ORDER BY events.detected_at DESC
                    LIMIT 15
                )
                ORDER BY ts DESC
                LIMIT 15;
                """
            )

            EVENT_LABELS = {
                "file_created": "Archivo creado",
                "file_modified": "Archivo modificado",
                "file_deleted": "Archivo eliminado",
                "file_renamed": "Archivo renombrado / movido",
            }
            SEVERITY_TYPE_LABELS = {
                "CRITICAL": "Detección crítica",
                "HIGH": "Detección alta",
                "SUSPICIOUS": "Detección sospechosa",
            }

            activity_feed = []
            for row in cursor.fetchall():
                kind, sev, raw_label, hostname, ts, file_path = row
                if kind == "alert":
                    type_label = SEVERITY_TYPE_LABELS.get(sev, "Detección")
                    description = raw_label
                else:
                    type_label = EVENT_LABELS.get(raw_label, raw_label)
                    description = file_path or type_label
                activity_feed.append({
                    "kind": kind, "severity": sev, "type_label": type_label,
                    "description": description, "hostname": hostname,
                    "ago": time_ago(ts), "file_path": file_path
                })

    finally:
        connection.close()

    return {
        "connected_endpoints": connected_endpoints,
        "detections_24h": detections_24h,
        "incidents_active": incidents_active,
        "overall_risk": overall_risk,
        "critical_n": critical_n,
        "high_n": high_n,
        "global_risk_score": global_risk_score,
        "updated_at": datetime.now().strftime("%H:%M"),
        "recent_alerts": recent_alerts,
        "activity_feed": activity_feed
    }


@app.get("/detecciones/{alert_id}")
def deteccion_detail_page(alert_id: int, request: Request):
    """Vista de una alerta puntual (lo que en el mockup del usuario
    aparece como 'DET-00042'). Muestra solo lo que realmente
    guardamos: no inventamos proceso/PID porque el agente todavía no
    correla eventos con el proceso responsable (tarea pendiente)."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title, alerts.description,
                       alerts.risk_score, alerts.status, alerts.created_at, alerts.details,
                       agents.id, agents.hostname, agents.operating_system,
                       heuristic_rules.name
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                WHERE alerts.id = %s;
                """,
                (alert_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            cursor.execute(
                "SELECT id FROM incidents WHERE alert_id = %s;",
                (alert_id,)
            )

            existing_incident = cursor.fetchone()

            cursor.execute(
                """
                SELECT events.id, events.event_type, events.metadata, events.detected_at
                FROM alert_events
                JOIN events ON events.id = alert_events.event_id
                WHERE alert_events.alert_id = %s
                ORDER BY events.detected_at DESC
                LIMIT 10;
                """,
                (alert_id,)
            )

            related_event_rows = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) FROM alert_events WHERE alert_id = %s;",
                (alert_id,)
            )

            related_events_total = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT alert_notes.id, alert_notes.note, alert_notes.created_at,
                       users.full_name
                FROM alert_notes
                JOIN users ON users.id = alert_notes.user_id
                WHERE alert_notes.alert_id = %s
                ORDER BY alert_notes.created_at DESC;
                """,
                (alert_id,)
            )

            note_rows = cursor.fetchall()

            # Honeyfile relacionado -- no hay un FK real entre alerts y
            # honeyfiles, así que esto es un cruce por ruta de archivo:
            # si el 'último archivo' que guardó la alerta coincide con
            # la ruta de un honeyfile registrado para este mismo
            # agente, lo mostramos. Es una coincidencia, no una
            # relación garantizada por la base de datos.
            details_data = row[7] or {}
            last_file = details_data.get("last_file") if isinstance(details_data, dict) else None

            related_honeyfile = None

            if last_file:
                cursor.execute(
                    """
                    SELECT id, file_name, file_path, status
                    FROM honeyfiles
                    WHERE agent_id = %s AND file_path = %s
                    LIMIT 1;
                    """,
                    (row[8], last_file)
                )
                hf_row = cursor.fetchone()
                if hf_row:
                    related_honeyfile = {
                        "id": hf_row[0], "file_name": hf_row[1],
                        "file_path": hf_row[2], "status": hf_row[3]
                    }

    finally:
        connection.close()

    notes = [
        {"id": n[0], "note": n[1], "created_at": n[2], "author": n[3]}
        for n in note_rows
    ]

    related_events = [
        {
            "id": r[0],
            "event_code": f"EVT-{r[0]:06d}",
            "type_label": EVENT_TYPE_LABELS_ES.get(r[1], r[1]),
            "file_path": _event_file_path(r[2]),
            "detected_at": r[3]
        }
        for r in related_event_rows
    ]

    detection = {
        "id": row[0],
        "severity": row[1],
        "severity_label": ALERT_SEVERITY_LABELS_ES.get(row[1], row[1]),
        "title": row[2],
        "description": row[3],
        "risk_score": row[4],
        "status": row[5],
        "status_label": ALERT_STATUS_LABELS_ES.get(row[5], row[5]),
        "created_at": row[6],
        "details": row[7] or {},
        "agent_id": row[8],
        "hostname": row[9],
        "operating_system": row[10],
        "rule_name": row[11],
        "rule_label": ALERT_RULE_LABELS_ES.get(row[11], row[11] or "—"),
        "is_honeyfile": row[11] == "honeyfile_access"
    }

    return templates.TemplateResponse(
        request,
        "deteccion_detail.html",
        {
            "user": user,
            "active_page": "detecciones",
            "d": detection,
            "existing_incident_id": existing_incident[0] if existing_incident else None,
            "related_events": related_events,
            "related_events_total": related_events_total,
            "related_honeyfile": related_honeyfile,
            "notes": notes,
            "status_options": ALERT_STATUS_LABELS_ES
        }
    )


@app.post("/incidents")
def create_incident(
    incident: IncidentCreate,
    user: dict = Depends(get_current_user)
):
    """Escala una detección a incidente. Si ya existe un incidente
    para esa alerta, no duplica -- devuelve el que ya había. La
    detección que dispara el incidente queda como 'alert_id' (para
    saber cuál lo originó) y además se vincula en 'incident_alerts'
    (la lista completa de detecciones del caso, que puede crecer
    después con POST /incidents/{id}/alerts)."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id FROM incidents WHERE alert_id = %s;",
                (incident.alert_id,)
            )

            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    INSERT INTO incident_alerts (incident_id, alert_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (existing[0], incident.alert_id)
                )
                connection.commit()
                return {
                    "message": "Ya existía un incidente para esta alerta",
                    "incident_id": existing[0]
                }

            cursor.execute(
                """
                SELECT alerts.agent_id, alerts.title, alerts.description
                FROM alerts WHERE alerts.id = %s;
                """,
                (incident.alert_id,)
            )

            alert_row = cursor.fetchone()

            if alert_row is None:
                raise HTTPException(status_code=404, detail="Alerta no encontrada")

            agent_id, title, description = alert_row

            cursor.execute(
                """
                INSERT INTO incidents (
                    alert_id, agent_id, title, description, classification
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (incident.alert_id, agent_id, title, description, incident.classification)
            )

            incident_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO incident_alerts (incident_id, alert_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (incident_id, incident.alert_id)
            )

            connection.commit()

        return {
            "message": "Incidente creado",
            "incident_id": incident_id
        }

    finally:
        connection.close()


@app.post("/incidents/{incident_id}/alerts")
def link_incident_alert(
    incident_id: int,
    payload: IncidentAlertLink,
    user: dict = Depends(get_current_user)
):
    """Vincula una detección adicional a un incidente ya existente --
    esto es lo que permite que un incidente agrupe varias detecciones
    relacionadas, en vez de quedarse 1 a 1 con la que lo originó."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT id FROM incidents WHERE id = %s;", (incident_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            cursor.execute("SELECT id FROM alerts WHERE id = %s;", (payload.alert_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            cursor.execute(
                """
                INSERT INTO incident_alerts (incident_id, alert_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (incident_id, payload.alert_id)
            )

            linked = cursor.fetchone()

            cursor.execute(
                "UPDATE incidents SET updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                (incident_id,)
            )

            connection.commit()

        return {
            "message": "Detección vinculada" if linked else "La detección ya estaba vinculada a este incidente",
            "incident_id": incident_id,
            "alert_id": payload.alert_id
        }

    finally:
        connection.close()


@app.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    user: dict = Depends(get_current_user)
):
    """Cambia el estado del incidente (Abierto -> En investigación ->
    Contenido -> Cerrado). Al cerrar, se registra cuándo y quién --
    si se reabre después, esos campos se limpian para no dejar un
    'cerrado por' fantasma en un incidente que ya no está cerrado."""

    if payload.status not in INCIDENT_STATUS_LABELS_ES:
        raise HTTPException(status_code=422, detail="Estado inválido")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if payload.status == "CLOSED":
                cursor.execute(
                    """
                    UPDATE incidents
                    SET status = %s, updated_at = CURRENT_TIMESTAMP,
                        closed_at = CURRENT_TIMESTAMP, closed_by = %s
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (payload.status, user["id"], incident_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE incidents
                    SET status = %s, updated_at = CURRENT_TIMESTAMP,
                        closed_at = NULL, closed_by = NULL
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (payload.status, incident_id)
                )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            connection.commit()

        return {
            "message": "Estado actualizado",
            "incident_id": incident_id,
            "status": payload.status,
            "status_label": INCIDENT_STATUS_LABELS_ES[payload.status]
        }

    finally:
        connection.close()


@app.patch("/incidents/{incident_id}/classification")
def update_incident_classification(
    incident_id: int,
    payload: IncidentClassify,
    user: dict = Depends(get_current_user)
):
    """Clasificación del resultado -- deliberadamente separada del
    estado (ver comentario de INCIDENT_CLASSIFICATION_LABELS_ES)."""

    if payload.classification not in INCIDENT_CLASSIFICATION_LABELS_ES:
        raise HTTPException(status_code=422, detail="Clasificación inválida")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE incidents
                SET classification = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id;
                """,
                (payload.classification, incident_id)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            connection.commit()

        return {
            "message": "Clasificación actualizada",
            "incident_id": incident_id,
            "classification": payload.classification,
            "classification_label": INCIDENT_CLASSIFICATION_LABELS_ES[payload.classification]
        }

    finally:
        connection.close()


@app.patch("/incidents/{incident_id}/assign")
def assign_incident(
    incident_id: int,
    payload: IncidentAssign,
    user: dict = Depends(get_current_user)
):
    """Asigna (o reasigna) un responsable real de la tabla 'users' --
    no un nombre libre, para que el vínculo se pueda seguir de
    verdad."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id, full_name FROM users WHERE id = %s AND is_active = TRUE;",
                (payload.user_id,)
            )
            target_user = cursor.fetchone()

            if target_user is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo")

            cursor.execute(
                """
                UPDATE incidents
                SET assigned_to = %s, assigned_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id;
                """,
                (payload.user_id, incident_id)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            connection.commit()

        return {
            "message": "Incidente asignado",
            "incident_id": incident_id,
            "assigned_to": target_user[0],
            "assigned_to_name": target_user[1]
        }

    finally:
        connection.close()


@app.patch("/incidents/{incident_id}/description")
def update_incident_description(
    incident_id: int,
    payload: IncidentDescriptionUpdate,
    user: dict = Depends(get_current_user)
):
    """El resumen inicial lo arma el sistema a partir de la alerta que
    disparó el incidente, pero el analista tiene que poder corregirlo
    o ampliarlo con lo que va encontrando."""

    description = payload.description.strip()

    if not description:
        raise HTTPException(status_code=422, detail="La descripción no puede estar vacía")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE incidents
                SET description = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id;
                """,
                (description, incident_id)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            connection.commit()

        return {"message": "Descripción actualizada", "incident_id": incident_id, "description": description}

    finally:
        connection.close()


@app.post("/incidents/{incident_id}/notes")
def create_incident_note(
    incident_id: int,
    payload: IncidentNoteCreate,
    user: dict = Depends(get_current_user)
):
    """Nota de analista sobre un incidente -- mismo patrón que
    alert_notes en Detecciones."""

    note_text = payload.note.strip()

    if not note_text:
        raise HTTPException(status_code=422, detail="La nota no puede estar vacía")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT id FROM incidents WHERE id = %s;", (incident_id,))

            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            cursor.execute(
                """
                INSERT INTO incident_notes (incident_id, user_id, note)
                VALUES (%s, %s, %s)
                RETURNING id, created_at;
                """,
                (incident_id, user["id"], note_text)
            )

            note_id, created_at = cursor.fetchone()

            cursor.execute(
                "UPDATE incidents SET updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                (incident_id,)
            )

            connection.commit()

        return {
            "message": "Nota agregada",
            "note": {
                "id": note_id,
                "note": note_text,
                "author": user.get("full_name", user.get("username", "—")),
                "created_at": created_at.strftime("%d/%m/%Y %H:%M")
            }
        }

    finally:
        connection.close()


@app.patch("/alerts/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    user: dict = Depends(get_current_user)
):
    """Cambia el estado de una detección. Antes de este endpoint,
    'alerts.status' se ponía en INSERT y no lo tocaba nada más -- toda
    alerta se quedaba en NEW para siempre. Esto es lo que hace real el
    ciclo de vida Nueva -> En investigación -> Confirmada/Falso
    positivo -> Cerrada."""

    if payload.status not in ALERT_STATUS_LABELS_ES:
        raise HTTPException(status_code=422, detail="Estado inválido")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "UPDATE alerts SET status = %s WHERE id = %s RETURNING id;",
                (payload.status, alert_id)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            connection.commit()

        return {
            "message": "Estado actualizado",
            "alert_id": alert_id,
            "status": payload.status,
            "status_label": ALERT_STATUS_LABELS_ES[payload.status]
        }

    finally:
        connection.close()


@app.post("/alerts/{alert_id}/notes")
def create_alert_note(
    alert_id: int,
    payload: AlertNoteCreate,
    user: dict = Depends(get_current_user)
):
    """Nota de analista sobre una detección puntual -- constancia de
    qué se investigó, en texto libre."""

    note_text = payload.note.strip()

    if not note_text:
        raise HTTPException(status_code=422, detail="La nota no puede estar vacía")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT id FROM alerts WHERE id = %s;", (alert_id,))

            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            cursor.execute(
                """
                INSERT INTO alert_notes (alert_id, user_id, note)
                VALUES (%s, %s, %s)
                RETURNING id, created_at;
                """,
                (alert_id, user["id"], note_text)
            )

            note_id, created_at = cursor.fetchone()

            connection.commit()

        return {
            "message": "Nota agregada",
            "note": {
                "id": note_id,
                "note": note_text,
                "author": user.get("full_name", user.get("username", "—")),
                "created_at": created_at.strftime("%d/%m/%Y %H:%M")
            }
        }

    finally:
        connection.close()


# 'severity' y 'detection_count' no son columnas de 'incidents' --
# se derivan de las detecciones vinculadas en 'incident_alerts'.
# 'severity' es la más alta entre esas detecciones (mismo criterio de
# "peor caso" que ya usa ENDPOINT_CTE para el riesgo de un endpoint).
# Se arma como CTE para poder filtrar/contar por estos valores
# derivados en cada consulta que lo necesite.
INCIDENT_CTE = """
    WITH incident_data AS (
        SELECT incidents.id, incidents.title, incidents.description,
               incidents.status, incidents.classification,
               incidents.opened_at, incidents.closed_at, incidents.updated_at,
               incidents.alert_id, incidents.agent_id, incidents.assigned_to,
               incidents.assigned_at, incidents.closed_by,
               agents.hostname,
               (
                   SELECT COUNT(*) FROM incident_alerts
                   WHERE incident_alerts.incident_id = incidents.id
               ) AS detection_count,
               (
                   SELECT alerts.severity FROM incident_alerts
                   JOIN alerts ON alerts.id = incident_alerts.alert_id
                   WHERE incident_alerts.incident_id = incidents.id
                   ORDER BY CASE alerts.severity
                       WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
                       WHEN 'SUSPICIOUS' THEN 2 ELSE 1
                   END DESC
                   LIMIT 1
               ) AS severity
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
    )
"""

INCIDENTES_PAGE_SIZE = 25


@app.get("/incidentes")
def incidentes_page(
    request: Request,
    agent_id: int | None = Query(None),
    status: str = Query(""),
    severity: str = Query(""),
    classification: str = Query(""),
    since: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1)
):
    """Lista de incidentes -- casos de seguridad armados a partir de
    una o varias detecciones relacionadas (ver incident_alerts).
    Deliberadamente no repite el detalle técnico de Detecciones: acá
    la pregunta es '¿qué caso estamos gestionando?', no '¿qué detectó
    el agente?'."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    status = status if status in INCIDENT_STATUS_LABELS_ES else ""
    severity = severity if severity in ALERT_SEVERITY_LABELS_ES else ""
    classification = classification if classification in INCIDENT_CLASSIFICATION_LABELS_ES else ""
    since = since if since in INCIDENTES_SINCE_OPTIONS else ""

    where_clauses = []
    params = {}

    if agent_id:
        where_clauses.append("agent_id = %(agent_id)s")
        params["agent_id"] = agent_id

    if status:
        where_clauses.append("status = %(status)s")
        params["status"] = status

    if severity:
        where_clauses.append("severity = %(severity)s")
        params["severity"] = severity

    if classification:
        where_clauses.append("classification = %(classification)s")
        params["classification"] = classification

    if since:
        where_clauses.append("opened_at >= CURRENT_TIMESTAMP - INTERVAL %(since_interval)s")
        params["since_interval"] = INCIDENTES_SINCE_OPTIONS[since][1]

    if search:
        where_clauses.append(
            "(title ILIKE %(search)s OR hostname ILIKE %(search)s OR CAST(id AS TEXT) ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Tarjetas de resumen -- globales, sin filtrar (mismo
            # criterio que Endpoints/Eventos/Detecciones).
            cursor.execute(INCIDENT_CTE + "SELECT COUNT(*) FROM incident_data;")
            total_incidents = cursor.fetchone()[0]

            cursor.execute(INCIDENT_CTE + "SELECT COUNT(*) FROM incident_data WHERE status != 'CLOSED';")
            open_incidents = cursor.fetchone()[0]

            cursor.execute(INCIDENT_CTE + "SELECT COUNT(*) FROM incident_data WHERE severity = 'CRITICAL';")
            critical_incidents = cursor.fetchone()[0]

            cursor.execute(INCIDENT_CTE + "SELECT COUNT(*) FROM incident_data WHERE status = 'IN_PROGRESS';")
            investigating_incidents = cursor.fetchone()[0]

            cursor.execute("SELECT id, hostname FROM agents ORDER BY hostname;")
            endpoint_options = cursor.fetchall()

            count_params = dict(params)
            cursor.execute(
                INCIDENT_CTE + f"SELECT COUNT(*) FROM incident_data {where_sql};",
                count_params
            )
            filtered_total = cursor.fetchone()[0]

            total_pages = max(1, -(-filtered_total // INCIDENTES_PAGE_SIZE))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * INCIDENTES_PAGE_SIZE

            page_params = dict(params)
            page_params["limit"] = INCIDENTES_PAGE_SIZE
            page_params["offset"] = offset

            cursor.execute(
                INCIDENT_CTE + f"""
                SELECT id, title, status, classification, opened_at, updated_at,
                       hostname, detection_count, severity
                FROM incident_data
                {where_sql}
                ORDER BY id DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            incident_rows = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute("SELECT hostname FROM agents WHERE id = %s;", (agent_id,))
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    incidents = [
        {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "status_label": INCIDENT_STATUS_LABELS_ES.get(row[2], row[2]),
            "classification": row[3],
            "classification_label": INCIDENT_CLASSIFICATION_LABELS_ES.get(row[3], "Sin clasificar"),
            "opened_at": row[4],
            "updated_at": row[5],
            "hostname": row[6],
            "detection_count": row[7],
            "severity": row[8],
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(row[8], row[8] or "—")
        }
        for row in incident_rows
    ]

    base_filters = {k: v for k, v in {
        "agent_id": agent_id, "status": status, "severity": severity,
        "classification": classification, "since": since, "search": search
    }.items() if v}
    filter_qs = urlencode(base_filters)

    return templates.TemplateResponse(
        request,
        "incidentes.html",
        {
            "user": user,
            "active_page": "incidentes",
            "incidents": incidents,
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "investigating_incidents": investigating_incidents,
            "endpoint_options": endpoint_options,
            "status_options": INCIDENT_STATUS_LABELS_ES,
            "severity_options": ALERT_SEVERITY_LABELS_ES,
            "classification_options": INCIDENT_CLASSIFICATION_LABELS_ES,
            "since_options": INCIDENTES_SINCE_OPTIONS,
            "current_status": status,
            "current_severity": severity,
            "current_classification": classification,
            "current_since": since,
            "current_search": search,
            "filter_qs": filter_qs,
            "current_page": current_page,
            "total_pages": total_pages,
            "filtered_total": filtered_total,
            "filtered_agent_id": agent_id,
            "filtered_hostname": filtered_hostname
        }
    )


@app.get("/incidentes/{incident_id}")
def incidente_detail_page(incident_id: int, request: Request):
    """Detalle de un incidente puntual. A propósito no repite el
    análisis heurístico de cada detección (eso ya está en /detecciones/{id})
    -- acá se muestra el caso: qué endpoint, qué detecciones lo
    integran, quién lo tiene asignado, y una línea de tiempo armada
    solo con marcas de tiempo reales (no se inventan pasos intermedios
    que la base no registra, como cambios de estado sin historial)."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                INCIDENT_CTE + "SELECT * FROM incident_data WHERE id = %s;",
                (incident_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            (inc_id, title, description, status, classification, opened_at, closed_at,
             updated_at, alert_id, agent_id, assigned_to, assigned_at, closed_by,
             hostname, detection_count, severity) = row

            cursor.execute(
                "SELECT operating_system, ip_address, status, last_seen_at FROM agents WHERE id = %s;",
                (agent_id,)
            )
            agent_row = cursor.fetchone()
            operating_system, ip_address, agent_status, last_seen_at = agent_row

            if agent_status != "ONLINE":
                agent_status_bucket = "offline"
            elif last_seen_at and (datetime.now() - last_seen_at).total_seconds() <= AGENT_STALE_SECONDS:
                agent_status_bucket = "ok"
            else:
                agent_status_bucket = "attention"

            assigned_to_name = None
            if assigned_to:
                cursor.execute("SELECT full_name FROM users WHERE id = %s;", (assigned_to,))
                assigned_row = cursor.fetchone()
                assigned_to_name = assigned_row[0] if assigned_row else None

            closed_by_name = None
            if closed_by:
                cursor.execute("SELECT full_name FROM users WHERE id = %s;", (closed_by,))
                closed_row = cursor.fetchone()
                closed_by_name = closed_row[0] if closed_row else None

            cursor.execute(
                """
                SELECT alerts.id, alerts.severity, alerts.title, alerts.status,
                       alerts.created_at, heuristic_rules.name, alerts.rule_id
                FROM incident_alerts
                JOIN alerts ON alerts.id = incident_alerts.alert_id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alerts.rule_id
                WHERE incident_alerts.incident_id = %s
                ORDER BY alerts.created_at ASC;
                """,
                (incident_id,)
            )

            linked_alert_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT alerts.id, alerts.title, alerts.severity, alerts.created_at
                FROM alerts
                WHERE alerts.agent_id = %s
                  AND alerts.id NOT IN (
                      SELECT alert_id FROM incident_alerts WHERE incident_id = %s
                  )
                ORDER BY alerts.created_at DESC
                LIMIT 20;
                """,
                (agent_id, incident_id)
            )

            linkable_alert_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT incident_notes.id, incident_notes.note, incident_notes.created_at,
                       users.full_name
                FROM incident_notes
                JOIN users ON users.id = incident_notes.user_id
                WHERE incident_notes.incident_id = %s
                ORDER BY incident_notes.created_at DESC;
                """,
                (incident_id,)
            )

            note_rows = cursor.fetchall()

            cursor.execute("SELECT id, full_name FROM users WHERE is_active = TRUE ORDER BY full_name;")
            assignable_users = cursor.fetchall()

    finally:
        connection.close()

    linked_detections = [
        {
            "id": r[0],
            "severity": r[1],
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(r[1], r[1]),
            "title": r[2],
            "status_label": ALERT_STATUS_LABELS_ES.get(r[3], r[3]),
            "created_at": r[4],
            "rule_label": ALERT_RULE_LABELS_ES.get(r[5], r[5] or "—"),
            "is_honeyfile": r[5] == "honeyfile_access"
        }
        for r in linked_alert_rows
    ]

    linkable_detections = [
        {
            "id": r[0], "title": r[1],
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(r[2], r[2]),
            "created_at": r[3]
        }
        for r in linkable_alert_rows
    ]

    notes = [
        {"id": n[0], "note": n[1], "created_at": n[2], "author": n[3]}
        for n in note_rows
    ]

    # Indicadores principales: combinaciones únicas de regla/severidad
    # entre las detecciones vinculadas -- no un análisis nuevo, solo un
    # resumen de lo que ya se ve en detalle en cada DET-XXXX.
    seen = set()
    indicators = []
    for det in linked_detections:
        key = (det["rule_label"], det["is_honeyfile"])
        if key not in seen:
            seen.add(key)
            indicators.append(det)

    # Línea temporal: solo hechos con marca de tiempo real en la base.
    # No se muestran pasos intermedios (p. ej. "pasó a Contenido") porque
    # no hay tabla de historial de estados todavía (ver PENDIENTES.md).
    timeline = []
    for det in linked_detections:
        timeline.append({
            "at": det["created_at"],
            "label": f"Detección generada: {det['rule_label']} (DET-{det['id']:05d})"
        })
    timeline.append({"at": opened_at, "label": f"Incidente INC-{inc_id:05d} creado"})
    if assigned_at:
        timeline.append({"at": assigned_at, "label": f"Incidente asignado a {assigned_to_name or 'usuario eliminado'}"})
    if closed_at:
        classification_label = INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "sin clasificar")
        timeline.append({"at": closed_at, "label": f"Incidente cerrado ({classification_label})"})
    timeline.sort(key=lambda item: item["at"])

    incident = {
        "id": inc_id,
        "title": title,
        "description": description,
        "status": status,
        "status_label": INCIDENT_STATUS_LABELS_ES.get(status, status),
        "classification": classification,
        "classification_label": INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "Sin clasificar"),
        "opened_at": opened_at,
        "closed_at": closed_at,
        "updated_at": updated_at,
        "alert_id": alert_id,
        "agent_id": agent_id,
        "hostname": hostname,
        "operating_system": operating_system,
        "ip_address": ip_address,
        "agent_status_bucket": agent_status_bucket,
        "assigned_to": assigned_to,
        "assigned_to_name": assigned_to_name,
        "assigned_at": assigned_at,
        "closed_by": closed_by,
        "closed_by_name": closed_by_name,
        "detection_count": detection_count,
        "severity": severity,
        "severity_label": ALERT_SEVERITY_LABELS_ES.get(severity, severity or "—")
    }

    return templates.TemplateResponse(
        request,
        "incidente_detail.html",
        {
            "user": user,
            "active_page": "incidentes",
            "inc": incident,
            "linked_detections": linked_detections,
            "linkable_detections": linkable_detections,
            "indicators": indicators,
            "timeline": timeline,
            "notes": notes,
            "assignable_users": assignable_users,
            "status_options": INCIDENT_STATUS_LABELS_ES,
            "classification_options": INCIDENT_CLASSIFICATION_LABELS_ES
        }
    )


@app.get("/procesos")
def procesos_page(request: Request):
    return render_placeholder(
        request,
        "procesos",
        "Procesos",
        "El agente ya lista los procesos en ejecución localmente (agent/process_monitor.py), "
        "pero todavía no envía esa información al servidor ni queda asociada a los eventos de "
        "archivos. Falta correlacionar cada evento con el proceso responsable (vía Visor de "
        "Eventos de Windows o auditd en Linux) antes de que esta vista pueda mostrar algo real."
    )


@app.get("/respuesta")
def respuesta_page(request: Request):
    return render_placeholder(
        request,
        "respuesta",
        "Respuesta",
        "El aislamiento de endpoints (tabla 'host_isolations') es parte del diseño del sistema, "
        "pero la respuesta automática todavía no está implementada. Por ahora la contención ante "
        "una detección crítica es manual, fuera de la consola."
    )


@app.get("/reportes")
def reportes_page(request: Request):
    return render_placeholder(
        request,
        "reportes",
        "Informes y reportes",
        "Todavía no hay generación de reportes (por ejemplo, un resumen semanal de detecciones "
        "por endpoint, o exportar incidentes a PDF/Excel). Es un buen candidato para más adelante, "
        "una vez que haya suficiente actividad real registrada."
    )


@app.get("/configuracion")
def configuracion_page(request: Request):
    return render_placeholder(
        request,
        "configuracion",
        "Configuración",
        "Aquí iría, por ejemplo, ajustar los umbrales de las reglas heurísticas "
        "(heuristic_rules) desde la consola en vez de por SQL directo. Hoy esos valores solo se "
        "pueden cambiar a mano en la base de datos."
    )


@app.post("/agents")
def register_agent(agent: AgentCreate):

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO agents (
                    hostname,
                    operating_system,
                    os_version,
                    architecture,
                    ip_address,
                    agent_version
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent.hostname,
                    agent.operating_system,
                    agent.os_version,
                    agent.architecture,
                    agent.ip_address,
                    agent.agent_version
                )
            )

            agent_id = cursor.fetchone()[0]

            connection.commit()

        return {
            "message": "Agente registrado correctamente",
            "agent_id": agent_id
        }

    finally:
        connection.close()


@app.post("/enrollment-tokens")
def create_enrollment_token(
    user: dict = Depends(require_role("admin"))
):
    # Antes esto recibía "created_by" como un número suelto en la URL
    # -- cualquiera que supiera la ruta podía generar tokens a nombre
    # de cualquier usuario, sin loguearse. Ahora exige sesión con rol
    # 'admin', y el id sale de la sesión, no de lo que mande quien
    # llama.
    created_by = user["id"]

    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO enrollment_tokens (
                    token_hash,
                    created_by,
                    expires_at
                )
                VALUES (
                    %s,
                    %s,
                    CURRENT_TIMESTAMP + INTERVAL '15 minutes'
                )
                RETURNING id, expires_at;
                """,
                (
                    token_hash,
                    created_by
                )
            )

            result = cursor.fetchone()

            connection.commit()

        return {
            "message": "Token de enrollment creado",
            "token": token,
            "token_id": result[0],
            "expires_at": result[1]
        }

    finally:
        connection.close()


@app.post("/enrollment")
def enroll_agent(enrollment: EnrollmentRequest):

    token_hash = hashlib.sha256(
        enrollment.token.encode()
    ).hexdigest()

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # 1. Buscar el token
            cursor.execute(
                """
                SELECT id
                FROM enrollment_tokens
                WHERE token_hash = %s
                  AND is_active = TRUE
                  AND used_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP;
                """,
                (token_hash,)
            )

            token_record = cursor.fetchone()

            if token_record is None:
                raise HTTPException(
                    status_code=401,
                    detail="Token de enrollment inválido o expirado"
                )

            token_id = token_record[0]

            # 2. Registrar el agente
            cursor.execute(
                """
                INSERT INTO agents (
                    hostname,
                    operating_system,
                    os_version,
                    architecture,
                    ip_address,
                    agent_version
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    enrollment.hostname,
                    enrollment.operating_system,
                    enrollment.os_version,
                    enrollment.architecture,
                    enrollment.ip_address,
                    enrollment.agent_version
                )
            )

            agent_id = cursor.fetchone()[0]

            # 3. Generar credencial del agente
            credential = secrets.token_urlsafe(32)

            credential_hash = hashlib.sha256(
                credential.encode()
            ).hexdigest()

            cursor.execute(
                """
                INSERT INTO agent_credentials (
                    agent_id,
                    credential_hash
                )
                VALUES (%s, %s);
                """,
                (
                    agent_id,
                    credential_hash
                )
            )

            # 4. Marcar el token como utilizado
            cursor.execute(
                """
                UPDATE enrollment_tokens
                SET used_at = CURRENT_TIMESTAMP,
                    is_active = FALSE
                WHERE id = %s;
                """,
                (token_id,)
            )

            connection.commit()

        return {
            "message": "Agente registrado correctamente",
            "agent_id": agent_id,
            "credential": credential
        }

    finally:
        connection.close()


@app.get("/agent/test")
def test_agent(x_agent_credential: str = Header(...)):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            agent_id = resolve_agent_id(cursor, x_agent_credential)

            return {
                "message": "Agente autenticado correctamente",
                "agent_id": agent_id
            }

    finally:

        connection.close()


@app.post("/agent/heartbeat")
def agent_heartbeat(x_agent_credential: str = Header(...)):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            agent_id = resolve_agent_id(cursor, x_agent_credential)

            cursor.execute(
                """
                UPDATE agents
                SET last_seen_at = CURRENT_TIMESTAMP,
                    status = 'ONLINE'
                WHERE id = %s;
                """,
                (agent_id,)
            )

            connection.commit()

            return {
                "message": "Heartbeat recibido",
                "agent_id": agent_id
            }

    finally:
        connection.close()


@app.post("/agent/events")
def report_event(
    event: EventCreate,
    x_agent_credential: str = Header(...)
):
    """Recibe eventos crudos del monitor de archivos/procesos del
    agente (tabla 'events')."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            agent_id = resolve_agent_id(cursor, x_agent_credential)

            cursor.execute(
                """
                INSERT INTO events (
                    agent_id,
                    event_type,
                    description,
                    process_id,
                    process_name,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent_id,
                    event.event_type,
                    event.description,
                    event.process_id,
                    event.process_name,
                    json.dumps(event.metadata) if event.metadata else None
                )
            )

            event_id = cursor.fetchone()[0]

            connection.commit()

        return {
            "message": "Evento registrado",
            "event_id": event_id
        }

    finally:
        connection.close()


@app.post("/agent/alerts")
def report_alert(
    alert: AlertCreate,
    x_agent_credential: str = Header(...)
):
    """Recibe alertas ya evaluadas por el motor heurístico del agente
    y las persiste en 'alerts', enlazándolas a la regla de
    'heuristic_rules' cuando el nombre coincide."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            agent_id = resolve_agent_id(cursor, x_agent_credential)

            rule_id = None

            if alert.rule_name:

                cursor.execute(
                    """
                    SELECT id FROM heuristic_rules
                    WHERE name = %s AND is_active = TRUE;
                    """,
                    (alert.rule_name,)
                )

                rule_row = cursor.fetchone()

                if rule_row:
                    rule_id = rule_row[0]

            cursor.execute(
                """
                INSERT INTO alerts (
                    agent_id,
                    rule_id,
                    severity,
                    title,
                    description,
                    risk_score,
                    details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent_id,
                    rule_id,
                    alert.severity,
                    alert.title,
                    alert.description,
                    alert.risk_score,
                    json.dumps(alert.details) if alert.details else None
                )
            )

            alert_id = cursor.fetchone()[0]

            # Vincular la alerta a los eventos que la dispararon. El
            # WHERE agent_id = %s es a propósito -- evita que un agente
            # (con su credencial válida) pueda vincular su alerta a
            # eventos de OTRO agente mandando IDs ajenos.
            if alert.event_ids:
                cursor.execute(
                    """
                    INSERT INTO alert_events (alert_id, event_id)
                    SELECT %s, events.id
                    FROM events
                    WHERE events.id = ANY(%s) AND events.agent_id = %s
                    ON CONFLICT (alert_id, event_id) DO NOTHING;
                    """,
                    (alert_id, alert.event_ids, agent_id)
                )

            connection.commit()

        return {
            "message": "Alerta registrada",
            "alert_id": alert_id
        }

    finally:
        connection.close()
