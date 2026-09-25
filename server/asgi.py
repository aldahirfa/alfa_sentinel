"""Entrypoint ASGI del servidor ALFA-Sentinel.

Reutiliza toda la aplicación definida en main.py y sustituye únicamente
los endpoints que hoy necesitan una evolución compatible sin reescribir
el servidor completo: heartbeat enriquecido y enrolamiento con código
corto de un solo uso.
"""

import hashlib
import secrets

from pydantic import BaseModel
from fastapi import Depends, Header, HTTPException

from main import (
    agent_online_sql,
    app,
    get_agent_stale_seconds,
    get_connection,
    get_current_user,
    require_role,
    resolve_agent_id,
)


ENROLLMENT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ENROLLMENT_CODE_LENGTH = 8

RESPONSE_ISOLATION_LABELS = {
    "REQUESTED": "Aislamiento pendiente",
    "EXECUTED": "Aislado",
    "ISOLATION_FAILED": "Aislamiento fallido",
    "RELEASE_REQUESTED": "Liberación pendiente",
    "RELEASED": "Liberado",
    "RECOMMENDED": "Recomendado",
}

RESPONSE_INCIDENT_LABELS = {
    "OPEN": "Abierto",
    "IN_PROGRESS": "En investigación",
    "CONTAINED": "Contenido",
    "CLOSED": "Cerrado",
}


class HeartbeatUpdate(BaseModel):
    hostname: str | None = None
    os: str | None = None
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


def _normalize_enrollment_code(value: str) -> str:
    """Acepta ABCD-EFGH, ABCDEFGH o el mismo valor con espacios."""

    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def _format_enrollment_code(raw_code: str) -> str:
    return f"{raw_code[:4]}-{raw_code[4:]}"


def _new_enrollment_code() -> tuple[str, str]:
    raw = "".join(secrets.choice(ENROLLMENT_CODE_ALPHABET) for _ in range(ENROLLMENT_CODE_LENGTH))
    return raw, _format_enrollment_code(raw)


def _remove_original_routes():
    replacements = {
        ("/agent/heartbeat", "POST"),
        ("/enrollment-tokens", "POST"),
        ("/enrollment", "POST"),
    }

    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not any(
            getattr(route, "path", None) == path
            and method in (getattr(route, "methods", set()) or set())
            for path, method in replacements
        )
    ]


_remove_original_routes()


@app.post("/enrollment-tokens")
def create_enrollment_code(user: dict = Depends(require_role("admin"))):
    """Genera un código humano de enrolamiento de un solo uso.

    Se conserva la misma tabla enrollment_tokens y el mismo token_hash:
    en la base nunca se guarda el código en claro. El formato visible es
    XXXX-XXXX (40 bits aprox. con alfabeto de 32 símbolos), válido 15 min.
    """

    created_by = user["id"]

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for _ in range(10):
                raw_code, display_code = _new_enrollment_code()
                token_hash = hashlib.sha256(raw_code.encode()).hexdigest()

                cursor.execute(
                    "SELECT 1 FROM enrollment_tokens WHERE token_hash = %s;",
                    (token_hash,)
                )
                if cursor.fetchone() is None:
                    break
            else:
                raise HTTPException(status_code=503, detail="No se pudo generar un código de enrolamiento único")

            cursor.execute(
                """
                INSERT INTO enrollment_tokens (token_hash, created_by, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '15 minutes')
                RETURNING id, expires_at;
                """,
                (token_hash, created_by)
            )
            token_id, expires_at = cursor.fetchone()
            connection.commit()

        return {
            "message": "Código de enrolamiento creado",
            "token": display_code,
            "code": display_code,
            "token_id": token_id,
            "expires_at": expires_at,
        }
    finally:
        connection.close()


@app.post("/enrollment")
def enroll_agent(enrollment: EnrollmentRequest):
    raw_code = _normalize_enrollment_code(enrollment.token)

    if len(raw_code) != ENROLLMENT_CODE_LENGTH or any(ch not in ENROLLMENT_CODE_ALPHABET for ch in raw_code):
        raise HTTPException(status_code=401, detail="Código de enrolamiento inválido o expirado")

    token_hash = hashlib.sha256(raw_code.encode()).hexdigest()

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
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
                raise HTTPException(status_code=401, detail="Código de enrolamiento inválido o expirado")

            token_id = token_record[0]

            cursor.execute(
                """
                INSERT INTO endpoints (hostname, os, os_version, ip_address)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (enrollment.hostname, enrollment.os, enrollment.os_version, enrollment.ip_address)
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

            credential = secrets.token_urlsafe(32)
            credential_hash = hashlib.sha256(credential.encode()).hexdigest()

            cursor.execute(
                "INSERT INTO agent_credentials (agent_id, credential_hash) VALUES (%s, %s);",
                (agent_id, credential_hash)
            )

            cursor.execute(
                """
                UPDATE enrollment_tokens
                SET used_at = CURRENT_TIMESTAMP, status = 'USED'
                WHERE id = %s;
                """,
                (token_id,)
            )

            connection.commit()

        return {
            "message": "Agente registrado correctamente",
            "agent_id": agent_id,
            "credential": credential,
        }
    finally:
        connection.close()


@app.post("/agent/heartbeat")
def agent_heartbeat(
    heartbeat: HeartbeatUpdate | None = None,
    x_agent_credential: str = Header(...),
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            agent_id = resolve_agent_id(cursor, x_agent_credential)

            cursor.execute(
                """
                UPDATE agents
                SET last_seen_at = CURRENT_TIMESTAMP,
                    status = 'ONLINE',
                    agent_version = COALESCE(%s, agent_version),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING endpoint_id;
                """,
                (heartbeat.agent_version if heartbeat else None, agent_id),
            )

            endpoint_row = cursor.fetchone()
            endpoint_id = endpoint_row[0]

            if heartbeat is not None:
                cursor.execute(
                    """
                    UPDATE endpoints
                    SET hostname = COALESCE(%s, hostname),
                        os = COALESCE(%s, os),
                        os_version = COALESCE(%s, os_version),
                        ip_address = COALESCE(%s, ip_address),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        heartbeat.hostname,
                        heartbeat.os,
                        heartbeat.os_version,
                        heartbeat.ip_address,
                        endpoint_id,
                    ),
                )

            connection.commit()

            return {
                "message": "Heartbeat recibido",
                "agent_id": agent_id,
                "endpoint_id": endpoint_id,
                "inventory_updated": heartbeat is not None,
            }
    finally:
        connection.close()


@app.get("/api/respuesta/endpoints")
def response_endpoints(user: dict = Depends(get_current_user)):
    """Vista operativa de contención agrupada por endpoint/agente.

    Devuelve una sola fila por agente registrado. El historial de
    host_isolations no se repite en esta lista: únicamente se expone el
    último estado para decidir qué control mostrar. La trazabilidad
    completa vive en /api/respuesta/endpoints/{agent_id}.
    """

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # agent_status con la regla única de estado (agent_online_sql),
            # no agents.status crudo: así Respuesta dice lo mismo que Endpoints.
            online_sql = agent_online_sql(get_agent_stale_seconds(cursor))
            cursor.execute(
                f"""
                SELECT
                    agents.id,
                    endpoints.hostname,
                    endpoints.os,
                    endpoints.os_version,
                    endpoints.ip_address,
                    CASE WHEN {online_sql} THEN 'ONLINE' ELSE 'OFFLINE' END,
                    agents.last_seen_at,
                    latest_iso.id,
                    latest_iso.status,
                    latest_iso.requested_at,
                    active_incident.id,
                    COALESCE(incident_stats.total, 0),
                    COALESCE(isolation_stats.total, 0)
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                LEFT JOIN LATERAL (
                    SELECT hi.id, hi.status, hi.requested_at
                    FROM host_isolations hi
                    WHERE hi.agent_id = agents.id
                    ORDER BY hi.requested_at DESC, hi.id DESC
                    LIMIT 1
                ) AS latest_iso ON TRUE
                LEFT JOIN LATERAL (
                    SELECT i.id
                    FROM incidents i
                    WHERE i.agent_id = agents.id
                      AND i.status != 'CLOSED'
                    ORDER BY i.opened_at DESC, i.id DESC
                    LIMIT 1
                ) AS active_incident ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS total
                    FROM incidents i
                    WHERE i.agent_id = agents.id
                ) AS incident_stats ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS total
                    FROM host_isolations hi
                    WHERE hi.agent_id = agents.id
                ) AS isolation_stats ON TRUE
                ORDER BY endpoints.hostname ASC, agents.id ASC;
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    endpoints_data = []
    for row in rows:
        isolation_status = row[8]
        endpoints_data.append({
            "agent_id": row[0],
            "hostname": row[1],
            "operating_system": row[2] or "Desconocido",
            "os_version": row[3] or "",
            "ip_address": str(row[4]) if row[4] else "—",
            "agent_status": row[5],
            "last_seen_at": row[6].strftime("%d/%m/%Y %H:%M:%S") if row[6] else None,
            "isolation_id": row[7],
            "isolation_status": isolation_status,
            "isolation_status_label": RESPONSE_ISOLATION_LABELS.get(isolation_status, "Sin aislamiento") if isolation_status else "Sin aislamiento",
            "latest_action_at": row[9].strftime("%d/%m/%Y %H:%M:%S") if row[9] else None,
            "active_incident_id": row[10],
            "incident_count": row[11],
            "isolation_count": row[12],
        })

    pending_statuses = {"REQUESTED", "RELEASE_REQUESTED"}
    return {
        "summary": {
            "total_endpoints": len(endpoints_data),
            "isolated_now": sum(1 for item in endpoints_data if item["isolation_status"] == "EXECUTED"),
            "pending_now": sum(1 for item in endpoints_data if item["isolation_status"] in pending_statuses),
            "with_history": sum(1 for item in endpoints_data if item["isolation_count"] > 0),
        },
        "endpoints": endpoints_data,
    }


@app.get("/api/respuesta/endpoints/{agent_id}")
def response_endpoint_detail(agent_id: int, user: dict = Depends(get_current_user)):
    """Detalle completo de contención para un endpoint registrado."""

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            online_sql = agent_online_sql(get_agent_stale_seconds(cursor))
            cursor.execute(
                f"""
                SELECT agents.id, endpoints.hostname, endpoints.os, endpoints.os_version,
                       endpoints.ip_address,
                       CASE WHEN {online_sql} THEN 'ONLINE' ELSE 'OFFLINE' END,
                       agents.last_seen_at,
                       agents.agent_version
                FROM agents
                JOIN endpoints ON endpoints.id = agents.endpoint_id
                WHERE agents.id = %s;
                """,
                (agent_id,),
            )
            endpoint_row = cursor.fetchone()
            if endpoint_row is None:
                raise HTTPException(status_code=404, detail="Endpoint no encontrado")

            cursor.execute(
                """
                SELECT hi.id, hi.status, hi.reason, hi.requested_at,
                       hi.executed_at, hi.released_at, hi.result,
                       users.full_name, hi.incident_id
                FROM host_isolations hi
                LEFT JOIN users ON users.id = hi.requested_by
                WHERE hi.agent_id = %s
                ORDER BY hi.requested_at DESC, hi.id DESC;
                """,
                (agent_id,),
            )
            isolation_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    i.id,
                    i.title,
                    i.status,
                    i.opened_at,
                    i.closed_at,
                    assigned_user.full_name,
                    (
                        SELECT sl.name
                        FROM alerts a
                        JOIN severity_levels sl ON sl.id = a.severity_id
                        WHERE a.incident_id = i.id
                        ORDER BY sl.min_score DESC
                        LIMIT 1
                    ) AS severity,
                    (
                        SELECT COALESCE(MAX(a.risk_score), 0)
                        FROM alerts a
                        WHERE a.incident_id = i.id
                    ) AS risk_score,
                    (
                        SELECT COUNT(*)
                        FROM alerts a
                        WHERE a.incident_id = i.id
                    ) AS detection_count
                FROM incidents i
                LEFT JOIN users AS assigned_user ON assigned_user.id = i.assigned_to
                WHERE i.agent_id = %s
                ORDER BY i.opened_at DESC, i.id DESC;
                """,
                (agent_id,),
            )
            incident_rows = cursor.fetchall()
    finally:
        connection.close()

    isolations = [
        {
            "id": row[0],
            "status": row[1],
            "status_label": RESPONSE_ISOLATION_LABELS.get(row[1], row[1]),
            "reason": row[2],
            "requested_at": row[3].strftime("%d/%m/%Y %H:%M:%S") if row[3] else None,
            "executed_at": row[4].strftime("%d/%m/%Y %H:%M:%S") if row[4] else None,
            "released_at": row[5].strftime("%d/%m/%Y %H:%M:%S") if row[5] else None,
            "result": row[6],
            "requested_by_name": row[7],
            "incident_id": row[8],
        }
        for row in isolation_rows
    ]

    incidents = [
        {
            "id": row[0],
            "code": f"INC-{row[0]:05d}",
            "title": row[1],
            "status": row[2],
            "status_label": RESPONSE_INCIDENT_LABELS.get(row[2], row[2]),
            "opened_at": row[3].strftime("%d/%m/%Y %H:%M:%S") if row[3] else None,
            "closed_at": row[4].strftime("%d/%m/%Y %H:%M:%S") if row[4] else None,
            "assigned_to_name": row[5],
            "severity": row[6],
            "risk_score": float(row[7] or 0),
            "detection_count": row[8],
        }
        for row in incident_rows
    ]

    latest = isolations[0] if isolations else None
    active_incident = next((item for item in incidents if item["status"] != "CLOSED"), None)

    return {
        "endpoint": {
            "agent_id": endpoint_row[0],
            "hostname": endpoint_row[1],
            "operating_system": endpoint_row[2] or "Desconocido",
            "os_version": endpoint_row[3] or "",
            "ip_address": str(endpoint_row[4]) if endpoint_row[4] else "—",
            "agent_status": endpoint_row[5],
            "last_seen_at": endpoint_row[6].strftime("%d/%m/%Y %H:%M:%S") if endpoint_row[6] else None,
            "agent_version": endpoint_row[7],
            "isolation_id": latest["id"] if latest else None,
            "isolation_status": latest["status"] if latest else None,
            "isolation_status_label": latest["status_label"] if latest else "Sin aislamiento",
            "active_incident_id": active_incident["id"] if active_incident else None,
        },
        "summary": {
            "incidents_total": len(incidents),
            "isolations_total": len(isolations),
            "isolated_now": bool(latest and latest["status"] == "EXECUTED"),
        },
        "incidents": incidents,
        "isolations": isolations,
    }
