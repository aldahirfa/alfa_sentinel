import os

from fastapi import FastAPI, HTTPException, Header, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, Response
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
import csv
import io
from datetime import datetime, timedelta
from urllib.parse import urlencode

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

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

    seconds = int((datetime.now(value.tzinfo) - value).total_seconds())

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
# una vez al arrancar (no hay bucle automático todavía), así que este
# umbral es generoso a propósito.
#
# Este valor era una constante fija hasta el 2026-08-12; ahora vive en
# 'system_settings' (key 'agent_stale_seconds') y es editable de
# verdad desde /configuracion -- get_agent_stale_seconds() lo lee de
# la base en cada request. Esta constante queda solo como default de
# emergencia si la fila no existiera todavía (base vieja sin migrar).
AGENT_STALE_SECONDS_DEFAULT = 120


def get_system_setting(cursor, key, default=None, cast=str):
    """Lee un valor de 'system_settings'. Devuelve 'default' si la
    fila no existe o si el valor guardado no se puede convertir con
    'cast' -- nunca revienta la página por un dato de configuración
    mal cargado a mano."""

    cursor.execute("SELECT value FROM system_settings WHERE key = %s;", (key,))
    row = cursor.fetchone()

    if row is None:
        return default

    try:
        return cast(row[0])
    except (TypeError, ValueError):
        return default


def get_agent_stale_seconds(cursor):
    """Reemplaza a la vieja constante AGENT_STALE_SECONDS -- único
    parámetro de 'Configuración > Agentes' que el servidor realmente
    vuelve a leer después de guardarlo."""

    return get_system_setting(cursor, "agent_stale_seconds", default=AGENT_STALE_SECONDS_DEFAULT, cast=int)


def log_audit(cursor, user_id, action, entity_type=None, entity_id=None, description=None):
    """Bitácora de auditoría real (2026-08-12) -- antes 'audit_logs'
    existía en el schema pero ningún endpoint escribía ahí. Se llama
    justo antes del commit() de cada mutación relevante, con el mismo
    cursor y la misma transacción que el cambio que registra: si el
    cambio se revierte por un error después, el log también (no queda
    una entrada de auditoría de algo que en realidad no se guardó).
    'ip_address' se deja NULL -- no todos los endpoints que mutan
    datos tienen 'Request' en su firma hoy, y agregarlo a todos para
    esto solo hubiera agrandado el alcance de este cambio."""

    cursor.execute(
        """
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, description)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (user_id, action, entity_type, entity_id, description)
    )


# Sirve server/static/* en /static/* -- ahí vive el logo (logo-icon.png,
# logo-full.png).
app.mount("/static", StaticFiles(directory="static"), name="static")


class AgentCreate(BaseModel):
    hostname: str
    os: str
    os_version: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None

class EnrollmentRequest(BaseModel):
    token: str
    hostname: str
    os: str
    os_version: str | None = None
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


class IncidentAlertLink(BaseModel):
    alert_id: int


class IncidentAssign(BaseModel):
    user_id: int | None = None


class IncidentStatusUpdate(BaseModel):
    status: str


class IncidentClassify(BaseModel):
    classification: str


class IncidentDescriptionUpdate(BaseModel):
    description: str


class RuleUpdate(BaseModel):
    weight: float | None = None
    is_active: bool | None = None
    threshold: float | None = None
    window_seconds: int | None = None


class ReportGenerate(BaseModel):
    report_type: str
    period: str
    format: str
    endpoint_id: int | None = None


class SettingUpdate(BaseModel):
    value: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    role: str | None = None


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
          AND status = 'ACTIVE';
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

            log_audit(
                cursor, current_user["id"], "CREATE_USER", "users", user_id,
                f"{new_user.username} ({new_user.role})"
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


@app.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: dict = Depends(require_role("admin"))
):
    """Editar/desactivar un usuario (2026-08-12) -- hasta ahora
    'POST /users' solo permitía crear, no había forma de corregir un
    dato o desactivar una cuenta sin ir directo a la base. Mismo nivel
    de acceso que crear usuarios (solo admin), consistente con que
    'GET /usuarios' hoy no lo exige (gap ya documentado en
    PENDIENTES.md) -- este endpoint sí lo exige porque escribe."""

    if payload.full_name is None and payload.email is None and payload.is_active is None and payload.role is None:
        raise HTTPException(status_code=422, detail="Nada para actualizar")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT username FROM users WHERE id = %s;", (user_id,))
            existing = cursor.fetchone()

            if existing is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            fields = []
            values = []
            change_parts = []

            if payload.full_name is not None:
                fields.append("full_name = %s")
                values.append(payload.full_name)
                change_parts.append(f"nombre -> {payload.full_name}")

            if payload.email is not None:
                fields.append("email = %s")
                values.append(payload.email)
                change_parts.append(f"email -> {payload.email}")

            if payload.is_active is not None:
                fields.append("is_active = %s")
                values.append(payload.is_active)
                change_parts.append(f"activo -> {payload.is_active}")

            if fields:
                fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(user_id)

                cursor.execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE id = %s;",
                    values
                )

            if payload.role is not None:

                cursor.execute("SELECT id FROM roles WHERE name = %s;", (payload.role,))
                role_row = cursor.fetchone()

                if role_row:
                    role_id = role_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO roles (name, description) VALUES (%s, %s) RETURNING id;",
                        (payload.role, f"Rol '{payload.role}'")
                    )
                    role_id = cursor.fetchone()[0]

                # Reemplaza los roles existentes en vez de sumarlos --
                # hoy la UI solo maneja "un rol por usuario" (mismo
                # criterio que POST /users), no roles múltiples.
                cursor.execute("DELETE FROM user_roles WHERE user_id = %s;", (user_id,))
                cursor.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s);",
                    (user_id, role_id)
                )
                change_parts.append(f"rol -> {payload.role}")

            log_audit(
                cursor, current_user["id"], "UPDATE_USER", "users", user_id,
                f"{existing[0]}: {', '.join(change_parts)}" if change_parts else existing[0]
            )

            connection.commit()

        return {"message": "Usuario actualizado", "user_id": user_id}

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
                SELECT severity_levels.name, COUNT(DISTINCT alerts.agent_id) AS n
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.status = 'NEW'
                GROUP BY severity_levels.name;
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
                SELECT alerts.id, severity_levels.name, alerts.title,
                       endpoints.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.status = 'NEW'
                ORDER BY alerts.created_at DESC
                LIMIT 6;
                """
            )
            recent_alerts = cursor.fetchall()

            # --- Endpoints con mayor riesgo ---

            cursor.execute(
                """
                SELECT agents.id, endpoints.hostname, agents.status, endpoints.ip_address,
                       MAX(
                           CASE severity_levels.name
                               WHEN 'CRITICAL' THEN 4
                               WHEN 'HIGH' THEN 3
                               WHEN 'SUSPICIOUS' THEN 2
                               ELSE 1
                           END
                       ) AS risk_rank,
                       COUNT(*) AS detection_count
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.status = 'NEW'
                GROUP BY agents.id, endpoints.hostname, agents.status, endpoints.ip_address
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

            stale_seconds = get_agent_stale_seconds(cursor)

            agents_ok = 0
            agents_attention = 0
            agents_offline = 0
            last_heartbeat = None

            for status, last_seen_at in agent_rows:

                if last_seen_at and (last_heartbeat is None or last_seen_at > last_heartbeat):
                    last_heartbeat = last_seen_at

                if status != "ONLINE":
                    agents_offline += 1
                elif last_seen_at and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() <= stale_seconds:
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
                JOIN alert_rule ON alert_rule.alert_id = alerts.id
                JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE heuristic_rules.name = 'honeyfile_access'
                  AND alerts.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
                """
            )
            honeyfile_activations_24h = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT endpoints.hostname, alerts.created_at
                FROM alerts
                JOIN alert_rule ON alert_rule.alert_id = alerts.id
                JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
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
                SELECT severity_levels.name, COUNT(*)
                FROM incidents
                JOIN alerts ON alerts.incident_id = incidents.id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE incidents.status = 'OPEN'
                GROUP BY severity_levels.name;
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
                    SELECT 'alert' AS kind, severity_levels.name AS sev,
                           alerts.title AS label, endpoints.hostname AS hostname,
                           alerts.created_at AS ts,
                           NULL AS file_path
                    FROM alerts
                    JOIN agents ON agents.id = alerts.agent_id
                    JOIN endpoints ON endpoints.id = agents.endpoint_id
                    JOIN severity_levels ON severity_levels.id = alerts.severity_id
                    ORDER BY alerts.created_at DESC
                    LIMIT 15
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           event_types.name AS label, endpoints.hostname AS hostname,
                           events.detected_at AS ts,
                           events.file_path AS file_path
                    FROM events
                    JOIN agents ON agents.id = events.agent_id
                    JOIN endpoints ON endpoints.id = agents.endpoint_id
                    JOIN event_types ON event_types.id = events.event_type_id
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

            # --- Motor heurístico: estado real de cada regla. La nueva
            # 'heuristic_rules' (alfa_sentinel) ya no tiene columnas
            # 'severity' ni 'auto_isolate' -- la severidad ahora es una
            # propiedad de la ALERTA (severity_id, según el score),
            # no de la regla que la disparó, y 'auto_isolate' no tenía
            # ningún código que lo leyera de todos modos. Se muestra
            # 'weight' en su lugar (el peso real que la regla aporta
            # al score cuando se cumple).

            cursor.execute(
                """
                SELECT name, threshold, window_seconds, weight, is_active
                FROM heuristic_rules
                ORDER BY id;
                """
            )
            heuristic_rule_rows = cursor.fetchall()

            # --- Vectores de amenaza: desglose por regla de las
            # alertas abiertas (mismo criterio de "abiertas" que el
            # resto del dashboard). 'alert_rule' reemplaza al viejo
            # 'alerts.rule_id'. Reutiliza el mismo cálculo de
            # pct/dash_offset que la dona de riesgo. ---

            cursor.execute(
                """
                SELECT heuristic_rules.name, COUNT(*) AS n
                FROM alerts
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
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
            "weight": row[3],
            "is_active": row[4]
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


def _endpoint_cte(stale_seconds):
    """Antes era el módulo-level 'ENDPOINT_CTE', formateado una sola
    vez al importar el módulo con la constante fija. Ahora es función
    porque 'stale_seconds' se lee de 'system_settings' en cada
    request (ver get_agent_stale_seconds) -- si quedara como string ya
    formateado al arrancar el proceso, cambiar el valor desde
    /configuracion no tendría efecto hasta reiniciar el servidor."""

    return """
    WITH endpoint_risk AS (
        SELECT alerts.agent_id,
               MAX(
                   CASE severity_levels.name
                       WHEN 'CRITICAL' THEN 4
                       WHEN 'HIGH' THEN 3
                       WHEN 'SUSPICIOUS' THEN 2
                       ELSE 1
                   END
               ) AS risk_rank
        FROM alerts
        JOIN severity_levels ON severity_levels.id = alerts.severity_id
        WHERE alerts.status = 'NEW'
        GROUP BY alerts.agent_id
    ),
    endpoint_data AS (
        SELECT agents.id, endpoints.hostname, endpoints.os AS operating_system, endpoints.os_version,
               endpoints.ip_address, agents.agent_version,
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
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        LEFT JOIN endpoint_risk ON endpoint_risk.agent_id = agents.id
    )
""".format(stale_seconds=stale_seconds)

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

# Reglas que el motor heurístico del agente implementa hoy (sembradas
# en database/schema.sql, sección de datos semilla). Las dos últimas
# se agregaron 2026-08-12 (agent/heuristic_engine.py).
ALERT_RULE_LABELS_ES = {
    "mass_file_activity": "Modificación masiva de archivos",
    "honeyfile_access": "Honeyfile activado",
    "ransomware_extension_rename": "Rename a extensión de ransomware",
    "mass_deletion": "Borrado masivo de archivos",
}

# La nueva 'alerts.status' (alfa_sentinel) es un VARCHAR sin CHECK
# constraint -- estos 5 valores ya no vienen impuestos por la base,
# los define este diccionario. El mapeo a "estado gestionable" (Nueva/
# En investigación/Confirmada/Cerrada/Falso positivo) sigue siendo una
# decisión de producto, no algo que venga dado.
ALERT_STATUS_LABELS_ES = {
    "NEW": "Nueva",
    "ACKNOWLEDGED": "En investigación",
    "ESCALATED": "Confirmada",
    "CLOSED": "Cerrada",
    "FALSE_POSITIVE": "Falso positivo",
}

# Igual que ALERT_STATUS_LABELS_ES: 'incidents.status' ya no tiene
# CHECK constraint en la base nueva, así que estos 4 valores los fija
# este diccionario. "CONTAINED" significa que ya se tomaron las
# acciones necesarias y el incidente está bajo control -- no que se
# confirmó que era ransomware. Esa determinación es aparte (ver
# INCIDENT_CLASSIFICATION_LABELS_ES).
INCIDENT_STATUS_LABELS_ES = {
    "OPEN": "Abierto",
    "IN_PROGRESS": "En investigación",
    "CONTAINED": "Contenido",
    "CLOSED": "Cerrado",
}

# Clasificación del resultado de la investigación -- separada del
# estado a propósito, para no mezclar "en qué etapa del ciclo de vida
# está" con "qué se determinó que era". Igual que status/rule: sin
# CHECK constraint en la base nueva, los valores los fija este
# diccionario.
INCIDENT_CLASSIFICATION_LABELS_ES = {
    "CONFIRMED": "Confirmado",
    "POSSIBLE_THREAT": "Posible amenaza",
    "FALSE_POSITIVE": "Falso positivo",
    "LEGITIMATE_ACTIVITY": "Actividad legítima",
    "UNDETERMINED": "No determinado",
}

# Página /reportes (2026-08-12). Solo 3 tipos -- cubren lo directivo
# (SECURITY), lo operativo (ENDPOINTS) e investigativo (INCIDENTS) sin
# inflar la interfaz. No hay generación automática/"por sistema"
# todavía: 'generated_by' siempre sale de la sesión de quien lo pide
# (ver PENDIENTES.md).
REPORT_TYPE_LABELS_ES = {
    "SECURITY": "Informe de Seguridad General",
    "ENDPOINTS": "Informe de Actividad de Endpoints",
    "INCIDENTS": "Informe de Incidentes",
}

REPORT_PERIOD_OPTIONS = [
    ("7d", "Últimos 7 días"),
    ("30d", "Últimos 30 días"),
    ("90d", "Últimos 90 días"),
    ("all", "Todo el histórico"),
]

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_reports")

REPORT_FORMAT_MEDIA_TYPES = {
    "PDF": "application/pdf",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _resolve_report_period(period: str):
    """Traduce el preset elegido en el formulario a un rango de fechas
    real. 'all' arranca en la fecha de creación de la base más vieja
    posible que tiene sentido acá (no hay datos de antes del propio
    proyecto), así que se usa una fecha fija bien anterior en vez de
    NULL, para no tener que ramificar el resto del código en "con
    filtro de fecha" / "sin filtro de fecha"."""

    now = datetime.now()

    if period == "7d":
        return now - timedelta(days=7), now, "Últimos 7 días"
    elif period == "30d":
        return now - timedelta(days=30), now, "Últimos 30 días"
    elif period == "90d":
        return now - timedelta(days=90), now, "Últimos 90 días"
    elif period == "all":
        return datetime(2000, 1, 1), now, "Todo el histórico"
    else:
        raise HTTPException(status_code=422, detail=f"Período desconocido: '{period}'")

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

            stale_seconds = get_agent_stale_seconds(cursor)

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
                """.format(stale_seconds=stale_seconds)
            )
            endpoints_ok, endpoints_attention, endpoints_offline, total_endpoints = cursor.fetchone()

            cursor.execute(
                "SELECT COUNT(DISTINCT agent_id) FROM alerts WHERE status = 'NEW';"
            )
            endpoints_with_alerts = cursor.fetchone()[0]

            # Equipos en Riesgo (Alto o Crítico)
            cursor.execute(
                _endpoint_cte(stale_seconds) + "SELECT COUNT(*) FROM endpoint_data WHERE risk_bucket IN ('HIGH', 'CRITICAL');"
            )
            endpoints_in_risk = cursor.fetchone()[0]

            # Equipos Aislados
            cursor.execute(
                "SELECT COUNT(DISTINCT agent_id) FROM host_isolations WHERE status IN ('REQUESTED', 'EXECUTED') AND released_at IS NULL;"
            )
            endpoints_isolated = cursor.fetchone()[0]

            # Set de IDs aislados
            cursor.execute(
                "SELECT DISTINCT agent_id FROM host_isolations WHERE status IN ('REQUESTED', 'EXECUTED') AND released_at IS NULL;"
            )
            isolated_agent_ids = {r[0] for r in cursor.fetchall()}

            cursor.execute("SELECT DISTINCT os FROM endpoints ORDER BY os;")
            distinct_os = [row[0] for row in cursor.fetchall()]

            count_params = dict(params)
            cursor.execute(_endpoint_cte(stale_seconds) + f"SELECT COUNT(*) FROM endpoint_data {where_sql};", count_params)
            filtered_total = cursor.fetchone()[0]

            total_pages = max(1, -(-filtered_total // ENDPOINTS_PAGE_SIZE))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * ENDPOINTS_PAGE_SIZE

            page_params = dict(params)
            page_params["limit"] = ENDPOINTS_PAGE_SIZE
            page_params["offset"] = offset

            cursor.execute(
                _endpoint_cte(stale_seconds) + f"""
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

    risk_score_map = {"NORMAL": 0, "SUSPICIOUS": 35, "HIGH": 65, "CRITICAL": 85}

    # Orden real de columnas de ENDPOINT_CTE.endpoint_data (ya no
    # incluye 'architecture' -- 'endpoints' no tiene esa columna):
    # id, hostname, operating_system, os_version, ip_address,
    # agent_version, status, last_seen_at, enrolled_at, status_bucket,
    # risk_bucket.
    endpoints = [
        {
            "id": row[0],
            "agent_code": f"AGT-{row[0]:06d}",
            "hostname": row[1],
            "operating_system": row[2],
            "os_version": row[3],
            "ip_address": str(row[4]) if row[4] else "127.0.0.1",
            "agent_version": row[5] or "v1.0.0",
            "status": row[6],
            "last_seen_at": row[7],
            "enrolled_at": row[8],
            "status_bucket": row[9],
            "risk_bucket": row[10],
            "risk_label": RISK_LABELS_ES[row[10]],
            "risk_score": risk_score_map.get(row[10], 0),
            "is_isolated": row[0] in isolated_agent_ids,
            "is_live": (row[9] == "ok" and row[7] is not None)
        }
        for row in rows
    ]

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
            "endpoints_in_risk": endpoints_in_risk,
            "endpoints_isolated": endpoints_isolated,
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


@app.get("/api/endpoints/{agent_id}/drawer")
def get_endpoint_drawer_data(agent_id: int, request: Request):
    """API para obtener la información completa del Host Drawer (panel lateral)."""
    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT agents.id, endpoints.hostname, endpoints.os, endpoints.os_version,
                       endpoints.ip_address, agents.agent_version, agents.status,
                       agents.last_seen_at, agents.enrolled_at
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )
            row = cursor.fetchone()
            if not row:
                return JSONResponse({"error": "Endpoint no encontrado"}, status_code=404)

            # Nivel de riesgo
            cursor.execute(
                """
                SELECT severity_levels.name FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.agent_id = %s AND alerts.status = 'NEW'
                ORDER BY CASE severity_levels.name WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'SUSPICIOUS' THEN 2 ELSE 1 END DESC
                LIMIT 1;
                """,
                (agent_id,)
            )
            risk_row = cursor.fetchone()
            risk_bucket = risk_row[0] if risk_row else "NORMAL"
            risk_scores = {"NORMAL": 0, "SUSPICIOUS": 35, "HIGH": 65, "CRITICAL": 85}

            # Aislamiento activo -- hoy siempre va a dar "no aislado":
            # ningún endpoint del servidor escribe en host_isolations
            # (ver nota de honestidad más abajo, en el botón del drawer).
            cursor.execute(
                """
                SELECT id, status FROM host_isolations
                WHERE agent_id = %s AND status IN ('REQUESTED', 'EXECUTED') AND released_at IS NULL
                ORDER BY id DESC LIMIT 1;
                """,
                (agent_id,)
            )
            iso_row = cursor.fetchone()
            is_isolated = iso_row is not None

            # Honeyfiles en este host
            cursor.execute(
                "SELECT COUNT(*) FROM honeyfiles WHERE agent_id = %s;",
                (agent_id,)
            )
            honeyfiles_total = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT file_path FROM events
                WHERE agent_id = %s AND (file_path ILIKE '%%honeyfile%%' OR file_path ILIKE '%%!0_%%')
                ORDER BY id DESC LIMIT 1;
                """,
                (agent_id,)
            )
            violated_evt = cursor.fetchone()
            violated_file = violated_evt[0] if violated_evt else None

            # Último evento/alerta. 'alerts' ya no tiene 'file_path' ni
            # 'rule_name' como columnas propias (nunca las tuvo en
            # realidad -- ver PENDIENTES.md); el nombre de la regla
            # sale de 'alert_rule'/'heuristic_rules'.
            cursor.execute(
                """
                SELECT alerts.title, severity_levels.name, alerts.created_at, heuristic_rules.name
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE alerts.agent_id = %s
                ORDER BY alerts.id DESC LIMIT 1;
                """,
                (agent_id,)
            )
            alert_row = cursor.fetchone()
            latest_alert = None
            if alert_row:
                latest_alert = {
                    "title": alert_row[0],
                    "severity": alert_row[1],
                    "created_at": alert_row[2].strftime("%d/%m/%Y %H:%M:%S") if alert_row[2] else "",
                    "file_path": None,
                    "rule_name": ALERT_RULE_LABELS_ES.get(alert_row[3], alert_row[3]) if alert_row[3] else ""
                }

            return {
                "id": row[0],
                "agent_code": f"AGT-{row[0]:06d}",
                "hostname": row[1],
                "operating_system": row[2],
                "os_version": row[3] or "",
                "architecture": None,
                "ip_address": str(row[4]) if row[4] else "127.0.0.1",
                "mac_address": None,
                "agent_version": row[5] or "v1.0.0 (watchdog)",
                "status": row[6],
                "last_seen_at": row[7].strftime("%d/%m/%Y %H:%M:%S") if row[7] else "Nunca",
                "enrolled_at": row[8].strftime("%d/%m/%Y") if row[8] else "",
                "risk_bucket": risk_bucket,
                "risk_score": risk_scores.get(risk_bucket, 0),
                "risk_label": RISK_LABELS_ES.get(risk_bucket, "Normal"),
                "is_isolated": is_isolated,
                "honeyfiles_total": honeyfiles_total,
                "honeyfiles_violated_file": violated_file,
                "latest_alert": latest_alert
            }
    finally:
        connection.close()


@app.post("/api/enrollment-tokens")
def generate_enrollment_token_api(request: Request, body: dict = None):
    """API para generar token de enrolamiento con duración dinámica."""
    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    created_by = user.get("id") if isinstance(user, dict) else None
    duration = (body or {}).get("duration", "24h") if body else "24h"

    if duration == "1h":
        interval_sql = "1 hour"
    elif duration == "7d":
        interval_sql = "7 days"
    elif duration == "15m":
        interval_sql = "15 minutes"
    else:
        interval_sql = "24 hours"

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO enrollment_tokens (token_hash, created_by, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '{interval_sql}')
                RETURNING id, expires_at;
                """,
                (token_hash, created_by)
            )
            res = cursor.fetchone()
            connection.commit()

            host = request.headers.get("host", "localhost:8000")
            server_url = f"http://{host}"
            command = f"python agent/main.py --enroll {token} --server {server_url}"

            return {
                "token": token,
                "token_id": res[0],
                "expires_at": res[1].strftime("%d/%m/%Y %H:%M:%S") if res[1] else "",
                "command": command
            }
    finally:
        connection.close()


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
                SELECT agents.id, endpoints.hostname, endpoints.os, endpoints.os_version,
                       endpoints.ip_address, agents.agent_version, agents.status,
                       agents.last_seen_at, agents.enrolled_at
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Endpoint no encontrado")

            (endpoint_id, hostname, operating_system, os_version,
             ip_address, agent_version, status, last_seen_at, enrolled_at) = row

            stale_seconds = get_agent_stale_seconds(cursor)

            if status != "ONLINE":
                status_bucket = "offline"
            elif last_seen_at and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() <= stale_seconds:
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
                    CASE severity_levels.name
                        WHEN 'CRITICAL' THEN 4
                        WHEN 'HIGH' THEN 3
                        WHEN 'SUSPICIOUS' THEN 2
                        ELSE 1
                    END
                )
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.agent_id = %s AND alerts.status = 'NEW';
                """,
                (agent_id,)
            )
            risk_rank_row = cursor.fetchone()[0]
            risk_bucket = {4: "CRITICAL", 3: "HIGH", 2: "SUSPICIOUS"}.get(risk_rank_row, "NORMAL")

            cursor.execute(
                """
                SELECT severity_levels.name, alerts.title, alerts.created_at
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.agent_id = %s
                ORDER BY alerts.created_at DESC
                LIMIT 5;
                """,
                (agent_id,)
            )
            latest_detections = [
                {"severity": sev, "title": title, "created_at": ts}
                for sev, title, ts in cursor.fetchall()
            ]

            # Credencial del agente -- si nunca completó enrollment (no
            # debería pasar, pero por las dudas) status queda None y
            # lo mostramos como "Sin credencial" en vez de asumir activa.
            cursor.execute(
                "SELECT status FROM agent_credentials WHERE agent_id = %s;",
                (agent_id,)
            )
            credential_row = cursor.fetchone()
            credential_active = (credential_row[0] == "ACTIVE") if credential_row else None

            cursor.execute(
                """
                (
                    SELECT 'alert' AS kind, severity_levels.name AS sev,
                           alerts.title AS label, alerts.created_at AS ts
                    FROM alerts
                    JOIN severity_levels ON severity_levels.id = alerts.severity_id
                    WHERE alerts.agent_id = %(agent_id)s
                    ORDER BY alerts.created_at DESC
                    LIMIT 8
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           event_types.name AS label, events.detected_at AS ts
                    FROM events
                    JOIN event_types ON event_types.id = events.event_type_id
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


EVENTOS_CATEGORY_LABELS_ES = {
    "honeyfile": "🍯 Honeyfile",
    "file": "📁 Archivo regular",
}

# Filtro/columna "Categoría" que pide el mockup no es una columna real
# de 'events' -- se deriva comparando events.file_path contra la ruta
# de un honeyfile real de ese mismo agente ('honeyfiles.file_path').
# No existen las categorías "Proceso" ni "Sistema" del mockup: el
# agente no reporta creación de procesos (ver PENDIENTES.md) y los
# heartbeats nunca se guardan en 'events'.
EVENT_IS_HONEYFILE_SQL = """
    EXISTS (
        SELECT 1 FROM honeyfiles
        WHERE honeyfiles.agent_id = events.agent_id
          AND honeyfiles.file_path = events.file_path
    )
"""


def _eventos_where(agent_id, type_filter, category, since, search, params):
    where_clauses = []

    if agent_id:
        where_clauses.append("events.agent_id = %(agent_id)s")
        params["agent_id"] = agent_id

    if type_filter:
        where_clauses.append("event_types.name = %(type)s")
        params["type"] = type_filter

    if category == "honeyfile":
        where_clauses.append(EVENT_IS_HONEYFILE_SQL)
    elif category == "file":
        where_clauses.append(f"NOT {EVENT_IS_HONEYFILE_SQL}")

    if since:
        where_clauses.append(
            "events.detected_at >= CURRENT_TIMESTAMP - INTERVAL %(since_interval)s"
        )
        params["since_interval"] = EVENTOS_SINCE_OPTIONS[since][1]

    if search:
        where_clauses.append(
            "(endpoints.hostname ILIKE %(search)s "
            "OR events.file_path ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    return where_sql


def _eventos_kpis(cursor):
    """KPIs reales de las últimas 24h -- ver PENDIENTES.md para lo que
    NO se incluye acá (no hay 'anomalías por evento': el score de
    riesgo vive en 'alerts', no en 'events')."""

    cursor.execute(
        "SELECT COUNT(*) FROM events WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';"
    )
    total_24h = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM honeyfile_activations WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';"
    )
    honeyfile_touches_24h = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM alerts WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';"
    )
    alerts_24h = cursor.fetchone()[0]

    # Tasa de entrada: eventos de los últimos 5 minutos / 300s. Una
    # ventana de 5 min amortigua el ruido de mirar solo el último
    # segundo; en un entorno de pocos agentes de prueba este número va
    # a ser chico casi siempre -- es real, no un valor de demo.
    cursor.execute(
        "SELECT COUNT(*) FROM events WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes';"
    )
    events_last_5min = cursor.fetchone()[0]
    event_rate = round(events_last_5min / 300.0, 2)

    return {
        "total_24h": total_24h,
        "honeyfile_touches_24h": honeyfile_touches_24h,
        "alerts_24h": alerts_24h,
        "event_rate": event_rate
    }


@app.get("/eventos")
def eventos_page(
    request: Request,
    agent_id: int | None = Query(None),
    type_filter: str = Query("", alias="type"),
    category: str = Query(""),
    since: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1)
):
    """Registro técnico de lo que reportan los agentes -- 'ocurrió
    esto, acá, a esta hora'. A propósito NO incluye proceso/PID real
    (el agente todavía no los reporta -- ver file_monitor.py) ni un
    juicio de severidad por evento (eso es trabajo de Detecciones).
    El filtro por 'alert_id' (venía de 'Eventos relacionados' en
    Detecciones) se sacó junto con 'alert_events' -- ver PENDIENTES.md."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    type_filter = type_filter if type_filter in EVENT_TYPE_LABELS_ES else ""
    category = category if category in EVENTOS_CATEGORY_LABELS_ES else ""
    since = since if since in EVENTOS_SINCE_OPTIONS else ""

    params = {}
    where_sql = _eventos_where(agent_id, type_filter, category, since, search, params)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            kpis = _eventos_kpis(cursor)

            cursor.execute(
                "SELECT agents.id, endpoints.hostname FROM agents "
                "JOIN endpoints ON endpoints.id = agents.endpoint_id ORDER BY endpoints.hostname;"
            )
            endpoint_options = cursor.fetchall()

            count_params = dict(params)
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                {where_sql};
                """,
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
                SELECT events.id, event_types.name, events.file_path,
                       endpoints.hostname, endpoints.os, events.agent_id, events.detected_at,
                       events.process_id, events.process_name, {EVENT_IS_HONEYFILE_SQL} AS is_honeyfile
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                {where_sql}
                ORDER BY events.id DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            rows = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute(
                    "SELECT endpoints.hostname FROM agents "
                    "JOIN endpoints ON endpoints.id = agents.endpoint_id WHERE agents.id = %s;",
                    (agent_id,)
                )
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    # events ya no tiene 'description' ni 'metadata' JSONB -- el nombre
    # del tipo y la ruta del archivo son columnas propias ahora
    # (event_types.name via join, events.file_path directo).
    events = [
        {
            "id": row[0],
            "event_code": f"EVT-{row[0]:06d}",
            "event_type": row[1],
            "type_label": EVENT_TYPE_LABELS_ES.get(row[1], row[1]),
            "file_path": row[2],
            "hostname": row[3],
            "operating_system": row[4],
            "agent_id": row[5],
            "detected_at": row[6],
            "process_id": row[7],
            "process_name": row[8],
            "is_honeyfile": row[9]
        }
        for row in rows
    ]

    last_id = events[0]["id"] if events else 0

    base_filters = {k: v for k, v in {
        "agent_id": agent_id, "type": type_filter, "category": category,
        "since": since, "search": search
    }.items() if v}
    filter_qs = urlencode(base_filters)

    return templates.TemplateResponse(
        request,
        "eventos.html",
        {
            "user": user,
            "active_page": "eventos",
            "events": events,
            "last_id": last_id,
            "kpis": kpis,
            "endpoint_options": endpoint_options,
            "event_type_options": EVENT_TYPE_LABELS_ES,
            "category_options": EVENTOS_CATEGORY_LABELS_ES,
            "since_options": EVENTOS_SINCE_OPTIONS,
            "current_type": type_filter,
            "current_category": category,
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
                SELECT events.id, event_types.name, events.file_path,
                       agents.id, endpoints.hostname, endpoints.os,
                       agents.status, agents.last_seen_at, events.detected_at
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                WHERE events.id = %s;
                """,
                (event_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Evento no encontrado")

            (evt_id, event_type, file_path, agent_id, hostname,
             operating_system, agent_status, last_seen_at, detected_at) = row

            stale_seconds = get_agent_stale_seconds(cursor)

            if agent_status != "ONLINE":
                agent_status_bucket = "offline"
            elif last_seen_at and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() <= stale_seconds:
                agent_status_bucket = "ok"
            else:
                agent_status_bucket = "attention"

    finally:
        connection.close()

    # "Detección relacionada" (lookup inverso vía alert_events) se
    # sacó: esa tabla no existe en la nueva estructura -- ver
    # PENDIENTES.md. 'extension' tampoco: salía de 'metadata' JSONB,
    # que ya no existe ('events.file_path' es columna directa ahora).
    related_alert = None

    event = {
        "id": evt_id,
        "event_code": f"EVT-{evt_id:06d}",
        "event_type": event_type,
        "type_label": EVENT_TYPE_LABELS_ES.get(event_type, event_type),
        "description": None,
        "file_path": file_path,
        # Ya no viene guardada (era parte de 'metadata' JSONB, que no
        # existe más) -- se recalcula del file_path real con el mismo
        # criterio que usaba el agente (os.path.splitext), no es un
        # dato inventado.
        "extension": (os.path.splitext(file_path)[1].lstrip(".").lower() or None) if file_path else None,
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


@app.get("/api/eventos/{event_id}/drawer")
def get_evento_drawer(event_id: int, request: Request):
    """Detalle rápido para el panel lateral de Eventos. 'Proceso' sale
    de 'events.process_id'/'process_name' -- columnas reales, pero
    siempre NULL hoy (ver PENDIENTES.md, "Atribución de proceso").
    No se fabrica línea de comando, hash de ejecutable, PID padre ni
    usuario ejecutor: ninguno de esos existe como dato en ningún lado
    del sistema."""

    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT events.id, event_types.name, events.file_path, events.detected_at,
                       events.process_id, events.process_name, endpoints.hostname,
                       endpoints.os, endpoints.os_version, endpoints.ip_address,
                       agents.id, agents.status, {EVENT_IS_HONEYFILE_SQL} AS is_honeyfile
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                WHERE events.id = %s;
                """,
                (event_id,)
            )
            r = cursor.fetchone()
            if not r:
                return JSONResponse({"error": "Evento no encontrado"}, status_code=404)

            file_path = r[2]
            is_honeyfile = r[12]

            honeyfile_activations = []
            if is_honeyfile:
                cursor.execute(
                    """
                    SELECT honeyfile_activations.detected_at, honeyfile_activations.operation,
                           honeyfile_activations.process_name, honeyfile_activations.process_id
                    FROM honeyfile_activations
                    JOIN honeyfiles ON honeyfiles.id = honeyfile_activations.honeyfile_id
                    WHERE honeyfiles.agent_id = %s AND honeyfiles.file_path = %s
                    ORDER BY honeyfile_activations.id DESC LIMIT 5;
                    """,
                    (r[10], file_path)
                )
                honeyfile_activations = [
                    {
                        "detected_at": ar[0].strftime("%d/%m %H:%M:%S") if ar[0] else "",
                        "operation": ar[1],
                        "process_name": ar[2] or "proceso desconocido",
                        "process_id": ar[3] or 0
                    }
                    for ar in cursor.fetchall()
                ]

            return {
                "id": r[0],
                "event_code": f"EVT-{r[0]:06d}",
                "type_label": EVENT_TYPE_LABELS_ES.get(r[1], r[1]),
                "file_path": file_path,
                "extension": (os.path.splitext(file_path)[1].lstrip(".").lower() or None) if file_path else None,
                "detected_at": r[3].strftime("%d/%m/%Y %H:%M:%S") if r[3] else "",
                "process_id": r[4],
                "process_name": r[5],
                "hostname": r[6],
                "operating_system": r[7],
                "os_version": r[8] or "",
                "ip_address": str(r[9]) if r[9] else "127.0.0.1",
                "agent_id": r[10],
                "agent_code": f"AGT-{r[10]:06d}",
                "agent_status": r[11],
                "is_honeyfile": is_honeyfile,
                "honeyfile_activations": honeyfile_activations
            }
    finally:
        connection.close()


@app.get("/api/eventos/live")
def get_eventos_live(
    request: Request,
    after_id: int = Query(0),
    agent_id: int | None = Query(None),
    type_filter: str = Query("", alias="type"),
    category: str = Query(""),
    since: str = Query(""),
    search: str = Query("")
):
    """El 'En Vivo' de Eventos es sondeo (polling) real, no streaming
    -- el proyecto no tiene WebSockets/SSE. El navegador llama esto
    cada pocos segundos pidiendo solo lo nuevo desde 'after_id' con
    los mismos filtros que tiene puestos la lista, y de paso trae los
    KPIs recalculados."""

    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    type_filter = type_filter if type_filter in EVENT_TYPE_LABELS_ES else ""
    category = category if category in EVENTOS_CATEGORY_LABELS_ES else ""
    since = since if since in EVENTOS_SINCE_OPTIONS else ""

    params = {"after_id": after_id}
    where_sql = _eventos_where(agent_id, type_filter, category, since, search, params)

    extra_clause = "events.id > %(after_id)s"
    where_sql = f"{where_sql} AND {extra_clause}" if where_sql else f"WHERE {extra_clause}"

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            kpis = _eventos_kpis(cursor)

            cursor.execute(
                f"""
                SELECT events.id, event_types.name, events.file_path,
                       endpoints.hostname, endpoints.os, events.agent_id, events.detected_at,
                       events.process_id, events.process_name, {EVENT_IS_HONEYFILE_SQL} AS is_honeyfile
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                {where_sql}
                ORDER BY events.id DESC
                LIMIT 100;
                """,
                params
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    events = [
        {
            "id": row[0],
            "event_code": f"EVT-{row[0]:06d}",
            "type_label": EVENT_TYPE_LABELS_ES.get(row[1], row[1]),
            "file_path": row[2],
            "hostname": row[3],
            "operating_system": row[4],
            "agent_id": row[5],
            "detected_at": row[6].strftime("%d/%m %H:%M:%S") if row[6] else "",
            "process_id": row[7],
            "process_name": row[8],
            "is_honeyfile": row[9]
        }
        for row in rows
    ]

    return {"events": events, "kpis": kpis}


@app.get("/eventos/export.csv")
def export_eventos_csv(
    request: Request,
    agent_id: int | None = Query(None),
    type_filter: str = Query("", alias="type"),
    category: str = Query(""),
    since: str = Query(""),
    search: str = Query("")
):
    """Exporta el feed filtrado (mismos filtros que /eventos) como CSV.
    Tope de 5000 filas para no colgar el servidor con una exportación
    sin límite -- si hace falta más, se puede acotar el rango de
    tiempo desde el filtro."""

    user = require_session_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    type_filter = type_filter if type_filter in EVENT_TYPE_LABELS_ES else ""
    category = category if category in EVENTOS_CATEGORY_LABELS_ES else ""
    since = since if since in EVENTOS_SINCE_OPTIONS else ""

    params = {}
    where_sql = _eventos_where(agent_id, type_filter, category, since, search, params)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT events.id, event_types.name, events.detected_at, endpoints.hostname,
                       endpoints.os, events.file_path, events.process_id, events.process_name,
                       {EVENT_IS_HONEYFILE_SQL} AS is_honeyfile
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                {where_sql}
                ORDER BY events.id DESC
                LIMIT 5000;
                """,
                params
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id", "codigo", "tipo", "categoria", "fecha_hora", "endpoint", "sistema_operativo",
        "ruta_archivo", "process_id", "process_name"
    ])
    for row in rows:
        writer.writerow([
            row[0],
            f"EVT-{row[0]:06d}",
            EVENT_TYPE_LABELS_ES.get(row[1], row[1]),
            "Honeyfile" if row[8] else "Archivo regular",
            row[2].strftime("%Y-%m-%d %H:%M:%S") if row[2] else "",
            row[3],
            row[4],
            row[5] or "",
            row[6] if row[6] is not None else "",
            row[7] or ""
        ])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eventos_alfa_sentinel.csv"}
    )


MANUAL_ALERT_RISK_SCORE_BY_SEVERITY = {
    "SUSPICIOUS": 45.00,
    "HIGH": 70.00,
    "CRITICAL": 90.00
}


class EventToAlert(BaseModel):
    severity: str
    title: str | None = None
    description: str | None = None


@app.post("/api/eventos/{event_id}/convert-to-alert")
def convert_evento_to_alert(event_id: int, body: EventToAlert, request: Request):
    """Promueve un evento crudo a una alerta real, a criterio del
    analista -- a diferencia de las alertas que arma el motor
    heurístico del agente, acá no hay un risk_score calculado (no
    hubo ventana/threshold evaluado), así que se guarda un puntaje
    fijo por banda de severidad (mitad del rango de cada banda en
    'severity_levels'), no un cálculo inventado con falsa precisión."""

    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    if body.severity not in ALERT_SEVERITY_LABELS_ES:
        return JSONResponse({"error": "Severidad inválida"}, status_code=400)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT events.id, event_types.name, events.file_path, events.detected_at,
                       events.agent_id, endpoints.hostname
                FROM events
                JOIN agents ON agents.id = events.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN event_types ON event_types.id = events.event_type_id
                WHERE events.id = %s;
                """,
                (event_id,)
            )
            r = cursor.fetchone()
            if not r:
                return JSONResponse({"error": "Evento no encontrado"}, status_code=404)

            event_code = f"EVT-{r[0]:06d}"
            type_label = EVENT_TYPE_LABELS_ES.get(r[1], r[1])
            file_path = r[2]
            agent_id = r[4]
            hostname = r[5]

            title = body.title or f"Alerta manual desde {event_code}"
            description = body.description or (
                f"Creada manualmente por {user.get('username', 'un analista')} "
                f"a partir del evento {event_code} ({type_label} en {hostname}"
                f"{': ' + file_path if file_path else ''})."
            )

            cursor.execute(
                "SELECT id FROM severity_levels WHERE name = %s;",
                (body.severity,)
            )
            severity_row = cursor.fetchone()
            if severity_row is None:
                return JSONResponse({"error": "Severidad desconocida en el catálogo"}, status_code=422)

            severity_id = severity_row[0]
            risk_score = MANUAL_ALERT_RISK_SCORE_BY_SEVERITY[body.severity]

            cursor.execute(
                """
                INSERT INTO alerts (agent_id, severity_id, title, description, risk_score, status)
                VALUES (%s, %s, %s, %s, %s, 'NEW')
                RETURNING id;
                """,
                (agent_id, severity_id, title, description, risk_score)
            )
            alert_id = cursor.fetchone()[0]

            connection.commit()

            return {"message": "Alerta creada", "alert_id": alert_id}
    finally:
        connection.close()


@app.get("/honeyfiles")
def honeyfiles_page(
    request: Request,
    agent_id: int | None = Query(None),
    status: str = Query(""),
    os_filter: str = Query("", alias="os"),
    search: str = Query("")
):
    """Vista principal de Honeyfiles (archivos señuelo)."""
    user = require_session_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            where_clauses = []
            params = {}

            if agent_id:
                where_clauses.append("honeyfiles.agent_id = %(agent_id)s")
                params["agent_id"] = agent_id
            if status:
                where_clauses.append("honeyfiles.status = %(status)s")
                params["status"] = status
            if os_filter:
                where_clauses.append("endpoints.os ILIKE %(os)s")
                params["os"] = f"%{os_filter}%"
            if search:
                where_clauses.append("(honeyfiles.file_name ILIKE %(search)s OR honeyfiles.file_path ILIKE %(search)s OR endpoints.hostname ILIKE %(search)s)")
                params["search"] = f"%{search}%"

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # 'agents' ya no tiene hostname/operating_system/ip_address/
            # architecture -- esos viven en 'endpoints' desde la
            # reestructuración a alfa_sentinel. Esta consulta no se había
            # actualizado todavía (se rompía contra la base nueva).
            cursor.execute(
                f"""
                SELECT honeyfiles.id, honeyfiles.file_name, honeyfiles.file_path,
                       honeyfiles.file_type, honeyfiles.status, honeyfiles.created_at,
                       honeyfiles.last_checked_at, agents.id AS agent_id, endpoints.hostname,
                       endpoints.ip_address, endpoints.os, endpoints.os_version,
                       agents.agent_version, agents.status AS agent_status,
                       agents.last_seen_at
                FROM honeyfiles
                JOIN agents ON agents.id = honeyfiles.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                {where_sql}
                ORDER BY honeyfiles.id DESC;
                """,
                params
            )
            rows = cursor.fetchall()

            # Conteo de activaciones por honeyfile
            cursor.execute(
                "SELECT honeyfile_id, COUNT(*) FROM honeyfile_activations GROUP BY honeyfile_id;"
            )
            activations_dict = dict(cursor.fetchall())

            # KPIs globales
            cursor.execute("SELECT COUNT(*) FROM honeyfiles;")
            total_honeyfiles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM honeyfiles WHERE status = 'ACTIVE';")
            active_honeyfiles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM honeyfiles WHERE status = 'TRIGGERED';")
            triggered_honeyfiles = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(detected_at) FROM honeyfile_activations;")
            last_act_row = cursor.fetchone()
            last_activation_ts = last_act_row[0] if last_act_row else None

            # Asignaciones (honeyfile_templates -> agent_honeyfile_templates)
            # que todavía no se materializaron como fila real en
            # 'honeyfiles' -- se crean solo cuando el agente confirma que
            # escribió el archivo (POST /agent/honeyfile-policy/report).
            cursor.execute(
                "SELECT COUNT(*) FROM agent_honeyfile_templates WHERE status = 'PENDING';"
            )
            pending_deployments = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM agent_honeyfile_templates WHERE status = 'FAILED';"
            )
            failed_deployments = cursor.fetchone()[0]

            # Filtros de SO distintos
            cursor.execute("SELECT DISTINCT os FROM endpoints ORDER BY os;")
            distinct_os = [r[0] for r in cursor.fetchall()]

            # Agentes disponibles para el Wizard de Despliegue
            cursor.execute(
                """
                SELECT agents.id, endpoints.hostname, endpoints.os, endpoints.os_version,
                       endpoints.ip_address, agents.status, agents.last_seen_at
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                ORDER BY agents.status DESC, endpoints.hostname ASC;
                """
            )
            agent_rows = cursor.fetchall()
            available_agents = [
                {
                    "id": r[0],
                    "hostname": r[1],
                    "operating_system": r[2],
                    "os_version": r[3] or "",
                    "ip_address": str(r[4]) if r[4] else "127.0.0.1",
                    "status": r[5],
                    "is_live": (r[5] == "ONLINE" and r[6] is not None and (datetime.now(r[6].tzinfo) - r[6]).total_seconds() < 30) if r[6] else False
                }
                for r in agent_rows
            ]

            filtered_hostname = None
            if agent_id:
                cursor.execute(
                    """
                    SELECT endpoints.hostname FROM agents
                    JOIN endpoints ON endpoints.id = agents.endpoint_id
                    WHERE agents.id = %s;
                    """,
                    (agent_id,)
                )
                h_row = cursor.fetchone()
                filtered_hostname = h_row[0] if h_row else None

    finally:
        connection.close()

    honeyfiles_list = []
    for r in rows:
        hf_id = r[0]
        act_cnt = activations_dict.get(hf_id, 0)
        status_val = r[4]
        if act_cnt > 0 and status_val == "ACTIVE":
            status_val = "TRIGGERED"

        last_seen = r[14]
        is_agent_live = (r[13] == "ONLINE" and last_seen is not None and (datetime.now(last_seen.tzinfo) - last_seen).total_seconds() < 30) if last_seen else False

        honeyfiles_list.append({
            "id": hf_id,
            "file_name": r[1],
            "file_path": r[2],
            "file_type": (r[3] or "FILE").upper(),
            "status": status_val,
            "created_at": r[5],
            "last_checked_at": r[6],
            "agent_id": r[7],
            "hostname": r[8],
            "ip_address": str(r[9]) if r[9] else "127.0.0.1",
            "operating_system": r[10],
            "os_version": r[11] or "",
            "agent_version": r[12] or "v1.0.0",
            "agent_status": r[13],
            "is_agent_live": is_agent_live,
            "activations_count": act_cnt
        })

    return templates.TemplateResponse(
        request,
        "honeyfiles.html",
        {
            "user": user,
            "active_page": "honeyfiles",
            "honeyfiles": honeyfiles_list,
            "total_honeyfiles": total_honeyfiles,
            "active_honeyfiles": active_honeyfiles,
            "triggered_honeyfiles": triggered_honeyfiles,
            "last_activation_ts": last_activation_ts,
            "pending_deployments": pending_deployments,
            "failed_deployments": failed_deployments,
            "distinct_os": distinct_os,
            "available_agents": available_agents,
            "current_status": status,
            "current_os": os_filter,
            "current_search": search,
            "filtered_agent_id": agent_id,
            "filtered_hostname": filtered_hostname
        }
    )


@app.get("/api/honeyfiles/{honeyfile_id}/detail")
def get_honeyfile_detail_api(honeyfile_id: int, request: Request):
    """API para obtener la información completa del Host Drawer de un Honeyfile."""
    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # Igual que en honeyfiles_page: join con 'endpoints' para
            # hostname/ip/os (ya no viven en 'agents'). 'file_hash' se lee
            # directo de 'honeyfiles' -- ya no se fabrica un hash de la
            # ruta acá, porque ahora el agente calcula el sha256 real del
            # contenido que escribió y lo manda al reportar el archivo.
            cursor.execute(
                """
                SELECT honeyfiles.id, honeyfiles.file_name, honeyfiles.file_path,
                       honeyfiles.file_type, honeyfiles.status, honeyfiles.created_at,
                       honeyfiles.last_checked_at, honeyfiles.file_hash, agents.id AS agent_id,
                       endpoints.hostname, endpoints.ip_address, endpoints.os, endpoints.os_version,
                       agents.agent_version, agents.status AS agent_status, agents.last_seen_at
                FROM honeyfiles
                JOIN agents ON agents.id = honeyfiles.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE honeyfiles.id = %s;
                """,
                (honeyfile_id,)
            )
            r = cursor.fetchone()
            if not r:
                return JSONResponse({"error": "Honeyfile no encontrado"}, status_code=404)

            # Historial de activaciones desde honeyfile_activations
            cursor.execute(
                """
                SELECT detected_at, operation, process_name, process_id
                FROM honeyfile_activations
                WHERE honeyfile_id = %s
                ORDER BY id DESC LIMIT 10;
                """,
                (honeyfile_id,)
            )
            act_rows = cursor.fetchall()
            activations = [
                {
                    "detected_at": ar[0].strftime("%d/%m %H:%M") if ar[0] else "",
                    "operation": ar[1],
                    "process_name": ar[2] or "proceso desconocido",
                    "process_id": ar[3] or 0
                }
                for ar in act_rows
            ]

            is_online = (r[14] == "ONLINE" and r[15] is not None and (datetime.now(r[15].tzinfo) - r[15]).total_seconds() < 30) if r[15] else False

            status_val = r[4]
            if len(activations) > 0 and status_val == "ACTIVE":
                status_val = "TRIGGERED"

            return {
                "id": r[0],
                "file_name": r[1],
                "file_path": r[2],
                "file_type": f"Archivo {(r[3] or 'FILE').upper()}",
                "sha256_hash": r[7] or "No disponible",
                "status": status_val,
                "created_at": r[5].strftime("%d/%m/%Y %H:%M") if r[5] else "",
                "last_checked_at": r[6].strftime("%d/%m/%Y %H:%M:%S") if r[6] else "Hace momentos",
                "agent_id": r[8],
                "agent_code": f"AGT-{r[8]:06d}",
                "hostname": r[9],
                "ip_address": str(r[10]) if r[10] else "127.0.0.1",
                "operating_system": r[11],
                "os_version": r[12] or "",
                "agent_version": r[13] or "v1.0.0",
                "is_online": is_online,
                "activations": activations,
                "activations_count": len(activations)
            }
    finally:
        connection.close()


@app.post("/api/honeyfiles/{honeyfile_id}/toggle-status")
def toggle_honeyfile_status_api(honeyfile_id: int, request: Request):
    """API para alternar el estado (ACTIVE / INACTIVE) o desactivar un Honeyfile."""
    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM honeyfiles WHERE id = %s;", (honeyfile_id,))
            row = cursor.fetchone()
            if not row:
                return JSONResponse({"error": "Honeyfile no encontrado"}, status_code=404)

            new_status = "INACTIVE" if row[0] in ("ACTIVE", "TRIGGERED") else "ACTIVE"
            cursor.execute(
                "UPDATE honeyfiles SET status = %s, last_checked_at = CURRENT_TIMESTAMP WHERE id = %s;",
                (new_status, honeyfile_id)
            )
            connection.commit()
            return {"id": honeyfile_id, "status": new_status, "message": f"Estado actualizado a {new_status}"}
    finally:
        connection.close()


@app.post("/api/honeyfiles/deploy")
def deploy_honeyfile_api(request: Request, body: dict = None):
    """Crea una plantilla de honeyfile ('honeyfile_templates') y la
    asigna a los agentes elegidos ('agent_honeyfile_templates', en
    PENDING).

    Antes esto insertaba directo en 'honeyfiles' como si el archivo ya
    existiera en el endpoint con solo tocar un botón acá -- ningún
    agente recibía la orden ni la ejecutaba, así que la fila era
    ficticia (el mismo tipo de problema que el toggle de aislamiento
    de red que se encontró y se sacó de Endpoints). Ahora esta ruta
    solo dice "qué debería existir"; la fila real en 'honeyfiles' se
    crea recién cuando el agente la escribe de verdad y lo confirma
    en POST /agent/honeyfile-policy/report."""
    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    if not body:
        return JSONResponse({"error": "Datos inválidos"}, status_code=400)

    display_name = (body.get("file_name") or "").strip()
    file_type = (body.get("file_type") or "txt").strip().lower()
    target_path = (body.get("target_path") or "").strip()
    platform = (body.get("platform") or "all").strip().lower()
    auto_deploy = bool(body.get("auto_deploy"))
    content = (body.get("content") or "").strip()
    agent_ids = body.get("agent_ids", []) or []

    if not display_name:
        return JSONResponse({"error": "Falta el nombre del archivo"}, status_code=400)
    if not target_path:
        return JSONResponse({"error": "Falta la ruta de destino en el cliente"}, status_code=400)
    if platform not in ("windows", "linux", "all"):
        return JSONResponse({"error": "Plataforma objetivo inválida"}, status_code=400)
    if not auto_deploy and not agent_ids:
        return JSONResponse({"error": "Selecciona al menos un endpoint destino, o marca despliegue automático"}, status_code=400)

    if not content:
        # Contenido genérico por defecto -- se muestra editable en el
        # wizard antes de desplegar, no se oculta ni se inventa nada
        # distinto de lo que el analista ve.
        content = "Documento confidencial. No modificar ni distribuir sin autorización."

    ext = f".{file_type}"
    full_file_name = display_name if display_name.lower().endswith(ext) else f"{display_name}{ext}"

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO honeyfile_templates (
                    name, file_name, file_type, file_path,
                    operating_system, content, auto_deploy, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    display_name, full_file_name, file_type.upper(), target_path,
                    platform.upper(), content, auto_deploy, user["id"]
                )
            )
            template_id = cursor.fetchone()[0]

            assigned_count = 0
            for aid in agent_ids:
                cursor.execute(
                    """
                    INSERT INTO agent_honeyfile_templates (agent_id, template_id, status)
                    VALUES (%s, %s, 'PENDING')
                    ON CONFLICT (agent_id, template_id) DO NOTHING
                    RETURNING id;
                    """,
                    (aid, template_id)
                )
                if cursor.fetchone() is not None:
                    assigned_count += 1

            connection.commit()
    finally:
        connection.close()

    if auto_deploy and not agent_ids:
        message = "Plantilla creada. Se creará sola en cada endpoint compatible la próxima vez que su agente se ejecute."
    elif auto_deploy:
        message = f"Plantilla creada y asignada a {assigned_count} endpoint(s) ahora mismo; también se aplicará sola en cualquier otro endpoint compatible que aparezca después."
    else:
        message = f"Plantilla creada y asignada a {assigned_count} endpoint(s). Se creará cuando el agente correspondiente vuelva a ejecutarse."

    return {
        "success": True,
        "template_id": template_id,
        "assigned_count": assigned_count,
        "message": message
    }


@app.get("/agent/honeyfile-policy")
def get_honeyfile_policy(x_agent_credential: str = Header(...)):
    """El agente llama esto en cada ejecución (no solo al enrolarse:
    hoy es un script de una sola pasada sin bucle, así que 'cada
    ejecución' es el único momento posible) para saber qué honeyfiles
    debería tener en disco.

    Devuelve dos listas:
    - 'pending': plantillas que todavía no se crearon en este agente
      (asignadas a mano desde el Wizard, o resueltas ahora mismo desde
      una plantilla con auto_deploy=TRUE que coincide con el SO de su
      endpoint). El agente tiene que escribirlas y reportarlas.
    - 'existing': honeyfiles que este agente ya creó en ejecuciones
      anteriores (tabla 'honeyfiles'), para que sepa qué rutas debe
      seguir vigilando aunque no las vuelva a crear."""

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            agent_id = resolve_agent_id(cursor, x_agent_credential)

            cursor.execute(
                """
                SELECT endpoints.os
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )
            os_row = cursor.fetchone()
            agent_os = (os_row[0] or "").upper() if os_row else ""

            # Resolver auto_deploy: cualquier plantilla activa marcada
            # auto_deploy=TRUE cuyo SO objetivo coincida (o sea 'ALL')
            # con el de este endpoint, que todavía no tenga una fila de
            # asignación para este agente, se asigna recién ahora --
            # perezoso a propósito: así una plantilla creada después de
            # que el agente ya existía igual lo alcanza en su próxima
            # ejecución, sin tener que sembrar filas por adelantado
            # para agentes que ni siquiera existían todavía.
            cursor.execute(
                """
                SELECT honeyfile_templates.id
                FROM honeyfile_templates
                WHERE honeyfile_templates.is_active = TRUE
                  AND honeyfile_templates.auto_deploy = TRUE
                  AND (honeyfile_templates.operating_system = 'ALL'
                       OR honeyfile_templates.operating_system = %s)
                  AND NOT EXISTS (
                      SELECT 1 FROM agent_honeyfile_templates
                      WHERE agent_honeyfile_templates.template_id = honeyfile_templates.id
                        AND agent_honeyfile_templates.agent_id = %s
                  );
                """,
                (agent_os, agent_id)
            )
            new_auto_template_ids = [r[0] for r in cursor.fetchall()]

            for template_id in new_auto_template_ids:
                cursor.execute(
                    """
                    INSERT INTO agent_honeyfile_templates (agent_id, template_id, status)
                    VALUES (%s, %s, 'PENDING')
                    ON CONFLICT (agent_id, template_id) DO NOTHING;
                    """,
                    (agent_id, template_id)
                )

            if new_auto_template_ids:
                connection.commit()

            # Pendientes de crear (recién asignadas arriba, asignaciones
            # manuales anteriores, o intentos previos que fallaron y se
            # reintentan).
            cursor.execute(
                """
                SELECT agent_honeyfile_templates.id, honeyfile_templates.file_name,
                       honeyfile_templates.file_type, honeyfile_templates.file_path,
                       honeyfile_templates.content
                FROM agent_honeyfile_templates
                JOIN honeyfile_templates ON honeyfile_templates.id = agent_honeyfile_templates.template_id
                WHERE agent_honeyfile_templates.agent_id = %s
                  AND agent_honeyfile_templates.status IN ('PENDING', 'FAILED')
                  AND honeyfile_templates.is_active = TRUE;
                """,
                (agent_id,)
            )
            pending = [
                {
                    "assignment_id": r[0],
                    "file_name": r[1],
                    "file_type": r[2],
                    "file_path": r[3],
                    "content": r[4]
                }
                for r in cursor.fetchall()
            ]

            # Ya creados en ejecuciones anteriores -- el agente los
            # necesita para saber qué rutas vigilar, no para recrearlas.
            cursor.execute(
                "SELECT id, file_path, file_name FROM honeyfiles WHERE agent_id = %s;",
                (agent_id,)
            )
            existing = [
                {"honeyfile_id": r[0], "file_path": r[1], "file_name": r[2]}
                for r in cursor.fetchall()
            ]

            return {"pending": pending, "existing": existing}
    finally:
        connection.close()


@app.get("/agent/rule-policy")
def get_rule_policy(x_agent_credential: str = Header(...)):
    """Agregado 2026-08-12: mismo patrón que GET /agent/honeyfile-policy
    -- el agente pide esto en cada ejecución (sigue siendo un script de
    una sola pasada sin bucle) para enterarse de los valores reales de
    peso/umbral/ventana de cada regla activa, en vez de tenerlos
    hardcodeados en FileActivityAnalyzer.__init__()
    (agent/heuristic_engine.py). Antes de esto, 'threshold' y
    'window_seconds' en 'heuristic_rules' eran solo referencia visual
    en /configuracion -- ahora el agente los aplica de verdad. Reglas
    con is_active=FALSE no se incluyen -- el agente ya no las evalúa
    en absoluto, en vez de evaluarlas con un umbral inalcanzable."""

    connection = get_connection()
    try:
        with connection.cursor() as cursor:

            # Solo valida que la credencial exista y esté activa -- las
            # reglas son globales, no por agente, así que no hace falta
            # el agent_id en sí para nada más que la autenticación.
            resolve_agent_id(cursor, x_agent_credential)

            cursor.execute(
                """
                SELECT name, weight, threshold, window_seconds
                FROM heuristic_rules
                WHERE is_active = TRUE;
                """
            )

            rules = [
                {
                    "name": r[0],
                    "weight": float(r[1]),
                    "threshold": float(r[2]),
                    "window_seconds": r[3]
                }
                for r in cursor.fetchall()
            ]

        return {"rules": rules}
    finally:
        connection.close()


class HoneyfileReportItem(BaseModel):
    assignment_id: int
    status: str
    file_path: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    file_hash: str | None = None
    error: str | None = None


class HoneyfileReport(BaseModel):
    results: list[HoneyfileReportItem]


@app.post("/agent/honeyfile-policy/report")
def report_honeyfile_policy(
    report: HoneyfileReport,
    x_agent_credential: str = Header(...)
):
    """El agente confirma acá qué pudo crear de verdad y qué no. Recién
    en este momento aparece la fila real en 'honeyfiles' -- antes de
    esto, un honeyfile 'PENDING' es solo una intención, no un archivo
    que exista en ningún disco."""

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            agent_id = resolve_agent_id(cursor, x_agent_credential)

            created_count = 0
            failed_count = 0

            for item in report.results:
                # La asignación tiene que ser de este agente -- no se
                # confía en que assignment_id venga "limpio".
                cursor.execute(
                    """
                    SELECT id FROM agent_honeyfile_templates
                    WHERE id = %s AND agent_id = %s;
                    """,
                    (item.assignment_id, agent_id)
                )
                if cursor.fetchone() is None:
                    continue

                if item.status == "CREATED":
                    cursor.execute(
                        """
                        INSERT INTO honeyfiles (
                            agent_id, file_path, file_name, file_type,
                            file_hash, status, last_checked_at
                        )
                        VALUES (%s, %s, %s, %s, %s, 'ACTIVE', CURRENT_TIMESTAMP)
                        RETURNING id;
                        """,
                        (
                            agent_id, item.file_path, item.file_name,
                            item.file_type, item.file_hash
                        )
                    )
                    cursor.execute(
                        """
                        UPDATE agent_honeyfile_templates
                        SET status = 'CREATED', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                        """,
                        (item.assignment_id,)
                    )
                    created_count += 1
                else:
                    cursor.execute(
                        """
                        UPDATE agent_honeyfile_templates
                        SET status = 'FAILED', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                        """,
                        (item.assignment_id,)
                    )
                    failed_count += 1

            connection.commit()

            return {
                "message": "Reporte de honeyfiles procesado",
                "created_count": created_count,
                "failed_count": failed_count
            }
    finally:
        connection.close()


DETECCIONES_PAGE_SIZE = 50


@app.get("/detecciones")
def detecciones_page(request: Request):
    """La lista se unificó dentro de 'Incidentes y Alertas' (2026-08-12)
    -- ver COMBINED_CTE / incidentes_page. Esta ruta se conserva como
    redirect para no romper enlaces/marcadores viejos.
    '/detecciones/{alert_id}' (el expediente de una alerta puntual)
    sigue existiendo tal cual, sin cambios -- ver deteccion_detail_page."""

    return RedirectResponse(url="/incidentes", status_code=302)


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

            rows = cursor.fetchall()

    finally:
        connection.close()

    users = [
        {
            "id": r[0],
            "username": r[1],
            "full_name": r[2],
            "email": r[3],
            "roles": r[4],
            "is_active": r[5],
            "last_login_at": r[6],
            "created_at": r[7]
        }
        for r in rows
    ]

    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "active_page": "usuarios",
            "users": users,
            "is_admin": "admin" in user.get("roles", [])
        }
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
                SELECT alerts.id, severity_levels.name, alerts.title,
                       endpoints.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
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
                SELECT severity_levels.name, COUNT(DISTINCT alerts.agent_id)
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.status = 'NEW'
                GROUP BY severity_levels.name;
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
                SELECT alerts.id, severity_levels.name, alerts.title,
                       endpoints.hostname, alerts.created_at
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
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
                    SELECT 'alert' AS kind, severity_levels.name AS sev,
                           alerts.title AS label, endpoints.hostname AS hostname,
                           alerts.created_at AS ts,
                           NULL AS file_path
                    FROM alerts
                    JOIN agents ON agents.id = alerts.agent_id
                    JOIN endpoints ON endpoints.id = agents.endpoint_id
                    JOIN severity_levels ON severity_levels.id = alerts.severity_id
                    ORDER BY alerts.created_at DESC
                    LIMIT 15
                )
                UNION ALL
                (
                    SELECT 'event' AS kind, NULL AS sev,
                           event_types.name AS label, endpoints.hostname AS hostname,
                           events.detected_at AS ts,
                           events.file_path AS file_path
                    FROM events
                    JOIN agents ON agents.id = events.agent_id
                    JOIN endpoints ON endpoints.id = agents.endpoint_id
                    JOIN event_types ON event_types.id = events.event_type_id
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
                SELECT alerts.id, severity_levels.name, alerts.title, alerts.description,
                       alerts.risk_score, alerts.status, alerts.created_at,
                       agents.id, endpoints.hostname, endpoints.os,
                       heuristic_rules.name, alerts.incident_id
                FROM alerts
                JOIN agents ON agents.id = alerts.agent_id
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE alerts.id = %s;
                """,
                (alert_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

    finally:
        connection.close()

    # "Eventos relacionados" (alert_events), "Notas del analista"
    # (alert_notes) y "Honeyfile relacionado" (cruce vía
    # alerts.details->>'last_file') se sacaron: ninguna de esas tres
    # tablas/columnas existe en la nueva estructura -- decisión
    # explícita de adoptarla tal cual. Ver PENDIENTES.md.
    notes = []
    related_events = []
    related_events_total = 0
    related_honeyfile = None

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
        "agent_id": row[7],
        "hostname": row[8],
        "operating_system": row[9],
        "rule_name": row[10],
        "rule_label": ALERT_RULE_LABELS_ES.get(row[10], row[10] or "—"),
        "is_honeyfile": row[10] == "honeyfile_access"
    }

    return templates.TemplateResponse(
        request,
        "deteccion_detail.html",
        {
            "user": user,
            "active_page": "detecciones",
            "d": detection,
            "existing_incident_id": row[11],
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
    """Escala una detección a incidente. 'incidents' ya no tiene
    'alert_id' ni existe la tabla puente 'incident_alerts' -- ahora
    'alerts.incident_id' es una FK directa nullable (un incidente
    agrupa varias alertas; cada alerta pertenece como máximo a un
    incidente). Si la detección ya estaba en un incidente, se
    devuelve ese en vez de crear uno nuevo."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT incident_id FROM alerts WHERE id = %s;",
                (incident.alert_id,)
            )

            alert_check = cursor.fetchone()

            if alert_check is None:
                raise HTTPException(status_code=404, detail="Alerta no encontrada")

            if alert_check[0] is not None:
                return {
                    "message": "Ya existía un incidente para esta alerta",
                    "incident_id": alert_check[0]
                }

            cursor.execute(
                """
                SELECT alerts.agent_id, alerts.title, alerts.description
                FROM alerts WHERE alerts.id = %s;
                """,
                (incident.alert_id,)
            )

            agent_id, title, description = cursor.fetchone()

            cursor.execute(
                """
                INSERT INTO incidents (
                    agent_id, title, description, classification
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (agent_id, title, description, incident.classification)
            )

            incident_id = cursor.fetchone()[0]

            cursor.execute(
                "UPDATE alerts SET incident_id = %s WHERE id = %s;",
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
    relacionadas. Con 'alerts.incident_id' como FK directa, esto es
    simplemente reasignar esa columna (una alerta solo puede estar en
    un incidente a la vez)."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT id FROM incidents WHERE id = %s;", (incident_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            cursor.execute(
                "UPDATE alerts SET incident_id = %s WHERE id = %s RETURNING id;",
                (incident_id, payload.alert_id)
            )

            linked = cursor.fetchone()

            if linked is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            connection.commit()

        return {
            "message": "Detección vinculada",
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
    Contenido -> Cerrado). La nueva 'incidents' no tiene 'updated_at'
    ni 'closed_by' -- solo se registra 'closed_at'."""

    if payload.status not in INCIDENT_STATUS_LABELS_ES:
        raise HTTPException(status_code=422, detail="Estado inválido")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if payload.status == "CLOSED":
                cursor.execute(
                    """
                    UPDATE incidents
                    SET status = %s, closed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (payload.status, incident_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE incidents
                    SET status = %s, closed_at = NULL
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (payload.status, incident_id)
                )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            log_audit(
                cursor, user["id"], "UPDATE_INCIDENT_STATUS", "incidents", incident_id,
                f"Estado -> {payload.status}"
            )

            connection.commit()

        return {
            "message": "Estado actualizado",
            "incident_id": incident_id,
            "status": payload.status,
            "status_label": INCIDENT_STATUS_LABELS_ES[payload.status]
        }

    finally:
        connection.close()


@app.patch("/incidents/{incident_id}/assign")
def assign_incident(
    incident_id: int,
    payload: IncidentAssign,
    user: dict = Depends(get_current_user)
):
    """Reintroducido 2026-08-12 -- 'assigned_to'/'assigned_at' se
    habían sacado al adoptar alfa_sentinel tal cual (ver PENDIENTES.md),
    pero se pidió la función de Responsable de verdad. payload.user_id
    en None desasigna (vuelve a 'Sin asignar')."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if payload.user_id is not None:

                cursor.execute("SELECT id FROM users WHERE id = %s;", (payload.user_id,))

                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")

                cursor.execute(
                    """
                    UPDATE incidents
                    SET assigned_to = %s, assigned_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (payload.user_id, incident_id)
                )

            else:

                cursor.execute(
                    """
                    UPDATE incidents
                    SET assigned_to = NULL, assigned_at = NULL
                    WHERE id = %s
                    RETURNING id;
                    """,
                    (incident_id,)
                )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            log_audit(
                cursor, user["id"],
                "ASSIGN_INCIDENT" if payload.user_id else "UNASSIGN_INCIDENT",
                "incidents", incident_id,
                f"Responsable -> user_id={payload.user_id}" if payload.user_id else "Responsable removido"
            )

            connection.commit()

        return {
            "message": "Responsable actualizado" if payload.user_id else "Incidente desasignado",
            "incident_id": incident_id,
            "user_id": payload.user_id
        }

    finally:
        connection.close()


@app.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    user: dict = Depends(get_current_user)
):
    """Página /configuracion. 'weight'/'is_active'/'threshold'/
    'window_seconds' son ahora los cuatro campos de 'heuristic_rules'
    que el sistema realmente lee después de guardarlos:

    - 'weight' se copia a 'alert_rule.weight_applied' en cada alerta
      nueva que matchea la regla (POST /agent/alerts) y participa del
      cálculo del riesgo agregado en reportes/analítica.
    - 'is_active' decide si una alerta nueva queda vinculada a la
      regla (is_active = FALSE en la consulta de POST /agent/alerts) y
      además ahora decide si el agente la evalúa en absoluto (ver
      GET /agent/rule-policy).
    - 'threshold'/'window_seconds' (2026-08-12): antes eran solo
      referencia visual porque el agente los tenía hardcodeados en
      FileActivityAnalyzer.__init__() (agent/heuristic_engine.py) y
      arrancaba sin pedirle nada a este ni a ningún otro endpoint.
      Ahora el agente pide GET /agent/rule-policy en cada ejecución
      (mismo patrón que ya existía para honeyfiles) y usa estos
      valores de verdad -- el cambio se aplica recién la próxima vez
      que el agente arranque, no en caliente sobre un proceso ya
      corriendo (sigue sin tener bucle en segundo plano, ver
      PENDIENTES.md)."""

    if all(v is None for v in (payload.weight, payload.is_active, payload.threshold, payload.window_seconds)):
        raise HTTPException(status_code=422, detail="Nada para actualizar")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            fields = []
            values = []

            if payload.weight is not None:
                if payload.weight < 0:
                    raise HTTPException(status_code=422, detail="El peso no puede ser negativo")
                fields.append("weight = %s")
                values.append(payload.weight)

            if payload.is_active is not None:
                fields.append("is_active = %s")
                values.append(payload.is_active)

            if payload.threshold is not None:
                if payload.threshold <= 0:
                    raise HTTPException(status_code=422, detail="El umbral tiene que ser mayor a 0")
                fields.append("threshold = %s")
                values.append(payload.threshold)

            if payload.window_seconds is not None:
                if payload.window_seconds <= 0:
                    raise HTTPException(status_code=422, detail="La ventana tiene que ser mayor a 0 segundos")
                fields.append("window_seconds = %s")
                values.append(payload.window_seconds)

            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(rule_id)

            cursor.execute(
                f"""
                UPDATE heuristic_rules
                SET {', '.join(fields)}
                WHERE id = %s
                RETURNING id, name, weight, is_active, threshold, window_seconds;
                """,
                values
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Regla no encontrada")

            change_parts = []
            if payload.weight is not None:
                change_parts.append(f"peso -> {payload.weight}")
            if payload.is_active is not None:
                change_parts.append(f"activa -> {payload.is_active}")
            if payload.threshold is not None:
                change_parts.append(f"umbral -> {payload.threshold}")
            if payload.window_seconds is not None:
                change_parts.append(f"ventana -> {payload.window_seconds}s")

            log_audit(
                cursor, user["id"], "UPDATE_RULE", "heuristic_rules", updated[0],
                f"{updated[1]}: {', '.join(change_parts)}"
            )

            connection.commit()

        return {
            "message": "Regla actualizada",
            "rule_id": updated[0],
            "name": updated[1],
            "weight": float(updated[2]),
            "is_active": updated[3],
            "threshold": float(updated[4]),
            "window_seconds": updated[5]
        }

    finally:
        connection.close()


@app.patch("/settings/{key}")
def update_setting(
    key: str,
    payload: SettingUpdate,
    user: dict = Depends(get_current_user)
):
    """Página /configuracion > Agentes (2026-08-12). A propósito solo
    acepta claves que el servidor de verdad vuelve a leer -- hoy la
    única es 'agent_stale_seconds' (ver get_agent_stale_seconds()).
    No se expone un endpoint genérico "guardame cualquier key" sin
    lista blanca: eso permitiría crear settings que nadie consume,
    el mismo problema que ya se evitó con threshold/window_seconds
    en las reglas heurísticas."""

    KNOWN_SETTINGS = {
        "agent_stale_seconds": {
            "cast": int,
            "validate": lambda v: v > 0,
            "error": "Tiene que ser un número entero mayor a 0.",
        }
    }

    if key not in KNOWN_SETTINGS:
        raise HTTPException(
            status_code=404,
            detail=f"'{key}' no es un parámetro configurable -- no hay ningún mecanismo en el servidor que lo consuma."
        )

    spec = KNOWN_SETTINGS[key]

    try:
        cast_value = spec["cast"](payload.value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=spec["error"])

    if not spec["validate"](cast_value):
        raise HTTPException(status_code=422, detail=spec["error"])

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE system_settings
                SET value = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE key = %s
                RETURNING key, value;
                """,
                (str(cast_value), user["id"], key)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Parámetro no encontrado")

            log_audit(
                cursor, user["id"], "UPDATE_SETTING", "system_settings", None,
                f"{key} -> {cast_value}"
            )

            connection.commit()

        return {"message": "Parámetro actualizado", "key": updated[0], "value": updated[1]}

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
                SET classification = %s
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
                SET description = %s
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
    positivo -> Cerrada. 'alerts.resolved_at' (columna nueva de
    alfa_sentinel) se completa al cerrar/marcar falso positivo y se
    limpia si se reabre, mismo criterio que 'incidents.closed_at'."""

    if payload.status not in ALERT_STATUS_LABELS_ES:
        raise HTTPException(status_code=422, detail="Estado inválido")

    resolved_statuses = ("CLOSED", "FALSE_POSITIVE")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE alerts
                SET status = %s,
                    resolved_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE id = %s
                RETURNING id;
                """,
                (payload.status, payload.status in resolved_statuses, alert_id)
            )

            updated = cursor.fetchone()

            if updated is None:
                raise HTTPException(status_code=404, detail="Detección no encontrada")

            log_audit(
                cursor, user["id"], "UPDATE_ALERT_STATUS", "alerts", alert_id,
                f"Estado -> {payload.status}"
            )

            connection.commit()

        return {
            "message": "Estado actualizado",
            "alert_id": alert_id,
            "status": payload.status,
            "status_label": ALERT_STATUS_LABELS_ES[payload.status]
        }

    finally:
        connection.close()


# Notas de analista sobre detecciones/incidentes (alert_notes,
# incident_notes) y "Responsable" de incidente (assigned_to/
# assigned_at) se sacaron: esas tablas/columnas no existen en la
# nueva estructura (alfa_sentinel) -- decisión explícita de adoptarla
# tal cual. Ver PENDIENTES.md.

# 'severity' y 'detection_count' no son columnas de 'incidents' --
# se derivan de las alertas vinculadas vía 'alerts.incident_id'
# (antes: tabla puente 'incident_alerts', ahora FK directa).
# 'severity' es la más alta entre esas detecciones (mismo criterio de
# "peor caso" que ya usa ENDPOINT_CTE para el riesgo de un endpoint).
# Se arma como CTE para poder filtrar/contar por estos valores
# derivados en cada consulta que lo necesite.
INCIDENT_CTE = """
    WITH incident_data AS (
        SELECT incidents.id, incidents.title, incidents.description,
               incidents.status, incidents.classification,
               incidents.opened_at, incidents.closed_at,
               incidents.agent_id,
               endpoints.hostname,
               (
                   SELECT COUNT(*) FROM alerts
                   WHERE alerts.incident_id = incidents.id
               ) AS detection_count,
               (
                   SELECT severity_levels.name FROM alerts
                   JOIN severity_levels ON severity_levels.id = alerts.severity_id
                   WHERE alerts.incident_id = incidents.id
                   ORDER BY CASE severity_levels.name
                       WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
                       WHEN 'SUSPICIOUS' THEN 2 ELSE 1
                   END DESC
                   LIMIT 1
               ) AS severity,
               (
                   SELECT COALESCE(MAX(alerts.risk_score), 0) FROM alerts
                   WHERE alerts.incident_id = incidents.id
               ) AS risk_score,
               incidents.assigned_to,
               assigned_user.full_name AS assigned_to_name
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        LEFT JOIN users AS assigned_user ON assigned_user.id = incidents.assigned_to
    )
"""

INCIDENTES_PAGE_SIZE = 25

# 'Incidentes y Alertas' unifica dos cosas de naturaleza distinta en
# una sola matriz, tal como lo pidió el mockup: incidentes ya agrupados
# (varias alertas relacionadas bajo un mismo caso) y alertas sueltas
# que todavía no se escalaron a incidente (alerts.incident_id IS NULL).
# Antes eran dos pantallas separadas (Detecciones / Incidentes) -- esa
# separación se mantiene a nivel de rutas (/detecciones/{id} sigue
# existiendo para el detalle de una alerta puntual) pero la LISTA
# ahora es una sola. 'status_bucket' traduce los dos vocabularios de
# estado reales (incidents.status e alerts.status, que no coinciden)
# a un set compartido solo para poder filtrar/colorear parejo -- el
# estado real de cada fila (status_label) se sigue mostrando tal cual
# está guardado, no se renombra.
COMBINED_CTE = """
    WITH combined AS (
        SELECT
            'incident' AS kind, incidents.id AS id, incidents.opened_at AS ts,
            incidents.status AS raw_status,
            CASE incidents.status
                WHEN 'OPEN' THEN 'nuevo' WHEN 'IN_PROGRESS' THEN 'investigando'
                WHEN 'CONTAINED' THEN 'contenido' WHEN 'CLOSED' THEN 'cerrado'
                ELSE 'nuevo'
            END AS status_bucket,
            endpoints.hostname, endpoints.ip_address, agents.id AS agent_id,
            (
                SELECT severity_levels.name FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.incident_id = incidents.id
                ORDER BY CASE severity_levels.name
                    WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
                    WHEN 'SUSPICIOUS' THEN 2 ELSE 1
                END DESC LIMIT 1
            ) AS severity,
            (
                SELECT COALESCE(MAX(alerts.risk_score), 0) FROM alerts
                WHERE alerts.incident_id = incidents.id
            ) AS risk_score,
            (
                SELECT STRING_AGG(DISTINCT heuristic_rules.name, ' + ') FROM alerts
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE alerts.incident_id = incidents.id
            ) AS rule_names,
            (SELECT COUNT(*) FROM alerts WHERE alerts.incident_id = incidents.id) AS detection_count,
            incidents.assigned_to, assigned_user.full_name AS assigned_to_name
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        LEFT JOIN users AS assigned_user ON assigned_user.id = incidents.assigned_to

        UNION ALL

        SELECT
            'alert' AS kind, alerts.id AS id, alerts.created_at AS ts,
            alerts.status AS raw_status,
            CASE alerts.status
                WHEN 'NEW' THEN 'nuevo' WHEN 'ACKNOWLEDGED' THEN 'investigando'
                WHEN 'ESCALATED' THEN 'confirmado' WHEN 'CLOSED' THEN 'cerrado'
                WHEN 'FALSE_POSITIVE' THEN 'falso_positivo'
                ELSE 'nuevo'
            END AS status_bucket,
            endpoints.hostname, endpoints.ip_address, agents.id AS agent_id,
            severity_levels.name AS severity,
            alerts.risk_score AS risk_score,
            heuristic_rules.name AS rule_names,
            0 AS detection_count,
            NULL::BIGINT AS assigned_to, NULL::TEXT AS assigned_to_name
        FROM alerts
        JOIN agents ON agents.id = alerts.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        JOIN severity_levels ON severity_levels.id = alerts.severity_id
        LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
        LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
        WHERE alerts.incident_id IS NULL
    )
"""

STATUS_BUCKET_LABELS_ES = {
    "nuevo": "Nuevo",
    "investigando": "En investigación",
    "confirmado": "Confirmado",
    "contenido": "Contenido",
    "cerrado": "Cerrado",
    "falso_positivo": "Falso positivo",
}


@app.get("/incidentes")
def incidentes_page(
    request: Request,
    agent_id: int | None = Query(None),
    status_bucket: str = Query("", alias="status"),
    severity: str = Query(""),
    rule: str = Query(""),
    since: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1)
):
    """Centro de investigación y respuesta: una sola matriz con
    incidentes ya agrupados (varias detecciones relacionadas) y
    alertas todavía sueltas (sin escalar a incidente). Antes eran dos
    pantallas separadas -- Detecciones (alertas) e Incidentes -- ver
    PENDIENTES.md, 'Unificación de Incidentes y Alertas'."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    status_bucket = status_bucket if status_bucket in STATUS_BUCKET_LABELS_ES else ""
    severity = severity if severity in ALERT_SEVERITY_LABELS_ES else ""
    rule = rule if rule in ALERT_RULE_LABELS_ES else ""
    since = since if since in INCIDENTES_SINCE_OPTIONS else ""

    where_clauses = []
    params = {}

    if agent_id:
        where_clauses.append("agent_id = %(agent_id)s")
        params["agent_id"] = agent_id

    if status_bucket:
        where_clauses.append("status_bucket = %(status_bucket)s")
        params["status_bucket"] = status_bucket

    if severity:
        where_clauses.append("severity = %(severity)s")
        params["severity"] = severity

    if rule:
        where_clauses.append("rule_names ILIKE %(rule)s")
        params["rule"] = f"%{rule}%"

    if since:
        where_clauses.append("ts >= CURRENT_TIMESTAMP - INTERVAL %(since_interval)s")
        params["since_interval"] = INCIDENTES_SINCE_OPTIONS[since][1]

    if search:
        where_clauses.append(
            "(hostname ILIKE %(search)s OR CAST(ip_address AS TEXT) ILIKE %(search)s "
            "OR rule_names ILIKE %(search)s OR CAST(id AS TEXT) ILIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # KPIs -- siempre globales, sin filtrar (mismo criterio
            # que el resto de las listas).
            cursor.execute(
                COMBINED_CTE + "SELECT COUNT(*) FROM combined WHERE kind = 'incident' AND severity = 'CRITICAL' AND raw_status != 'CLOSED';"
            )
            critical_incidents = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE status IN ('NEW', 'ACKNOWLEDGED');"
            )
            active_alerts = cursor.fetchone()[0]

            # 'host_isolations' no lo escribe nada todavía (el agente
            # no tiene forma de aislar una red -- ver PENDIENTES.md).
            # Se cuenta igual, de verdad: hoy siempre da 0, y el día
            # que exista aislamiento real este número deja de ser 0
            # solo, sin tocar la consulta.
            cursor.execute(
                "SELECT COUNT(*) FROM host_isolations WHERE released_at IS NULL;"
            )
            isolated_hosts = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)))
                FROM alerts WHERE resolved_at IS NOT NULL;
                """
            )
            mttr_row = cursor.fetchone()
            mttr_seconds = mttr_row[0] if mttr_row else None
            mttr_minutes = round(mttr_seconds / 60, 1) if mttr_seconds is not None else None

            cursor.execute(
                "SELECT agents.id, endpoints.hostname FROM agents "
                "JOIN endpoints ON endpoints.id = agents.endpoint_id ORDER BY endpoints.hostname;"
            )
            endpoint_options = cursor.fetchall()

            cursor.execute("SELECT id, full_name FROM users ORDER BY full_name;")
            assignable_users = [{"id": r[0], "full_name": r[1]} for r in cursor.fetchall()]

            count_params = dict(params)
            cursor.execute(
                COMBINED_CTE + f"SELECT COUNT(*) FROM combined {where_sql};",
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
                COMBINED_CTE + f"""
                SELECT kind, id, ts, raw_status, status_bucket, hostname, ip_address,
                       agent_id, severity, risk_score, rule_names, detection_count,
                       assigned_to, assigned_to_name
                FROM combined
                {where_sql}
                ORDER BY ts DESC
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                page_params
            )

            rows = cursor.fetchall()

            filtered_hostname = None

            if agent_id:
                cursor.execute(
                    "SELECT endpoints.hostname FROM agents "
                    "JOIN endpoints ON endpoints.id = agents.endpoint_id WHERE agents.id = %s;",
                    (agent_id,)
                )
                hostname_row = cursor.fetchone()
                filtered_hostname = hostname_row[0] if hostname_row else None

    finally:
        connection.close()

    items = []
    for row in rows:
        (kind, item_id, ts, raw_status, bucket, hostname, ip_address, item_agent_id,
         severity_val, risk_score, rule_names, detection_count, assigned_to, assigned_to_name) = row

        items.append({
            "kind": kind,
            "id": item_id,
            "code": f"INC-{item_id:05d}" if kind == "incident" else f"ALT-{item_id:05d}",
            "detail_url": f"/incidentes/{item_id}" if kind == "incident" else f"/detecciones/{item_id}",
            "ts": ts,
            "raw_status": raw_status,
            "status_bucket": bucket,
            "status_label": (INCIDENT_STATUS_LABELS_ES.get(raw_status, raw_status) if kind == "incident"
                              else ALERT_STATUS_LABELS_ES.get(raw_status, raw_status)),
            "hostname": hostname,
            "ip_address": str(ip_address) if ip_address else "127.0.0.1",
            "agent_id": item_agent_id,
            "severity": severity_val,
            "severity_label": ALERT_SEVERITY_LABELS_ES.get(severity_val, severity_val or "—"),
            "risk_score": risk_score,
            "rule_label": " + ".join(
                ALERT_RULE_LABELS_ES.get(n, n) for n in (rule_names or "").split(" + ") if n
            ) or "—",
            "detection_count": detection_count,
            "assigned_to": assigned_to,
            "assigned_to_name": assigned_to_name
        })

    base_filters = {k: v for k, v in {
        "agent_id": agent_id, "status": status_bucket, "severity": severity,
        "rule": rule, "since": since, "search": search
    }.items() if v}
    filter_qs = urlencode(base_filters)

    return templates.TemplateResponse(
        request,
        "incidentes.html",
        {
            "user": user,
            "active_page": "incidentes",
            "items": items,
            "critical_incidents": critical_incidents,
            "active_alerts": active_alerts,
            "isolated_hosts": isolated_hosts,
            "mttr_minutes": mttr_minutes,
            "endpoint_options": endpoint_options,
            "assignable_users": assignable_users,
            "status_options": STATUS_BUCKET_LABELS_ES,
            "incident_status_options": INCIDENT_STATUS_LABELS_ES,
            "alert_status_options": ALERT_STATUS_LABELS_ES,
            "severity_options": ALERT_SEVERITY_LABELS_ES,
            "rule_options": ALERT_RULE_LABELS_ES,
            "since_options": INCIDENTES_SINCE_OPTIONS,
            "current_status": status_bucket,
            "current_severity": severity,
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


@app.get("/api/incidentes/{kind}/{item_id}/drawer")
def get_incidente_drawer(kind: str, item_id: int, request: Request):
    """Expediente para el panel lateral -- sirve tanto un incidente
    agrupado como una alerta suelta ('kind' viene de la fila que
    armó COMBINED_CTE). La 'cadena de evidencia' es real: eventos y
    activaciones de honeyfile del mismo agente en una ventana
    alrededor del momento en que se disparó (5 min antes, 1 min
    después) -- no se inventa un paso de 'ejecución de proceso' que
    el agente no reportó."""

    user = require_session_user(request)
    if user is None:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    if kind not in ("incident", "alert"):
        return JSONResponse({"error": "Tipo inválido"}, status_code=400)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:

            if kind == "incident":

                cursor.execute(INCIDENT_CTE + "SELECT * FROM incident_data WHERE id = %s;", (item_id,))
                row = cursor.fetchone()
                if row is None:
                    return JSONResponse({"error": "Incidente no encontrado"}, status_code=404)

                (inc_id, title_val, description_val, status, classification, opened_at, closed_at,
                 agent_id, hostname, detection_count, severity, risk_score,
                 assigned_to, assigned_to_name) = row

                cursor.execute(
                    """
                    SELECT alerts.created_at, heuristic_rules.name
                    FROM alerts
                    LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                    LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                    WHERE alerts.incident_id = %s
                    ORDER BY alerts.created_at ASC;
                    """,
                    (item_id,)
                )
                linked = cursor.fetchall()
                anchor_ts = linked[0][0] if linked else opened_at
                is_honeyfile = any(r[1] == "honeyfile_access" for r in linked)
                code = f"INC-{inc_id:05d}"
                status_label = INCIDENT_STATUS_LABELS_ES.get(status, status)

            else:

                cursor.execute(
                    """
                    SELECT alerts.id, alerts.title, alerts.description, alerts.status, alerts.created_at,
                           alerts.risk_score, severity_levels.name, heuristic_rules.name,
                           alerts.agent_id
                    FROM alerts
                    JOIN severity_levels ON severity_levels.id = alerts.severity_id
                    LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                    LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                    WHERE alerts.id = %s;
                    """,
                    (item_id,)
                )
                row = cursor.fetchone()
                if row is None:
                    return JSONResponse({"error": "Alerta no encontrada"}, status_code=404)

                (alert_id, title_val, description_val, status, anchor_ts, risk_score, severity,
                 rule_name, agent_id) = row

                code = f"ALT-{alert_id:05d}"
                status_label = ALERT_STATUS_LABELS_ES.get(status, status)
                is_honeyfile = rule_name == "honeyfile_access"
                classification = None
                assigned_to = None
                assigned_to_name = None
                detection_count = 1

            cursor.execute(
                """
                SELECT endpoints.hostname, endpoints.ip_address, endpoints.os,
                       agents.status, agents.last_seen_at
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )
            hostname, ip_address, operating_system, agent_status, last_seen_at = cursor.fetchone()

            stale_seconds = get_agent_stale_seconds(cursor)

            is_online = (
                agent_status == "ONLINE" and last_seen_at is not None
                and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() < stale_seconds
            ) if last_seen_at else False

            window_start = anchor_ts - timedelta(minutes=5)
            window_end = anchor_ts + timedelta(minutes=1)

            cursor.execute(
                """
                SELECT events.detected_at, event_types.name, events.file_path
                FROM events
                JOIN event_types ON event_types.id = events.event_type_id
                WHERE events.agent_id = %s
                  AND events.detected_at BETWEEN %s AND %s
                ORDER BY events.detected_at DESC LIMIT 25;
                """,
                (agent_id, window_start, window_end)
            )
            timeline = [
                {
                    "at_raw": r[0],
                    "at": r[0].strftime("%d/%m %H:%M:%S"),
                    "kind": "event",
                    "label": EVENT_TYPE_LABELS_ES.get(r[1], r[1]),
                    "detail": r[2] or ""
                }
                for r in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT honeyfile_activations.detected_at, honeyfile_activations.operation,
                       honeyfiles.file_name, honeyfile_activations.process_name,
                       honeyfile_activations.process_id
                FROM honeyfile_activations
                JOIN honeyfiles ON honeyfiles.id = honeyfile_activations.honeyfile_id
                WHERE honeyfile_activations.agent_id = %s
                  AND honeyfile_activations.detected_at BETWEEN %s AND %s
                ORDER BY honeyfile_activations.detected_at DESC LIMIT 10;
                """,
                (agent_id, window_start, window_end)
            )
            timeline += [
                {
                    "at_raw": r[0],
                    "at": r[0].strftime("%d/%m %H:%M:%S"),
                    "kind": "honeyfile",
                    "label": f"{r[1]} · {r[2]}",
                    "detail": f"proceso: {r[3] or 'No disponible'} (PID: {r[4] if r[4] is not None else 'No disponible'})"
                }
                for r in cursor.fetchall()
            ]

            timeline.sort(key=lambda i: i["at_raw"], reverse=True)
            for item in timeline:
                del item["at_raw"]

    finally:
        connection.close()

    return {
        "kind": kind,
        "id": item_id,
        "code": code,
        "title": title_val,
        "description": description_val,
        "status": status,
        "status_label": status_label,
        "severity": severity,
        "severity_label": ALERT_SEVERITY_LABELS_ES.get(severity, severity or "—"),
        "risk_score": risk_score,
        "classification": classification,
        "classification_label": INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "Sin clasificar") if kind == "incident" else None,
        "assigned_to": assigned_to,
        "assigned_to_name": assigned_to_name,
        "hostname": hostname,
        "ip_address": str(ip_address) if ip_address else "127.0.0.1",
        "operating_system": operating_system,
        "is_online": is_online,
        "agent_id": agent_id,
        "detection_count": detection_count,
        "is_honeyfile": is_honeyfile,
        "timeline": timeline
    }


@app.get("/incidentes/{incident_id}/reporte.pdf")
def incidente_reporte_pdf(incident_id: int, request: Request):
    """PDF del incidente (2026-08-12), pedido junto con la unificación
    de Incidentes y Alertas. Solo existe para incidentes agrupados, no
    para alertas sueltas -- una alerta sin escalar no tiene 'ficha' de
    caso todavía (el link del drawer ya queda deshabilitado para
    kind == 'alert' en el frontend).

    Todo el contenido sale de tablas reales: 'incidents', 'alerts',
    'alert_rule'/'heuristic_rules', 'endpoints'/'agents', 'events' y
    'honeyfile_activations'/'honeyfiles' (para el hash SHA-256, que
    'honeyfiles.file_hash' sí guarda). Lo que el agente no reporta hoy
    -- proceso padre, línea de comando, usuario ejecutor, hash de un
    archivo cualquiera que no sea honeyfile, e historial de cambios de
    estado del incidente -- se imprime como 'No disponible' en vez de
    inventarse, siguiendo la misma regla que el resto de la consola."""

    user = require_session_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:

            cursor.execute(INCIDENT_CTE + "SELECT * FROM incident_data WHERE id = %s;", (incident_id,))
            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Incidente no encontrado")

            (inc_id, title_val, description_val, status, classification, opened_at, closed_at,
             agent_id, hostname, detection_count, severity, risk_score,
             assigned_to, assigned_to_name) = row

            cursor.execute(
                """
                SELECT endpoints.hostname, endpoints.ip_address, endpoints.os
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )
            ep_hostname, ep_ip, ep_os = cursor.fetchone()

            cursor.execute(
                """
                SELECT alerts.id, alerts.title, alerts.created_at, alerts.resolved_at,
                       alerts.status, alerts.risk_score, severity_levels.name,
                       heuristic_rules.name, alert_rule.weight_applied
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE alerts.incident_id = %s
                ORDER BY alerts.created_at ASC;
                """,
                (incident_id,)
            )
            linked_alerts = cursor.fetchall()

            if linked_alerts:
                window_start = min(r[2] for r in linked_alerts) - timedelta(minutes=5)
                last_ts = max((r[3] or r[2]) for r in linked_alerts)
                window_end = (closed_at or last_ts) + timedelta(minutes=1)
            else:
                window_start = opened_at - timedelta(minutes=5)
                window_end = (closed_at or opened_at) + timedelta(minutes=1)

            cursor.execute(
                """
                SELECT events.detected_at, event_types.name, events.process_name,
                       events.process_id, events.file_path
                FROM events
                JOIN event_types ON event_types.id = events.event_type_id
                WHERE events.agent_id = %s
                  AND events.detected_at BETWEEN %s AND %s
                ORDER BY events.detected_at ASC;
                """,
                (agent_id, window_start, window_end)
            )
            event_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT honeyfile_activations.detected_at, honeyfile_activations.operation,
                       honeyfiles.file_name, honeyfiles.file_hash,
                       honeyfile_activations.process_name, honeyfile_activations.process_id
                FROM honeyfile_activations
                JOIN honeyfiles ON honeyfiles.id = honeyfile_activations.honeyfile_id
                WHERE honeyfile_activations.agent_id = %s
                  AND honeyfile_activations.detected_at BETWEEN %s AND %s
                ORDER BY honeyfile_activations.detected_at ASC;
                """,
                (agent_id, window_start, window_end)
            )
            honeyfile_rows = cursor.fetchall()

    finally:
        connection.close()

    # --- Armado del PDF ---

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="AlfaTitle", parent=styles["Title"], fontSize=18, spaceAfter=4))
    styles.add(ParagraphStyle(name="AlfaSubtitle", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#6b7280"), spaceAfter=14))
    styles.add(ParagraphStyle(name="AlfaSection", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#111827")))
    styles.add(ParagraphStyle(name="AlfaNote", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#6b7280"), spaceAfter=6))

    code = f"INC-{inc_id:05d}"
    story = []

    story.append(Paragraph(f"ALFA-Sentinel &mdash; Reporte de Incidente {code}", styles["AlfaTitle"]))
    story.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {user.get('full_name', user.get('email', 'usuario'))}",
        styles["AlfaSubtitle"]
    ))

    # 1. Ficha del incidente
    story.append(Paragraph("1. Ficha del Incidente", styles["AlfaSection"]))
    ficha_data = [
        ["ID", code],
        ["Título", title_val],
        ["Estado", INCIDENT_STATUS_LABELS_ES.get(status, status)],
        ["Clasificación", INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "Sin clasificar")],
        ["Endpoint", f"{ep_hostname} ({ep_ip}) &mdash; {ep_os or 'SO no disponible'}"],
        ["Responsable", assigned_to_name or "Sin asignar"],
        ["Abierto", opened_at.strftime("%d/%m/%Y %H:%M:%S")],
        ["Cerrado", closed_at.strftime("%d/%m/%Y %H:%M:%S") if closed_at else "Sigue abierto"],
    ]
    if description_val:
        ficha_data.append(["Descripción", description_val])
    story.append(_alfa_kv_table([[Paragraph(str(k), styles["Normal"]), Paragraph(str(v), styles["Normal"])] for k, v in ficha_data]))

    # 2. Impacto
    story.append(Paragraph("2. Impacto", styles["AlfaSection"]))
    honeyfiles_involved = sorted({(r[2], r[3]) for r in honeyfile_rows})
    impacto_data = [
        ["Severidad máxima", ALERT_SEVERITY_LABELS_ES.get(severity, severity or "—")],
        ["Puntaje de riesgo máximo", f"{float(risk_score):.0f} / 100" if risk_score is not None else "—"],
        ["Alertas vinculadas", str(detection_count)],
        ["Honeyfiles comprometidos", str(len(honeyfiles_involved)) if honeyfiles_involved else "0"],
    ]
    story.append(_alfa_kv_table([[Paragraph(str(k), styles["Normal"]), Paragraph(str(v), styles["Normal"])] for k, v in impacto_data]))

    # 3. Reglas heurísticas disparadas
    story.append(Paragraph("3. Reglas Heurísticas Disparadas", styles["AlfaSection"]))
    if linked_alerts:
        rule_table_data = [["Alerta", "Regla", "Peso aplicado", "Fecha"]]
        for a_id, a_title, a_created, a_resolved, a_status, a_risk, a_sev, a_rule, a_weight in linked_alerts:
            rule_table_data.append([
                f"ALT-{a_id:05d}",
                ALERT_RULE_LABELS_ES.get(a_rule, a_rule) if a_rule else "Sin regla vinculada",
                f"{float(a_weight):.0f}" if a_weight is not None else "—",
                a_created.strftime("%d/%m %H:%M:%S")
            ])
        story.append(_alfa_table(rule_table_data))
    else:
        story.append(Paragraph("No hay alertas vinculadas a este incidente todavía.", styles["Normal"]))

    # 4. Traza técnica (cadena de evidencia)
    story.append(Paragraph("4. Traza Técnica (Cadena de Evidencia)", styles["AlfaSection"]))
    story.append(Paragraph(
        "Eventos y activaciones de honeyfile del mismo endpoint, en la ventana entre 5 minutos "
        "antes de la primera alerta y 1 minuto después del cierre (o de la última alerta, si "
        "sigue abierto). El agente actual no reporta proceso padre, línea de comando ni usuario "
        "ejecutor -- esos campos se marcan 'No disponible' en vez de inventarse.",
        styles["AlfaNote"]
    ))

    trace_rows = [["Fecha / hora", "Tipo", "Detalle", "Proceso"]]
    for detected_at, ev_type, proc_name, proc_id, file_path in event_rows:
        detail = file_path or "—"
        proc = f"{proc_name} (PID {proc_id})" if proc_name else "No disponible"
        trace_rows.append([
            detected_at.strftime("%d/%m %H:%M:%S"),
            EVENT_TYPE_LABELS_ES.get(ev_type, ev_type),
            Paragraph(detail, styles["Normal"]),
            proc
        ])
    for detected_at, operation, file_name, file_hash, proc_name, proc_id in honeyfile_rows:
        detail = f"Honeyfile: {file_name} &mdash; {operation}<br/>SHA-256: {file_hash or 'No disponible'}"
        proc = f"{proc_name} (PID {proc_id})" if proc_name else "No disponible"
        trace_rows.append([
            detected_at.strftime("%d/%m %H:%M:%S"),
            "Honeyfile activado",
            Paragraph(detail, styles["Normal"]),
            proc
        ])
    trace_rows[1:] = sorted(trace_rows[1:], key=lambda r: r[0])

    if len(trace_rows) > 1:
        story.append(_alfa_table(trace_rows, col_widths=[2.6 * cm, 3 * cm, 7.2 * cm, 3.5 * cm]))
    else:
        story.append(Paragraph("No se registraron eventos ni activaciones de honeyfile en la ventana evaluada.", styles["Normal"]))

    # 5. Resolución y bitácora
    story.append(Paragraph("5. Resolución y Bitácora", styles["AlfaSection"]))
    resolucion_data = [
        ["Estado final", INCIDENT_STATUS_LABELS_ES.get(status, status)],
        ["Clasificación final", INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "Sin clasificar")],
        ["Cerrado el", closed_at.strftime("%d/%m/%Y %H:%M:%S") if closed_at else "Sigue abierto"],
    ]
    story.append(_alfa_kv_table([[Paragraph(str(k), styles["Normal"]), Paragraph(str(v), styles["Normal"])] for k, v in resolucion_data]))
    story.append(Paragraph(
        "No hay historial de cambios de estado registrado para este incidente -- la base de "
        "datos guarda solo el estado actual, no cada transición con fecha y autor (pendiente, "
        "ver PENDIENTES.md, 'Historial de cambios de estado de un incidente'). Tampoco existen "
        "notas de analista guardadas en la base (ver PENDIENTES.md sobre 'incident_notes').",
        styles["AlfaNote"]
    ))

    doc.build(story)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="incidente_{code}.pdf"'}
    )


def _alfa_kv_table(data):
    """Tabla de dos columnas (campo/valor) con el mismo look en todas
    las secciones de la ficha del reporte PDF."""

    table = Table(data, colWidths=[4 * cm, 12.5 * cm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
    ]))
    return table


def _alfa_table(data, col_widths=None):
    """Tabla con encabezado (primera fila) para listas dentro del
    reporte PDF -- reglas disparadas, cadena de evidencia."""

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    return table


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
             agent_id, hostname, detection_count, severity, risk_score,
             assigned_to, assigned_to_name) = row

            cursor.execute(
                """
                SELECT endpoints.os, endpoints.ip_address, agents.status, agents.last_seen_at
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,)
            )
            agent_row = cursor.fetchone()
            operating_system, ip_address, agent_status, last_seen_at = agent_row

            stale_seconds = get_agent_stale_seconds(cursor)

            if agent_status != "ONLINE":
                agent_status_bucket = "offline"
            elif last_seen_at and (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() <= stale_seconds:
                agent_status_bucket = "ok"
            else:
                agent_status_bucket = "attention"

            # Detecciones vinculadas -- ahora vía alerts.incident_id
            # directo (antes: tabla puente incident_alerts). El nombre
            # de la regla sale de alert_rule/heuristic_rules.
            cursor.execute(
                """
                SELECT alerts.id, severity_levels.name, alerts.title, alerts.status,
                       alerts.created_at, heuristic_rules.name
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                WHERE alerts.incident_id = %s
                ORDER BY alerts.created_at ASC;
                """,
                (incident_id,)
            )

            linked_alert_rows = cursor.fetchall()

            # Detecciones del mismo endpoint que todavía se podrían
            # vincular a este incidente: cualquier alerta que no esté
            # YA en este incidente (puede estar libre o en otro caso).
            cursor.execute(
                """
                SELECT alerts.id, alerts.title, severity_levels.name, alerts.created_at
                FROM alerts
                JOIN severity_levels ON severity_levels.id = alerts.severity_id
                WHERE alerts.agent_id = %s
                  AND alerts.incident_id IS DISTINCT FROM %s
                ORDER BY alerts.created_at DESC
                LIMIT 20;
                """,
                (agent_id, incident_id)
            )

            linkable_alert_rows = cursor.fetchall()

    finally:
        connection.close()

    # "Notas del incidente" (incident_notes) sigue sin existir -- ver
    # PENDIENTES.md. "Responsable" (assigned_to/assigned_at) se
    # reintrodujo 2026-08-12.
    notes = []

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, full_name FROM users ORDER BY full_name;")
            assignable_users = [{"id": r[0], "full_name": r[1]} for r in cursor.fetchall()]
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
    if closed_at:
        classification_label = INCIDENT_CLASSIFICATION_LABELS_ES.get(classification, "sin clasificar")
        timeline.append({"at": closed_at, "label": f"Incidente cerrado ({classification_label})"})
    timeline.sort(key=lambda item: item["at"])

    # 'incidents' sigue sin 'updated_at'/'alert_id'/'closed_by' -- no
    # existen en la nueva estructura, ver PENDIENTES.md.
    # 'assigned_to'/'assigned_at' sí, reintroducidos 2026-08-12.
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
        "agent_id": agent_id,
        "hostname": hostname,
        "operating_system": operating_system,
        "ip_address": ip_address,
        "agent_status_bucket": agent_status_bucket,
        "detection_count": detection_count,
        "severity": severity,
        "severity_label": ALERT_SEVERITY_LABELS_ES.get(severity, severity or "—"),
        "risk_score": risk_score,
        "assigned_to": assigned_to,
        "assigned_to_name": assigned_to_name
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


def _alfa_styles():
    """Hoja de estilos compartida por los generadores de PDF de
    /reportes (mismo look que el reporte de un incidente puntual,
    /incidentes/{id}/reporte.pdf)."""

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="AlfaTitle", parent=styles["Title"], fontSize=18, spaceAfter=4))
    styles.add(ParagraphStyle(name="AlfaSubtitle", parent=styles["Normal"], fontSize=9.5, textColor=colors.HexColor("#6b7280"), spaceAfter=16))
    styles.add(ParagraphStyle(name="AlfaSection", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#111827")))
    styles.add(ParagraphStyle(name="AlfaNote", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#6b7280"), spaceAfter=10))
    return styles


def _xlsx_section(ws, title, headers, rows):
    """Sección repetible dentro de una hoja de cálculo de /reportes:
    título en negrita, encabezado opcional (para tablas) y filas de
    datos, seguidos de una fila en blanco de separación."""

    ws.append([title])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

    if headers:
        ws.append(headers)
        header_row = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="111827", end_color="111827", fill_type="solid")

    for r in rows:
        ws.append(r)

    ws.append([])


# --- Recolección de datos (una función por tipo de informe) ---
# Todas devuelven solo lo que sale de una consulta real -- ninguna
# arma "proceso ejecutado", "línea de comando" ni hashes que el agente
# no reporta hoy (ver PENDIENTES.md, "Atribución de proceso en
# eventos de archivo").

def _gather_security_report_data(cursor, start, end, endpoint_id):
    params = {"start": start, "end": end}
    ep_filter = ""
    hf_filter = ""
    if endpoint_id:
        ep_filter = "AND endpoints.id = %(endpoint_id)s"
        hf_filter = "AND agents.endpoint_id = %(endpoint_id)s"
        params["endpoint_id"] = endpoint_id

    cursor.execute(
        f"""
        SELECT severity_levels.name, COUNT(*)
        FROM alerts
        JOIN severity_levels ON severity_levels.id = alerts.severity_id
        JOIN agents ON agents.id = alerts.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE alerts.created_at BETWEEN %(start)s AND %(end)s
        {ep_filter}
        GROUP BY severity_levels.name;
        """,
        params
    )
    severity_counts = dict(cursor.fetchall())

    cursor.execute(
        f"""
        SELECT incidents.status, COUNT(*)
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE incidents.opened_at BETWEEN %(start)s AND %(end)s
        {ep_filter}
        GROUP BY incidents.status;
        """,
        params
    )
    incident_status_counts = dict(cursor.fetchall())

    cursor.execute(
        f"""
        SELECT incidents.classification, COUNT(*)
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE incidents.opened_at BETWEEN %(start)s AND %(end)s
          AND incidents.classification IS NOT NULL
        {ep_filter}
        GROUP BY incidents.classification;
        """,
        params
    )
    classification_counts = dict(cursor.fetchall())

    cursor.execute(
        f"""
        SELECT heuristic_rules.name, COUNT(*)
        FROM alert_rule
        JOIN alerts ON alerts.id = alert_rule.alert_id
        JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
        JOIN agents ON agents.id = alerts.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE alerts.created_at BETWEEN %(start)s AND %(end)s
        {ep_filter}
        GROUP BY heuristic_rules.name
        ORDER BY COUNT(*) DESC;
        """,
        params
    )
    rule_counts = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE honeyfiles.status = 'ACTIVE'),
            COUNT(*) FILTER (WHERE honeyfiles.status = 'TRIGGERED'),
            COUNT(*)
        FROM honeyfiles
        JOIN agents ON agents.id = honeyfiles.agent_id
        WHERE 1=1 {hf_filter};
        """,
        params
    )
    hf_active, hf_triggered, hf_total = cursor.fetchone()

    cursor.execute(
        f"""
        SELECT AVG(EXTRACT(EPOCH FROM (alerts.resolved_at - alerts.created_at)))
        FROM alerts
        JOIN agents ON agents.id = alerts.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE alerts.resolved_at IS NOT NULL
          AND alerts.created_at BETWEEN %(start)s AND %(end)s
        {ep_filter};
        """,
        params
    )
    avg_resolution_seconds = cursor.fetchone()[0]

    return {
        "severity_counts": severity_counts,
        "total_alerts": sum(severity_counts.values()),
        "incident_status_counts": incident_status_counts,
        "total_incidents": sum(incident_status_counts.values()),
        "classification_counts": classification_counts,
        "rule_counts": rule_counts,
        "honeyfiles_active": hf_active or 0,
        "honeyfiles_triggered": hf_triggered or 0,
        "honeyfiles_total": hf_total or 0,
        "avg_resolution_seconds": float(avg_resolution_seconds) if avg_resolution_seconds is not None else None,
    }


def _gather_endpoints_report_data(cursor, start, end, endpoint_id):
    params = {"start": start, "end": end}
    ep_filter = ""
    if endpoint_id:
        ep_filter = "AND endpoints.id = %(endpoint_id)s"
        params["endpoint_id"] = endpoint_id

    stale_seconds = get_agent_stale_seconds(cursor)

    # 'is_online' se calcula en SQL (CURRENT_TIMESTAMP, con el mismo
    # criterio que _endpoint_cte() en /endpoints) y no en Python --
    # restar 'datetime.now()' (naive) de 'agents.last_seen_at'
    # (TIMESTAMPTZ, llega con tz desde psycopg) revienta con "can't
    # subtract offset-naive and offset-aware datetimes" apenas hay un
    # agente ONLINE real con last_seen_at seteado. El mismo bug late
    # en get_incidente_drawer -- corregido ahí también.
    cursor.execute(
        f"""
        SELECT endpoints.hostname, endpoints.ip_address, endpoints.os,
               agents.status,
               (
                   agents.status = 'ONLINE'
                   AND agents.last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '{stale_seconds} seconds'
               ) AS is_online,
               (
                   SELECT COUNT(*) FROM events
                   WHERE events.agent_id = agents.id
                     AND events.detected_at BETWEEN %(start)s AND %(end)s
               ) AS event_count,
               (
                   SELECT COUNT(*) FROM honeyfiles
                   WHERE honeyfiles.agent_id = agents.id
               ) AS honeyfiles_deployed,
               (
                   SELECT COUNT(*) FROM agent_honeyfile_templates
                   WHERE agent_honeyfile_templates.agent_id = agents.id
                     AND agent_honeyfile_templates.status = 'PENDING'
               ) AS honeyfiles_pending
        FROM agents
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        WHERE 1=1 {ep_filter}
        ORDER BY endpoints.hostname ASC;
        """,
        params
    )
    rows = cursor.fetchall()

    endpoints_data = []
    for hostname, ip, os_name, status, is_online, event_count, hf_deployed, hf_pending in rows:
        status_label = "En línea" if is_online else ("Sin señal reciente" if status == "ONLINE" else "Desconectado")
        endpoints_data.append({
            "hostname": hostname,
            "ip_address": str(ip) if ip else "—",
            "os": os_name,
            "is_online": is_online,
            "status_label": status_label,
            "event_count": event_count,
            "honeyfiles_deployed": hf_deployed,
            "honeyfiles_pending": hf_pending
        })

    return {
        "endpoints": endpoints_data,
        "total_endpoints": len(endpoints_data),
        "online_count": sum(1 for e in endpoints_data if e["is_online"]),
        "total_events": sum(e["event_count"] for e in endpoints_data),
    }


def _gather_incidents_report_data(cursor, start, end, endpoint_id):
    params = {"start": start, "end": end}
    ep_filter = ""
    if endpoint_id:
        ep_filter = "AND endpoints.id = %(endpoint_id)s"
        params["endpoint_id"] = endpoint_id

    cursor.execute(
        f"""
        SELECT incidents.id, incidents.title, incidents.status, incidents.classification,
               incidents.opened_at, incidents.closed_at, endpoints.hostname,
               assigned_user.full_name,
               (
                   SELECT COALESCE(MAX(alerts.risk_score), 0) FROM alerts
                   WHERE alerts.incident_id = incidents.id
               ) AS risk_score,
               (
                   SELECT STRING_AGG(DISTINCT heuristic_rules.name, ' + ') FROM alerts
                   LEFT JOIN alert_rule ON alert_rule.alert_id = alerts.id
                   LEFT JOIN heuristic_rules ON heuristic_rules.id = alert_rule.rule_id
                   WHERE alerts.incident_id = incidents.id
               ) AS rule_names,
               (
                   SELECT COUNT(*) FROM alerts WHERE alerts.incident_id = incidents.id
               ) AS alert_count
        FROM incidents
        JOIN agents ON agents.id = incidents.agent_id
        JOIN endpoints ON endpoints.id = agents.endpoint_id
        LEFT JOIN users AS assigned_user ON assigned_user.id = incidents.assigned_to
        WHERE incidents.opened_at BETWEEN %(start)s AND %(end)s
        {ep_filter}
        ORDER BY incidents.opened_at DESC;
        """,
        params
    )
    rows = cursor.fetchall()

    incidents_data = [
        {
            "id": r[0], "code": f"INC-{r[0]:05d}", "title": r[1],
            "status": r[2], "status_label": INCIDENT_STATUS_LABELS_ES.get(r[2], r[2]),
            "classification_label": INCIDENT_CLASSIFICATION_LABELS_ES.get(r[3], "Sin clasificar"),
            "opened_at": r[4], "closed_at": r[5], "hostname": r[6],
            "assigned_to_name": r[7] or "Sin asignar", "risk_score": float(r[8]),
            "rule_label": ALERT_RULE_LABELS_ES.get(r[9], r[9]) if r[9] else "Sin regla vinculada",
            "alert_count": r[10]
        }
        for r in rows
    ]

    return {
        "incidents": incidents_data,
        "total_incidents": len(incidents_data),
        "closed_count": sum(1 for i in incidents_data if i["status"] == "CLOSED"),
        "open_count": sum(1 for i in incidents_data if i["status"] != "CLOSED"),
    }


REPORT_DATA_GATHERERS = {
    "SECURITY": _gather_security_report_data,
    "ENDPOINTS": _gather_endpoints_report_data,
    "INCIDENTS": _gather_incidents_report_data,
}


# --- Generadores de PDF (reportlab) ---

def _build_security_pdf(data, meta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _alfa_styles()
    story = [Paragraph(f"ALFA-Sentinel &mdash; {meta['title']}", styles["AlfaTitle"]), Paragraph(meta["subtitle"], styles["AlfaSubtitle"])]

    story.append(Paragraph("1. Resumen de Alertas por Severidad", styles["AlfaSection"]))
    sev_rows = [["Severidad", "Cantidad"]]
    for key in ("CRITICAL", "HIGH", "SUSPICIOUS"):
        sev_rows.append([ALERT_SEVERITY_LABELS_ES.get(key, key), str(data["severity_counts"].get(key, 0))])
    sev_rows.append(["Total", str(data["total_alerts"])])
    story.append(_alfa_table(sev_rows))

    story.append(Paragraph("2. Incidentes por Estado", styles["AlfaSection"]))
    if data["incident_status_counts"]:
        inc_rows = [["Estado", "Cantidad"]] + [[INCIDENT_STATUS_LABELS_ES.get(s, s), str(n)] for s, n in data["incident_status_counts"].items()]
        story.append(_alfa_table(inc_rows))
    else:
        story.append(Paragraph("No se abrieron incidentes en el período evaluado.", styles["Normal"]))

    if data["classification_counts"]:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Clasificación de los incidentes cerrados en el período:", styles["Normal"]))
        cls_rows = [["Clasificación", "Cantidad"]] + [[INCIDENT_CLASSIFICATION_LABELS_ES.get(c, c), str(n)] for c, n in data["classification_counts"].items()]
        story.append(_alfa_table(cls_rows))

    story.append(Paragraph("3. Reglas Heurísticas Más Activas", styles["AlfaSection"]))
    if data["rule_counts"]:
        rule_rows = [["Regla", "Alertas disparadas"]] + [[ALERT_RULE_LABELS_ES.get(name, name or "Sin regla vinculada"), str(n)] for name, n in data["rule_counts"]]
        story.append(_alfa_table(rule_rows))
    else:
        story.append(Paragraph("No hubo alertas en el período evaluado.", styles["Normal"]))

    story.append(Paragraph("4. Cobertura de Honeyfiles", styles["AlfaSection"]))
    coverage_pct = round((data["honeyfiles_active"] + data["honeyfiles_triggered"]) / data["honeyfiles_total"] * 100, 1) if data["honeyfiles_total"] else 0
    hf_kv = [
        ["Honeyfiles desplegados", str(data["honeyfiles_total"])],
        ["Activos (intactos)", str(data["honeyfiles_active"])],
        ["Activados (comprometidos)", str(data["honeyfiles_triggered"])],
        ["Cobertura operativa", f"{coverage_pct}%"],
    ]
    story.append(_alfa_kv_table([[Paragraph(k, styles["Normal"]), Paragraph(v, styles["Normal"])] for k, v in hf_kv]))

    story.append(Paragraph("5. Tiempo de Resolución", styles["AlfaSection"]))
    if data["avg_resolution_seconds"] is not None:
        minutes = round(data["avg_resolution_seconds"] / 60, 1)
        story.append(Paragraph(f"Tiempo promedio de resolución de alertas en el período: {minutes} minutos.", styles["Normal"]))
    else:
        story.append(Paragraph("Sin datos aún -- no hay alertas resueltas en el período evaluado.", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _build_endpoints_pdf(data, meta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _alfa_styles()
    story = [Paragraph(f"ALFA-Sentinel &mdash; {meta['title']}", styles["AlfaTitle"]), Paragraph(meta["subtitle"], styles["AlfaSubtitle"])]

    story.append(Paragraph("1. Resumen", styles["AlfaSection"]))
    resumen = [
        ["Endpoints evaluados", str(data["total_endpoints"])],
        ["En línea al momento de generar", str(data["online_count"])],
        ["Eventos totales en el período", str(data["total_events"])],
    ]
    story.append(_alfa_kv_table([[Paragraph(k, styles["Normal"]), Paragraph(v, styles["Normal"])] for k, v in resumen]))

    story.append(Paragraph("2. Detalle por Endpoint", styles["AlfaSection"]))
    if data["endpoints"]:
        rows = [["Endpoint", "SO", "Conectividad", "Eventos", "Honeyfiles (desplegados / pendientes)"]]
        for ep in data["endpoints"]:
            rows.append([
                Paragraph(f"{ep['hostname']}<br/>{ep['ip_address']}", styles["Normal"]),
                ep["os"] or "—", ep["status_label"], str(ep["event_count"]),
                f"{ep['honeyfiles_deployed']} / {ep['honeyfiles_pending']}"
            ])
        story.append(_alfa_table(rows, col_widths=[4.5 * cm, 2.3 * cm, 3 * cm, 2 * cm, 4.5 * cm]))
    else:
        story.append(Paragraph("No hay endpoints registrados que coincidan con el filtro.", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _build_incidents_pdf(data, meta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _alfa_styles()
    story = [Paragraph(f"ALFA-Sentinel &mdash; {meta['title']}", styles["AlfaTitle"]), Paragraph(meta["subtitle"], styles["AlfaSubtitle"])]

    story.append(Paragraph(
        "Este informe es un resumen de auditoría de los incidentes abiertos en el período -- no "
        "incluye la traza técnica completa de cada uno (proceso, hashes, cadena de evidencia). "
        "Para el detalle forense de un incidente puntual, usar su Reporte PDF individual desde el "
        "Expediente en Incidentes y Alertas.",
        styles["AlfaNote"]
    ))

    story.append(Paragraph("1. Resumen", styles["AlfaSection"]))
    resumen = [
        ["Incidentes en el período", str(data["total_incidents"])],
        ["Cerrados", str(data["closed_count"])],
        ["Abiertos / en curso", str(data["open_count"])],
    ]
    story.append(_alfa_kv_table([[Paragraph(k, styles["Normal"]), Paragraph(v, styles["Normal"])] for k, v in resumen]))

    story.append(Paragraph("2. Detalle de Incidentes", styles["AlfaSection"]))
    if data["incidents"]:
        rows = [["ID", "Título", "Endpoint", "Regla", "Estado", "Responsable", "Abierto"]]
        for inc in data["incidents"]:
            rows.append([
                inc["code"], Paragraph(inc["title"], styles["Normal"]), inc["hostname"],
                inc["rule_label"], inc["status_label"], inc["assigned_to_name"],
                inc["opened_at"].strftime("%d/%m/%Y")
            ])
        story.append(_alfa_table(rows, col_widths=[2 * cm, 4 * cm, 2.7 * cm, 3 * cm, 2.3 * cm, 2.5 * cm, 2 * cm]))
    else:
        story.append(Paragraph("No se abrieron incidentes en el período evaluado.", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


# --- Generadores de XLSX (openpyxl) ---

def _build_security_xlsx(data, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Seguridad"
    ws.append([meta["title"]])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([meta["subtitle"]])
    ws.append([])

    sev_rows = [[ALERT_SEVERITY_LABELS_ES.get(k, k), data["severity_counts"].get(k, 0)] for k in ("CRITICAL", "HIGH", "SUSPICIOUS")]
    sev_rows.append(["Total", data["total_alerts"]])
    _xlsx_section(ws, "Alertas por severidad", ["Severidad", "Cantidad"], sev_rows)

    inc_rows = [[INCIDENT_STATUS_LABELS_ES.get(s, s), n] for s, n in data["incident_status_counts"].items()]
    _xlsx_section(ws, "Incidentes por estado", ["Estado", "Cantidad"], inc_rows or [["Sin incidentes en el período", ""]])

    if data["classification_counts"]:
        cls_rows = [[INCIDENT_CLASSIFICATION_LABELS_ES.get(c, c), n] for c, n in data["classification_counts"].items()]
        _xlsx_section(ws, "Clasificación de incidentes cerrados", ["Clasificación", "Cantidad"], cls_rows)

    rule_rows = [[ALERT_RULE_LABELS_ES.get(name, name or "Sin regla vinculada"), n] for name, n in data["rule_counts"]]
    _xlsx_section(ws, "Reglas más activas", ["Regla", "Alertas disparadas"], rule_rows or [["Sin alertas en el período", ""]])

    coverage_pct = round((data["honeyfiles_active"] + data["honeyfiles_triggered"]) / data["honeyfiles_total"] * 100, 1) if data["honeyfiles_total"] else 0
    hf_rows = [
        ["Honeyfiles desplegados", data["honeyfiles_total"]],
        ["Activos (intactos)", data["honeyfiles_active"]],
        ["Activados (comprometidos)", data["honeyfiles_triggered"]],
        ["Cobertura operativa (%)", coverage_pct],
    ]
    _xlsx_section(ws, "Cobertura de honeyfiles", None, hf_rows)

    minutes = round(data["avg_resolution_seconds"] / 60, 1) if data["avg_resolution_seconds"] is not None else "Sin datos aún"
    _xlsx_section(ws, "Tiempo de resolución", None, [["Promedio (minutos)", minutes]])

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 32

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _build_endpoints_xlsx(data, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Endpoints"
    ws.append([meta["title"]])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([meta["subtitle"]])
    ws.append([])

    resumen_rows = [
        ["Endpoints evaluados", data["total_endpoints"]],
        ["En línea al momento de generar", data["online_count"]],
        ["Eventos totales en el período", data["total_events"]],
    ]
    _xlsx_section(ws, "Resumen", None, resumen_rows)

    ep_rows = [
        [ep["hostname"], ep["ip_address"], ep["os"] or "—", ep["status_label"], ep["event_count"], ep["honeyfiles_deployed"], ep["honeyfiles_pending"]]
        for ep in data["endpoints"]
    ]
    _xlsx_section(
        ws, "Detalle por endpoint",
        ["Endpoint", "IP", "SO", "Conectividad", "Eventos", "Honeyfiles desplegados", "Honeyfiles pendientes"],
        ep_rows or [["Sin endpoints que coincidan con el filtro", "", "", "", "", "", ""]]
    )

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _build_incidents_xlsx(data, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Incidentes"
    ws.append([meta["title"]])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([meta["subtitle"]])
    ws.append(["Resumen de auditoría -- para traza forense completa de un incidente puntual, usar su Reporte PDF individual."])
    ws.append([])

    resumen_rows = [
        ["Incidentes en el período", data["total_incidents"]],
        ["Cerrados", data["closed_count"]],
        ["Abiertos / en curso", data["open_count"]],
    ]
    _xlsx_section(ws, "Resumen", None, resumen_rows)

    inc_rows = [
        [
            inc["code"], inc["title"], inc["hostname"], inc["rule_label"], inc["status_label"],
            inc["classification_label"], inc["assigned_to_name"],
            inc["opened_at"].strftime("%d/%m/%Y %H:%M"),
            inc["closed_at"].strftime("%d/%m/%Y %H:%M") if inc["closed_at"] else "Sigue abierto",
            inc["risk_score"]
        ]
        for inc in data["incidents"]
    ]
    _xlsx_section(
        ws, "Detalle de incidentes",
        ["ID", "Título", "Endpoint", "Regla", "Estado", "Clasificación", "Responsable", "Abierto", "Cerrado", "Riesgo máx."],
        inc_rows or [["Sin incidentes en el período", "", "", "", "", "", "", "", "", ""]]
    )

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


REPORT_BUILDERS = {
    ("SECURITY", "PDF"): _build_security_pdf,
    ("SECURITY", "XLSX"): _build_security_xlsx,
    ("ENDPOINTS", "PDF"): _build_endpoints_pdf,
    ("ENDPOINTS", "XLSX"): _build_endpoints_xlsx,
    ("INCIDENTS", "PDF"): _build_incidents_pdf,
    ("INCIDENTS", "XLSX"): _build_incidents_xlsx,
}


@app.post("/reportes/generar")
def generar_reporte(payload: ReportGenerate, user: dict = Depends(get_current_user)):
    """Genera el informe en el momento (PDF con reportlab o XLSX con
    openpyxl), lo guarda en disco (server/generated_reports/, no en la
    base -- ver comentario en 'reports' en database/schema.sql) e
    inserta la fila de auditoría. 'generated_by' siempre es quien tiene
    la sesión activa; no existe generación automática/por sistema hoy."""

    if payload.report_type not in REPORT_TYPE_LABELS_ES:
        raise HTTPException(status_code=422, detail=f"Tipo de informe desconocido: '{payload.report_type}'")

    if payload.format not in ("PDF", "XLSX"):
        raise HTTPException(status_code=422, detail=f"Formato desconocido: '{payload.format}'")

    start, end, period_label = _resolve_report_period(payload.period)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            endpoint_hostname = None
            if payload.endpoint_id is not None:
                cursor.execute("SELECT hostname FROM endpoints WHERE id = %s;", (payload.endpoint_id,))
                ep_row = cursor.fetchone()
                if ep_row is None:
                    raise HTTPException(status_code=404, detail="Endpoint no encontrado")
                endpoint_hostname = ep_row[0]

            data = REPORT_DATA_GATHERERS[payload.report_type](cursor, start, end, payload.endpoint_id)

            type_label = REPORT_TYPE_LABELS_ES[payload.report_type]
            title = f"{type_label} - {period_label}"
            if endpoint_hostname:
                title += f" - {endpoint_hostname}"

            subtitle = (
                f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {user.get('full_name', 'usuario')} "
                f"&mdash; Período evaluado: {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')} "
                f"&mdash; {('Endpoint: ' + endpoint_hostname) if endpoint_hostname else 'Todos los endpoints'}"
            )
            meta = {"title": title, "subtitle": subtitle}

            buffer = REPORT_BUILDERS[(payload.report_type, payload.format)](data, meta)

            cursor.execute(
                """
                INSERT INTO reports (
                    title, report_type, format, period_label,
                    start_date, end_date, endpoint_id, generated_by, file_path
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (title, payload.report_type, payload.format, period_label,
                 start, end, payload.endpoint_id, user["id"], "")
            )
            report_id, created_at = cursor.fetchone()

            os.makedirs(REPORTS_DIR, exist_ok=True)
            ext = "pdf" if payload.format == "PDF" else "xlsx"
            code = f"REP-{created_at.year}-{report_id:04d}"
            file_path = os.path.join(REPORTS_DIR, f"{code}.{ext}")

            with open(file_path, "wb") as f:
                f.write(buffer.getvalue())

            cursor.execute("UPDATE reports SET file_path = %s WHERE id = %s;", (file_path, report_id))

            connection.commit()

    finally:
        connection.close()

    return {
        "message": "Informe generado",
        "report": {
            "id": report_id,
            "code": code,
            "title": title,
            "report_type_label": type_label,
            "format": payload.format,
            "period_label": period_label,
            "endpoint": endpoint_hostname or "Todos los endpoints",
            "generated_by": user.get("full_name", "usuario"),
            "created_at": created_at.strftime("%d/%m/%Y %H:%M")
        }
    }


@app.get("/reportes")
def reportes_page(request: Request, page: int = Query(1, ge=1)):
    """Reemplaza el placeholder anterior (2026-08-12): página real de
    generación y auditoría de informes, respaldada por la tabla
    'reports'."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("SELECT COUNT(*) FROM reports;")
            total_reports = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT reports.created_at, users.full_name
                FROM reports
                LEFT JOIN users ON users.id = reports.generated_by
                ORDER BY reports.created_at DESC
                LIMIT 1;
                """
            )
            last_row = cursor.fetchone()
            last_generated_at, last_generated_by = last_row if last_row else (None, None)

            cursor.execute("SELECT id, hostname FROM endpoints ORDER BY hostname;")
            endpoint_options = cursor.fetchall()

            page_size = 20
            total_pages = max(1, -(-total_reports // page_size))
            current_page = min(page, total_pages)
            offset = (current_page - 1) * page_size

            cursor.execute(
                """
                SELECT reports.id, reports.title, reports.report_type, reports.format,
                       reports.period_label, reports.created_at, endpoints.hostname,
                       users.full_name
                FROM reports
                LEFT JOIN endpoints ON endpoints.id = reports.endpoint_id
                LEFT JOIN users ON users.id = reports.generated_by
                ORDER BY reports.created_at DESC
                LIMIT %s OFFSET %s;
                """,
                (page_size, offset)
            )
            rows = cursor.fetchall()

    finally:
        connection.close()

    history = [
        {
            "id": r[0],
            "code": f"REP-{r[5].year}-{r[0]:04d}",
            "title": r[1],
            "report_type_label": REPORT_TYPE_LABELS_ES.get(r[2], r[2]),
            "format": r[3],
            "period_label": r[4],
            "created_at": r[5],
            "endpoint": r[6] or "Todos los endpoints",
            "generated_by": r[7] or "Usuario eliminado"
        }
        for r in rows
    ]

    return templates.TemplateResponse(
        request,
        "reportes.html",
        {
            "user": user,
            "active_page": "reportes",
            "total_reports": total_reports,
            "last_generated_at": last_generated_at,
            "last_generated_by": last_generated_by,
            "endpoint_options": endpoint_options,
            "report_type_options": list(REPORT_TYPE_LABELS_ES.items()),
            "period_options": REPORT_PERIOD_OPTIONS,
            "history": history,
            "current_page": current_page,
            "total_pages": total_pages
        }
    )


@app.get("/reportes/{report_id}/archivo")
def descargar_reporte(report_id: int, request: Request, disposition: str = Query("attachment")):
    """Sirve el archivo ya generado y guardado en disco -- no regenera
    con datos más nuevos, para que la copia descargada sea siempre la
    misma que quedó auditada en 'reports' en el momento de generarla."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    if disposition not in ("inline", "attachment"):
        disposition = "attachment"

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT format, file_path, created_at FROM reports WHERE id = %s;",
                (report_id,)
            )
            row = cursor.fetchone()

    finally:
        connection.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    fmt, file_path, created_at = row

    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="El archivo de este informe ya no está disponible en el servidor.")

    with open(file_path, "rb") as f:
        content = f.read()

    ext = "pdf" if fmt == "PDF" else "xlsx"
    code = f"REP-{created_at.year}-{report_id:04d}"

    return Response(
        content=content,
        media_type=REPORT_FORMAT_MEDIA_TYPES.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'{disposition}; filename="{code}.{ext}"'}
    )


# Etiquetas de 'audit_logs.action' -- strings libres a propósito
# (columna VARCHAR sin CHECK), cada endpoint que llama a log_audit()
# manda el código que quiere; este diccionario solo traduce lo que ya
# se está mandando hoy. Una acción que llegue sin traducción se
# muestra tal cual (nunca se oculta una fila de auditoría por no
# tener label).
AUDIT_ACTION_LABELS_ES = {
    "UPDATE_RULE": "Regla heurística modificada",
    "UPDATE_SETTING": "Parámetro global modificado",
    "CREATE_USER": "Usuario creado",
    "UPDATE_USER": "Usuario modificado",
    "ASSIGN_INCIDENT": "Responsable asignado",
    "UNASSIGN_INCIDENT": "Responsable removido",
    "UPDATE_INCIDENT_STATUS": "Estado de incidente cambiado",
    "UPDATE_ALERT_STATUS": "Estado de alerta cambiado",
}

CONFIGURACION_AUDIT_PAGE_SIZE = 30


@app.get("/configuracion")
def configuracion_page(
    request: Request,
    tab: str = Query("deteccion"),
    sub: str = Query("reglas"),
    page: int = Query(1, ge=1)
):
    """Reescrita 2026-08-12 con 4 pestañas (Detección, Agentes,
    Auditoría, más el link a /usuarios para Usuarios y Roles) sobre el
    mismo route -- 'tab'/'sub' deciden qué bloque de datos se arma,
    todo dentro de una sola página para no fragmentar la navegación
    de Configuración en rutas sueltas.

    Reglas Heurísticas: solo 'weight' e 'is_active' se muestran
    editables porque son los únicos campos que el sistema realmente
    consume después (ver comentario en PATCH /rules/{rule_id}).
    Severidades: de solo lectura -- el agente tiene su propia copia
    hardcodeada de estos rangos y no consulta la base, así que
    editarlos acá no cambiaría la clasificación real (ver
    PENDIENTES.md). Agentes: 'agent_stale_seconds' es el único
    parámetro real; heartbeat/sincronización de reglas se muestran
    como no aplicables, no como campos editables, porque no existe
    ningún mecanismo que los consuma. Auditoría: 'audit_logs' real,
    poblada desde 2026-08-12 por log_audit()."""

    user = require_session_user(request)

    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    tab = tab if tab in ("deteccion", "agentes", "auditoria") else "deteccion"
    sub = sub if sub in ("reglas", "severidades") else "reglas"

    context = {
        "user": user,
        "active_page": "configuracion",
        "tab": tab,
        "sub": sub,
        "rules": [],
        "severities": [],
        "agent_stale_seconds": None,
        "audit_entries": [],
        "audit_total": 0,
        "current_page": 1,
        "total_pages": 1
    }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            if tab == "deteccion" and sub == "reglas":

                cursor.execute(
                    """
                    SELECT
                        heuristic_rules.id,
                        heuristic_rules.name,
                        heuristic_rules.description,
                        heuristic_rules.weight,
                        heuristic_rules.threshold,
                        heuristic_rules.window_seconds,
                        heuristic_rules.is_active,
                        heuristic_rules.updated_at,
                        event_types.name,
                        (
                            SELECT COUNT(*)
                            FROM alert_rule
                            JOIN alerts ON alerts.id = alert_rule.alert_id
                            WHERE alert_rule.rule_id = heuristic_rules.id
                              AND alerts.created_at >= NOW() - INTERVAL '30 days'
                        ) AS alerts_30d,
                        (
                            SELECT MAX(alerts.created_at)
                            FROM alert_rule
                            JOIN alerts ON alerts.id = alert_rule.alert_id
                            WHERE alert_rule.rule_id = heuristic_rules.id
                        ) AS last_triggered_at
                    FROM heuristic_rules
                    LEFT JOIN event_types ON event_types.id = heuristic_rules.event_type_id
                    ORDER BY heuristic_rules.weight DESC, heuristic_rules.name ASC;
                    """
                )

                rows = cursor.fetchall()

                context["rules"] = [
                    {
                        "id": r[0],
                        "name": r[1],
                        "label": ALERT_RULE_LABELS_ES.get(r[1], r[1]),
                        "description": r[2],
                        "weight": float(r[3]),
                        "threshold": float(r[4]),
                        "window_seconds": r[5],
                        "is_active": r[6],
                        "updated_at": r[7],
                        "event_type_label": EVENT_TYPE_LABELS_ES.get(r[8], r[8]) if r[8] else "Cualquiera en la ventana",
                        "alerts_30d": r[9],
                        "last_triggered_at": r[10]
                    }
                    for r in rows
                ]

            elif tab == "deteccion" and sub == "severidades":

                cursor.execute(
                    "SELECT name, min_score, max_score FROM severity_levels ORDER BY min_score;"
                )

                context["severities"] = [
                    {
                        "name": r[0],
                        "label": RISK_LABELS_ES.get(r[0], r[0]),
                        "min_score": float(r[1]),
                        "max_score": float(r[2])
                    }
                    for r in cursor.fetchall()
                ]

            elif tab == "agentes":

                context["agent_stale_seconds"] = get_agent_stale_seconds(cursor)

            elif tab == "auditoria":

                cursor.execute("SELECT COUNT(*) FROM audit_logs;")
                audit_total = cursor.fetchone()[0]

                total_pages = max(1, -(-audit_total // CONFIGURACION_AUDIT_PAGE_SIZE))
                current_page = min(page, total_pages)
                offset = (current_page - 1) * CONFIGURACION_AUDIT_PAGE_SIZE

                cursor.execute(
                    """
                    SELECT audit_logs.created_at, users.full_name, audit_logs.action,
                           audit_logs.entity_type, audit_logs.entity_id, audit_logs.description
                    FROM audit_logs
                    LEFT JOIN users ON users.id = audit_logs.user_id
                    ORDER BY audit_logs.created_at DESC
                    LIMIT %s OFFSET %s;
                    """,
                    (CONFIGURACION_AUDIT_PAGE_SIZE, offset)
                )

                context["audit_entries"] = [
                    {
                        "created_at": r[0],
                        "user_name": r[1] or "Usuario eliminado",
                        "action": r[2],
                        "action_label": AUDIT_ACTION_LABELS_ES.get(r[2], r[2]),
                        "entity_type": r[3],
                        "entity_id": r[4],
                        "description": r[5]
                    }
                    for r in cursor.fetchall()
                ]
                context["audit_total"] = audit_total
                context["current_page"] = current_page
                context["total_pages"] = total_pages

        db_error = None

    except Exception:
        db_error = "No se pudo leer la configuración -- probá de nuevo en un momento."

    finally:
        connection.close()

    context["db_error"] = db_error

    return templates.TemplateResponse(request, "configuracion.html", context)


@app.post("/agents")
def register_agent(agent: AgentCreate):
    # 'endpoints' (el host físico) y 'agents' (la instalación del
    # agente en ese host) son tablas separadas desde la reestructuración
    # a alfa_sentinel -- hay que crear una fila en cada una.

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO endpoints (hostname, os, os_version, ip_address)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (agent.hostname, agent.os, agent.os_version, agent.ip_address)
            )

            endpoint_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO agents (endpoint_id, agent_version)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (endpoint_id, agent.agent_version or "desconocido")
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
                  AND status = 'ACTIVE'
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

            # 2. Registrar el endpoint (host físico) y el agente
            # (instalación en ese host) -- son tablas separadas desde
            # la reestructuración a alfa_sentinel.
            cursor.execute(
                """
                INSERT INTO endpoints (hostname, os, os_version, ip_address)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    enrollment.hostname,
                    enrollment.os,
                    enrollment.os_version,
                    enrollment.ip_address
                )
            )

            endpoint_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO agents (endpoint_id, agent_version)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (endpoint_id, enrollment.agent_version or "desconocido")
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
                    status = 'USED'
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

            # 'events.event_type' pasó a ser 'event_type_id' (FK a la
            # tabla catálogo 'event_types'). El agente sigue mandando
            # el nombre como texto -- se traduce acá. Si no matchea
            # ningún catálogo, se rechaza en vez de guardar un evento
            # con un tipo inventado.
            cursor.execute(
                "SELECT id FROM event_types WHERE name = %s;",
                (event.event_type,)
            )

            event_type_row = cursor.fetchone()

            if event_type_row is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Tipo de evento desconocido: '{event.event_type}'"
                )

            event_type_id = event_type_row[0]

            cursor.execute(
                """
                INSERT INTO events (
                    agent_id,
                    event_type_id,
                    process_id,
                    process_name,
                    file_path
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent_id,
                    event_type_id,
                    event.process_id,
                    event.process_name,
                    (event.metadata or {}).get("file_path")
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
    'heuristic_rules' que matcheó (tabla puente 'alert_rule')."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            agent_id = resolve_agent_id(cursor, x_agent_credential)

            # 'alerts.severity' pasó a ser 'severity_id' (FK a
            # 'severity_levels'). Igual que con event_type: se rechaza
            # si el agente manda un nombre que no está en el catálogo,
            # en vez de guardar una severidad inventada.
            cursor.execute(
                "SELECT id FROM severity_levels WHERE name = %s;",
                (alert.severity,)
            )

            severity_row = cursor.fetchone()

            if severity_row is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Severidad desconocida: '{alert.severity}'"
                )

            severity_id = severity_row[0]

            rule_id = None
            rule_weight = None

            if alert.rule_name:

                cursor.execute(
                    """
                    SELECT id, weight FROM heuristic_rules
                    WHERE name = %s AND is_active = TRUE;
                    """,
                    (alert.rule_name,)
                )

                rule_row = cursor.fetchone()

                if rule_row:
                    rule_id, rule_weight = rule_row

            cursor.execute(
                """
                INSERT INTO alerts (
                    agent_id,
                    severity_id,
                    title,
                    description,
                    risk_score
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    agent_id,
                    severity_id,
                    alert.title,
                    alert.description,
                    alert.risk_score if alert.risk_score is not None else 0
                )
            )

            alert_id = cursor.fetchone()[0]

            # Qué regla(s) dispararon esta alerta y con qué peso --
            # 'alert_rule' reemplaza al viejo 'alerts.rule_id' (que
            # solo permitía una regla por alerta).
            if rule_id is not None:
                cursor.execute(
                    """
                    INSERT INTO alert_rule (alert_id, rule_id, weight_applied)
                    VALUES (%s, %s, %s);
                    """,
                    (alert_id, rule_id, rule_weight)
                )

            connection.commit()

        return {
            "message": "Alerta registrada",
            "alert_id": alert_id
        }

    finally:
        connection.close()
