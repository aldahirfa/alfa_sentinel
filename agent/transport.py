"""Canal HTTPS del agente hacia ALFA-Sentinel.

Todo pedido del agente al servidor pasa por get()/post() de este
módulo (agent/client.py ya no llama a httpx.get/httpx.post sueltos).
Reglas de seguridad que aplica, sin excepciones silenciosas:

1. HTTPS obligatorio. 'http://' solo se acepta si el servidor es
   127.0.0.1/localhost/::1 (pruebas locales, run_server.py
   --insecure-dev): en loopback el tráfico no sale de la máquina. Hacia
   cualquier otra IP, http:// se rechaza antes de mandar un solo byte
   -- la credencial del agente nunca viaja en claro por la red.

2. Confianza SOLO en la CA propia de ALFA-Sentinel (agent/certs/ca.crt,
   generada con server/generar_certificados.py). No se usa el almacén de
   certificados de Windows ni el de certifi: aunque un atacante en la
   red consiga un certificado "válido" de una CA comercial, o instale
   una CA falsa en el equipo, el agente lo rechaza (pinning de CA).
   Se verifica además que el nombre/IP coincida con el certificado.

3. TLS 1.2 como mínimo.

Si la verificación falla el pedido NO se hace (httpx.ConnectError, que
client.py ya trata como "no se pudo conectar") -- nunca se reintenta sin
verificar.
"""

import ipaddress
import os
import ssl
import threading
from urllib.parse import urlparse

import httpx

import config

_LOOPBACK_NAMES = {"localhost"}

_lock = threading.Lock()
_client = None
_client_key = None


class InsecureServerURLError(ValueError):
    """La URL del servidor no cumple la política de transporte."""


def _is_loopback(host):
    if not host:
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def ca_file_path():
    """Ruta absoluta de la CA en la que confía el agente.

    Prioridad: variable de entorno ALFA_SENTINEL_CA_FILE, luego
    config.CA_CERT_FILE (relativa a la carpeta del agente)."""

    path = os.environ.get("ALFA_SENTINEL_CA_FILE") or config.CA_CERT_FILE
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    return path


def validate_server_url(url=None):
    """Lanza InsecureServerURLError si la URL no es aceptable.
    Devuelve 'https' o 'http-loopback'."""

    url = url or config.SERVER_URL
    parsed = urlparse(url)

    if parsed.scheme == "https":
        if not os.path.isfile(ca_file_path()):
            raise InsecureServerURLError(
                f"No se encontró la CA de ALFA-Sentinel en {ca_file_path()}. "
                "Cópiala desde server/certs/ca.crt (o usa --ca <ruta>)."
            )
        return "https"

    if parsed.scheme == "http" and _is_loopback(parsed.hostname):
        return "http-loopback"

    if parsed.scheme == "http":
        raise InsecureServerURLError(
            f"Conexión rechazada: {url} usa HTTP sin cifrar. El agente solo "
            "habla HTTPS con el servidor (http:// únicamente hacia 127.0.0.1)."
        )

    raise InsecureServerURLError(f"URL de servidor inválida: {url!r}")


def _build_ssl_context():
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_file_path())
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _get_client():
    """Un único httpx.Client compartido por todos los hilos del agente
    (heartbeat, sync de honeyfiles/aislamiento, monitor de archivos):
    reutiliza la conexión TLS en vez de negociar un handshake por
    evento. Se reconstruye si cambia SERVER_URL o la CA (--server,
    --ca o las pruebas que cambian config en caliente)."""

    global _client, _client_key

    mode = validate_server_url()
    key = (config.SERVER_URL, ca_file_path() if mode == "https" else None)

    with _lock:
        if _client is None or _client_key != key:
            if _client is not None:
                _client.close()
            verify = _build_ssl_context() if mode == "https" else True
            _client = httpx.Client(verify=verify, timeout=10)
            _client_key = key
        return _client


def get(url, **kwargs):
    return _get_client().get(url, **kwargs)


def post(url, **kwargs):
    return _get_client().post(url, **kwargs)
