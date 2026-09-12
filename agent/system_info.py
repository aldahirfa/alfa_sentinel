import platform
import socket
import sys
from urllib.parse import urlparse

import psutil

import config


def _linux_distribution_info():
    """Devuelve nombre y versión legibles de la distribución Linux.

    platform.system() solo devuelve "Linux" y platform.version() devuelve
    información del kernel. Para inventariar el endpoint necesitamos la
    distribución real (Ubuntu, Debian, etc.) y su versión de usuario.
    """

    try:
        info = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        info = {}

        try:
            with open("/etc/os-release", "r", encoding="utf-8") as os_release:
                for line in os_release:
                    if "=" not in line:
                        continue
                    key, value = line.rstrip().split("=", 1)
                    info[key] = value.strip().strip('"')
        except OSError:
            pass

    name = info.get("NAME") or "Linux"
    version = info.get("VERSION") or info.get("VERSION_ID") or platform.release()

    return name, version


def _windows_info():
    """Nombre amigable de Windows y número de compilación."""

    try:
        build = sys.getwindowsversion().build
    except AttributeError:
        build = None

    if build is not None and build >= 22000:
        name = "Windows 11"
    else:
        release = platform.release()
        name = f"Windows {release}" if release else "Windows"

    version = f"Build {build}" if build is not None else platform.version()
    return name, version


def get_os_info():
    system = platform.system()

    if system == "Linux":
        return _linux_distribution_info()

    if system == "Windows":
        return _windows_info()

    if system == "Darwin":
        mac_version = platform.mac_ver()[0]
        return "macOS", mac_version or platform.release()

    return system or "Desconocido", platform.version() or platform.release()


def _route_ip_to_server(server_url):
    """Obtiene la IP local usada realmente para alcanzar al servidor.

    No envía tráfico de aplicación: un socket UDP conectado solo obliga al
    SO a resolver qué interfaz/ruta usaría. Esto evita escoger por error
    loopback, Docker u otra interfaz cuando el endpoint tiene varias IP.
    """

    parsed = urlparse(server_url)
    host = parsed.hostname

    if not host:
        return None

    if parsed.port:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((host, port))
            ip_address = sock.getsockname()[0]

        if ip_address and not ip_address.startswith("127.") and ip_address != "0.0.0.0":
            return ip_address
    except OSError:
        return None

    return None


def _fallback_ipv4():
    """Busca una IPv4 útil si no fue posible resolver la ruta al servidor."""

    try:
        interfaces = psutil.net_if_addrs()
    except Exception:
        return None

    for addresses in interfaces.values():
        for address in addresses:
            if address.family != socket.AF_INET:
                continue

            ip_address = address.address

            if not ip_address:
                continue
            if ip_address.startswith("127."):
                continue
            if ip_address.startswith("169.254."):
                continue
            if ip_address == "0.0.0.0":
                continue

            return ip_address

    return None


def get_ip_address(server_url=None):
    return _route_ip_to_server(server_url or config.SERVER_URL) or _fallback_ipv4()


def get_system_info():
    os_name, os_version = get_os_info()

    return {
        "hostname": socket.gethostname(),
        "os": os_name,
        "os_version": os_version,
        "ip_address": get_ip_address(config.SERVER_URL),
        "agent_version": config.AGENT_VERSION,
    }
