import httpx

import config
# Se usa "import config" (no "from config import X") a propósito: si
# main.py recibe --server y pisa config.SERVER_URL/config.EVENTS_URL/etc
# en tiempo de ejecución (ver parse_args() en main.py), estas funciones
# tienen que leer el valor actualizado, no el que tenía config.py al
# momento de este import.


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
        "token": config.ENROLLMENT_TOKEN,
        **system_info
    }

    try:

        response = httpx.post(
            config.ENROLLMENT_URL,
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
            config.AUTHENTICATION_URL,
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
            config.HEARTBEAT_URL,
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
            config.EVENTS_URL,
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


def get_honeyfile_policy(credential):

    try:

        response = httpx.get(
            config.HONEYFILE_POLICY_URL,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "pedir la política de honeyfiles")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def report_honeyfile_policy(credential, results):

    try:

        response = httpx.post(
            config.HONEYFILE_POLICY_REPORT_URL,
            json={"results": results},
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "reportar honeyfiles creados")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def get_rule_policy(credential):
    """Agregado 2026-08-12, mismo patrón que get_honeyfile_policy: pide
    al servidor los valores reales de peso/umbral/ventana de cada
    regla activa (GET /agent/rule-policy), para que FileActivityAnalyzer
    ya no dependa de los valores hardcodeados en su __init__()."""

    try:

        response = httpx.get(
            config.RULE_POLICY_URL,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "pedir la política de reglas")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def get_isolation_status(credential):
    """Agregado 2026-08-17 (ver PENDIENTES.md, "Corrección definitiva
    del motor heurístico..."): mismo patrón de polling que
    get_honeyfile_policy/get_rule_policy -- pregunta si el servidor
    ordenó aislar este endpoint (GET /agent/isolation-status)."""

    try:

        response = httpx.get(
            config.ISOLATION_STATUS_URL,
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "pedir el estado de aislamiento")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def report_isolation_status(credential, isolation_id, status, result):
    """Confirma el resultado REAL de haber intentado ejecutar una
    orden de aislamiento (ver agent/isolation_executor.py) --
    'status' es 'EXECUTED' o 'ISOLATION_FAILED', nunca un valor
    inventado."""

    try:

        response = httpx.post(
            config.ISOLATION_STATUS_REPORT_URL,
            json={
                "isolation_id": isolation_id,
                "status": status,
                "result": result,
            },
            headers={
                "X-Agent-Credential": credential
            },
            timeout=10
        )

        _warn_if_error(response, "reportar el resultado de un aislamiento")

        return response

    except httpx.RequestError as error:

        print("No se pudo conectar con el servidor:")
        print(error)

        return None


def send_alert(credential, alert_data):

    try:

        response = httpx.post(
            config.ALERTS_URL,
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
