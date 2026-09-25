import httpx

import config
import transport
# Se usa "import config" (no "from config import X") a propósito: si
# main.py recibe --server y pisa config.SERVER_URL/config.EVENTS_URL/etc
# en tiempo de ejecución (ver parse_args() en main.py), estas funciones
# tienen que leer el valor actualizado, no el que tenía config.py al
# momento de este import.


def _warn_if_error(response, action):
    """Imprime errores HTTP del servidor sin detener el agente."""

    if response is None:
        return

    if response.status_code >= 400:
        print(f"⚠ El servidor respondió con un error al {action}:")
        print(f"  status: {response.status_code}")
        try:
            print(f"  detalle: {response.json()}")
        except Exception:
            print(f"  detalle: {response.text}")


def _report_connection_error(error):
    """Distingue un fallo de red de un certificado rechazado: lo segundo
    puede ser un ataque (alguien suplantando al servidor) o una CA mal
    copiada, y no debe confundirse con 'el servidor está caído'."""

    text = str(error)
    if isinstance(error, transport.InsecureServerURLError):
        print(f"⚠ {text}")
    elif "CERTIFICATE_VERIFY_FAILED" in text or "certificate" in text.lower():
        print("⚠ El servidor presentó un certificado TLS NO confiable. Conexión cancelada.")
        print("  Posible suplantación del servidor, o agent/certs/ca.crt no corresponde")
        print("  a la CA del servidor / la IP no está en su certificado.")
        print(f"  detalle: {text}")
    else:
        print("No se pudo conectar con el servidor:")
        print(error)


def enroll_agent(system_info):
    data = {
        "token": config.ENROLLMENT_TOKEN,
        **system_info
    }

    try:
        response = transport.post(config.ENROLLMENT_URL, json=data, timeout=10)
        _warn_if_error(response, "hacer enrollment")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def authenticate_agent(credential):
    try:
        response = transport.get(
            config.AUTHENTICATION_URL,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "autenticar al agente")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def send_heartbeat(credential, system_info=None):
    """Envía presencia y, cuando está disponible, inventario actualizado.

    El body es opcional para conservar compatibilidad con servidores/agentes
    anteriores. El servidor nuevo usa estos datos para refrescar hostname,
    IP, SO, versión del SO y versión del agente sin exigir re-enrollment.
    """

    try:
        response = transport.post(
            config.HEARTBEAT_URL,
            json=system_info or {},
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "enviar el heartbeat")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def send_event(credential, event_data):
    try:
        response = transport.post(
            config.EVENTS_URL,
            json=event_data,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "enviar un evento")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def get_honeyfile_policy(credential, full=False):
    """full=True pide también el archivo de los honeyfiles ya creados
    (solo hace falta para recrear alguno que desapareció del disco)."""
    try:
        response = transport.get(
            config.HONEYFILE_POLICY_URL,
            params={"completo": "1"} if full else None,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "pedir la política de honeyfiles")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def report_honeyfile_policy(credential, results):
    try:
        response = transport.post(
            config.HONEYFILE_POLICY_REPORT_URL,
            json={"results": results},
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "reportar honeyfiles creados")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def get_rule_policy(credential):
    try:
        response = transport.get(
            config.RULE_POLICY_URL,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "pedir la política de reglas")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def get_isolation_status(credential):
    try:
        response = transport.get(
            config.ISOLATION_STATUS_URL,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "pedir el estado de aislamiento")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def report_isolation_status(credential, isolation_id, status, result):
    try:
        response = transport.post(
            config.ISOLATION_STATUS_REPORT_URL,
            json={
                "isolation_id": isolation_id,
                "status": status,
                "result": result,
            },
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "reportar el resultado de un aislamiento")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None


def send_alert(credential, alert_data):
    try:
        response = transport.post(
            config.ALERTS_URL,
            json=alert_data,
            headers={"X-Agent-Credential": credential},
            timeout=10
        )
        _warn_if_error(response, "enviar una alerta")
        return response
    except (httpx.RequestError, transport.InsecureServerURLError) as error:
        _report_connection_error(error)
        return None
