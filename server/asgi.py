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

from main import app, get_connection, require_role, resolve_agent_id


ENROLLMENT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ENROLLMENT_CODE_LENGTH = 8


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
            # La probabilidad de colisión es mínima, pero se comprueba antes
            # de insertar para mantener token_hash UNIQUE sin depender del azar.
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
            # Se conserva 'token' por compatibilidad con el frontend actual.
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

            # Esta credencial sí permanece larga y aleatoria: ya no la escribe
            # una persona, la recibe el agente y la guarda automáticamente.
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
