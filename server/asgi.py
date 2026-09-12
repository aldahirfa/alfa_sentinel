"""Entrypoint ASGI del servidor ALFA-Sentinel.

Reutiliza toda la aplicación definida en main.py y sustituye únicamente
POST /agent/heartbeat por la versión que, además de mantener last_seen_at,
refresca el inventario del endpoint. Esto permite que cambios de IP por
DHCP o una corrección del nombre/versionado del SO se reflejen sin tener
que volver a enrolar el agente.
"""

from pydantic import BaseModel
from fastapi import Header

from main import app, get_connection, resolve_agent_id


class HeartbeatUpdate(BaseModel):
    hostname: str | None = None
    os: str | None = None
    os_version: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None


def _remove_original_heartbeat_route():
    """Quita la implementación heredada de main.py antes de registrar la nueva."""

    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == "/agent/heartbeat"
            and "POST" in (getattr(route, "methods", set()) or set())
        )
    ]


_remove_original_heartbeat_route()


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
