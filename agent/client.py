import httpx

from config import (
    ENROLLMENT_URL,
    AUTHENTICATION_URL,
    HEARTBEAT_URL,
    EVENTS_URL,
    ALERTS_URL,
    ENROLLMENT_TOKEN
)


def _warn_if_error(response, action):
    """Antes, si el servidor respondía con un error (401, 422, 500...),
    el agente se quedaba con la respuesta y seguía de largo sin decir
    nada -- así perdimos tiempo depurando hoy. Esto imprime un aviso
    claro cada vez que el servidor rechaza algo, sin frenar al agente."""

    if response is None:
        return

    if response.status_code >= 400:

        print(f"⚠ El servidor respondió con un error al {action}:")
        print(f"  status: {response.status_code}")

        try:
            print(f"  detalle: {response.json()}")
        except Exception:
            print(f"  detalle: {response.text}")


def enroll_agent(system_info):

    data = {
        "token": ENROLLMENT_TOKEN,
        **system_info
    }

    try:

        response = httpx.post(
            ENROLLMENT_URL,
            json=data,
            timeout=10
        )

        _warn_if_error(response, "hacer enrollment")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def authenticate_agent(credential):

    try:

        response = httpx.get(
            AUTHENTICATION_URL,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "autenticar al agente")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def send_heartbeat(credential):

    try:

        response = httpx.post(
            HEARTBEAT_URL,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "enviar el heartbeat")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def send_event(credential, event_data):

    try:

        response = httpx.post(
            EVENTS_URL,
            json=event_data,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "enviar un evento")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def send_alert(credential, alert_data):

    try:

        response = httpx.post(
            ALERTS_URL,
            json=alert_data,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "enviar una alerta")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None
