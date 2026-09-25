"""Protección del servidor frente a un endpoint comprometido.

Un equipo infectado tiene una credencial de agente válida, así que el
servidor no puede confiar en lo que le manda. Este módulo agrupa las
defensas que no dependen de la lógica de cada ruta:

- Límite de volumen por agente (y por IP en el enrolamiento), para que
  un agente no inunde la base.
- Límite de tamaño del cuerpo de los pedidos.
- Tipos de texto validados para los modelos que llegan de los agentes.
- Bloqueo temporal del login tras varios intentos fallidos.

Los contadores viven en memoria: el servidor corre en un solo proceso
(run_server.py no usa workers) y un reinicio los pone en cero, que es
aceptable para límites de ventana corta.
"""

import hashlib
import ipaddress
import json
import threading
import time
from collections import deque
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


# --- Texto que llega de los agentes -----------------------------------

# Caracteres de control (salvo tabulador): PostgreSQL rechaza el NUL en
# columnas de texto (daría un error 500) y el resto puede falsear lo que
# ve el analista en la consola. En texto libre (rutas, descripciones) se
# reemplazan en vez de rechazar el pedido: un nombre de archivo raro es
# evidencia de un ataque y no debe perderse.
_CONTROL_CHARS = {c: "�" for c in range(32) if c != 9}
_CONTROL_CHARS[127] = "�"


def _replace_control_chars(value: str) -> str:
    return value.translate(_CONTROL_CHARS)


def _reject_control_chars(value: str) -> str:
    if value != _replace_control_chars(value):
        raise ValueError("contiene caracteres de control")
    return value


def _valid_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise ValueError("no es una dirección IP válida") from None


def FreeText(max_length: int):
    """Texto libre (ruta, descripción, error): largo acotado y caracteres
    de control reemplazados."""
    return Annotated[str, StringConstraints(max_length=max_length), AfterValidator(_replace_control_chars)]


def Identifier(max_length: int):
    """Dato de inventario o nombre de catálogo (hostname, SO, tipo de
    evento): largo acotado, sin caracteres de control."""
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(_reject_control_chars),
    ]


IpAddress = Annotated[str, StringConstraints(max_length=45), AfterValidator(_valid_ip)]

# PID: entero no negativo que entra en BIGINT (Windows y Linux usan 32 bits).
MAX_PID = 2**32


# --- Límite de volumen ------------------------------------------------

class SlidingWindowLimiter:
    """Cuenta pedidos por clave en una ventana deslizante. Además lleva
    cuántos se rechazaron, para avisar una sola vez por ventana en vez
    de llenar el log con un mensaje por pedido."""

    def __init__(self):
        self._hits = {}
        self._rejected = {}
        self._lock = threading.Lock()

    def hit(self, key, limit, window_seconds):
        """Registra un pedido. Devuelve (permitido, segundos_para_reintentar,
        primer_rechazo_de_la_ventana)."""

        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) < limit:
                hits.append(now)
                self._rejected.pop(key, None)
                return True, 0, False
            retry_after = max(1, int(hits[0] + window_seconds - now) + 1)
            count = self._rejected.get(key, 0) + 1
            self._rejected[key] = count
            return False, retry_after, count == 1

    def prune(self, window_seconds):
        """Descarta las claves sin actividad reciente (evita que el
        diccionario crezca sin fin con credenciales o IPs de paso)."""

        now = time.monotonic()
        with self._lock:
            for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - window_seconds]:
                self._hits.pop(key, None)
                self._rejected.pop(key, None)


# (límite, ventana en segundos) por tipo de ruta de agente. El agente
# legítimo manda un heartbeat cada 30 s y sincroniza aislamiento y
# honeyfiles cada 15 s y 45 s. Los eventos llevan el margen más grande
# porque un cifrado real genera muchos cambios por segundo; si se supera,
# se descartan eventos crudos, pero las alertas (que el agente manda
# aparte, con su propio límite) siguen llegando.
AGENT_RATE_LIMITS = {
    "events": (1200, 60),
    "alerts": (120, 60),
    "heartbeat": (20, 60),
    "other": (60, 60),
}
ENROLLMENT_RATE_LIMIT = (10, 60)  # por IP: pedidos sin credencial

# Tamaño máximo del cuerpo de un pedido.
AGENT_MAX_BODY_BYTES = 64 * 1024
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024


def agent_route_kind(path):
    if path == "/agent/events":
        return "events"
    if path == "/agent/alerts":
        return "alerts"
    if path == "/agent/heartbeat":
        return "heartbeat"
    return "other"


def _json_response(status, detail, extra_headers=()):
    body = json.dumps({"detail": detail}).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    headers.extend(extra_headers)
    return status, headers, body


async def _send(send, status, headers, body):
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class AgentProtectionMiddleware:
    """Middleware ASGI: límite de volumen para las rutas de agente y de
    enrolamiento, y límite de tamaño del cuerpo para todo pedido.

    El límite por agente se aplica ANTES de consultar la base, usando el
    hash de la credencial como clave: un agente que inunda el servidor no
    llega a costar ni una consulta. Una credencial inválida igual pasa
    por el límite ("other") y después la ruta la rechaza con 401."""

    def __init__(self, app):
        self.app = app
        self.limiter = SlidingWindowLimiter()
        self._last_prune = time.monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_agent = path.startswith("/agent/")
        is_enrollment = path == "/enrollment"

        if is_agent or is_enrollment:
            rejection = self._check_rate(scope, path, is_agent)
            if rejection is not None:
                await _send(send, *rejection)
                return

        max_bytes = AGENT_MAX_BODY_BYTES if (is_agent or is_enrollment) else DEFAULT_MAX_BODY_BYTES
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await _send(send, *_json_response(413, f"El cuerpo del pedido supera el máximo de {max_bytes} bytes."))
                return

        # Sin Content-Length (envío por partes) se cuenta lo que va
        # llegando. Al pasarse se responde 413 acá mismo y se corta la
        # lectura; lo que la aplicación intente responder después (FastAPI
        # lo convertiría en un 400 genérico) se descarta.
        received = 0
        response_started = False
        rejected = False

        async def limited_receive():
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    if not response_started and not rejected:
                        rejected = True
                        await _send(send, *_json_response(413, f"El cuerpo del pedido supera el máximo de {max_bytes} bytes."))
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal response_started
            if rejected:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            pass

    def _check_rate(self, scope, path, is_agent):
        now = time.monotonic()
        if now - self._last_prune > 300:
            self.limiter.prune(300)
            self._last_prune = now

        if is_agent:
            headers = dict(scope.get("headers") or [])
            credential = headers.get(b"x-agent-credential", b"")
            kind = agent_route_kind(path)
            limit, window = AGENT_RATE_LIMITS[kind]
            # Nunca se guarda la credencial en claro, ni siquiera en memoria.
            identity = hashlib.sha256(credential).hexdigest()[:16] if credential else "sin-credencial"
            key = ("agent", identity, kind)
            who = f"agente {identity}"
        else:
            client = scope.get("client") or ("desconocido", 0)
            limit, window = ENROLLMENT_RATE_LIMIT
            key = ("enrollment", client[0])
            who = f"IP {client[0]}"
            kind = "enrollment"

        allowed, retry_after, first_rejection = self.limiter.hit(key, limit, window)
        if allowed:
            return None
        if first_rejection:
            print(f"[límite] {who} superó {limit} pedidos '{kind}' en {window} s; se rechaza lo que exceda.")
        return _json_response(
            429,
            "Demasiados pedidos. Reintenta más tarde.",
            [(b"retry-after", str(retry_after).encode())],
        )


class _BodyTooLarge(Exception):
    pass


# --- Login ------------------------------------------------------------

LOGIN_MAX_FAILURES_PER_USER = 5
LOGIN_MAX_FAILURES_PER_IP = 30
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60


class LoginGuard:
    """Bloqueo temporal tras varios intentos fallidos.

    Se cuenta por usuario (frena probar contraseñas contra una cuenta) y
    por IP con un umbral más alto (frena probar muchos usuarios desde un
    mismo origen; más alto porque detrás del proxy de la consola varios
    analistas pueden compartir IP). Se cuenta igual si el usuario no
    existe, para no revelar qué usuarios son válidos."""

    def __init__(self):
        self._failures = {}
        self._locked_until = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(username, ip):
        return [("user", username.strip().lower()), ("ip", ip)]

    def seconds_locked(self, username, ip):
        now = time.monotonic()
        with self._lock:
            remaining = [until - now for key in self._keys(username, ip) if (until := self._locked_until.get(key, 0)) > now]
        # int() y no ceil(): el reloj de Windows avanza a saltos y un
        # bloqueo recién puesto da 900.0000001 s, que ceil() llevaría a 901.
        return max(1, int(max(remaining))) if remaining else 0

    def register_failure(self, username, ip):
        now = time.monotonic()
        limits = {"user": LOGIN_MAX_FAILURES_PER_USER, "ip": LOGIN_MAX_FAILURES_PER_IP}
        with self._lock:
            for key in self._keys(username, ip):
                failures = self._failures.setdefault(key, deque())
                while failures and failures[0] <= now - LOGIN_FAILURE_WINDOW_SECONDS:
                    failures.popleft()
                failures.append(now)
                if len(failures) >= limits[key[0]]:
                    self._locked_until[key] = now + LOGIN_LOCKOUT_SECONDS
                    failures.clear()
                    print(f"[login] bloqueo temporal por intentos fallidos ({key[0]}: {key[1]}).")

    def register_success(self, username):
        with self._lock:
            key = ("user", username.strip().lower())
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)
