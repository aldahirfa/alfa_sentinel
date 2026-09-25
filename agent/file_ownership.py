"""Dueño de las carpetas y archivos que crea el agente.

El agente corre con privilegios (root en Linux, Administrador en
Windows): los necesita para aislar la red, atribuir procesos (fanotify /
ETW) y vigilar las carpetas de todos los usuarios. Pero lo que crea en
la carpeta de un usuario -- ALFA_ARCHIVOS y los honeyfiles -- tiene que
quedar como un archivo normal de ese usuario:

- Si un honeyfile fuera de root, un ransomware que corre con el usuario
  (el caso típico) no podría modificarlo; el archivo nunca cambiaría y
  el señuelo no detectaría justamente al atacante para el que existe.
- El usuario tiene que poder moverlo, renombrarlo o borrarlo como a
  cualquier archivo suyo (también para verificar que está vigilado).

Regla única: todo lo que crea el agente toma el dueño de la carpeta que
lo contiene. No se usa SUDO_USER ni el usuario que lanzó el agente: así
funciona igual con sudo, como servicio del sistema y con varios
usuarios en el mismo equipo.

Seguridad: como el agente es privilegiado y escribe en carpetas que
controla el usuario, nunca sigue enlaces simbólicos (lchown, O_NOFOLLOW);
de lo contrario un enlace plantado por el usuario podría hacer que el
agente escriba o regale la propiedad de un archivo del sistema.
"""

import os
import platform
import subprocess

COMMAND_TIMEOUT_SECONDS = 15


def _is_privileged():
    system = platform.system()
    if system == "Linux":
        return os.geteuid() == 0
    if system == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return False


def is_link_or_junction(path):
    """Enlace simbólico (Linux/Windows) o junction (Windows)."""

    return os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def _windows_owner(path):
    # Comillas simples de PowerShell: la única secuencia especial es ''.
    literal = path.replace("'", "''")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", f"(Get-Acl -LiteralPath '{literal}').Owner"],
        capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=True,
    )
    return result.stdout.strip() or None


def adopt_parent_owner(path, newly_created):
    """Asigna a 'path' el dueño de su carpeta padre.

    Linux: se aplica siempre (es un stat barato), así también se corrigen
    archivos que una versión anterior dejó a nombre de root.
    Windows: solo a lo recién creado (necesita lanzar PowerShell/icacls);
    lo que ya existía conserva los permisos heredados de la carpeta del
    usuario, que ya le dan control total.

    Devuelve True si cambió el dueño. Un fallo se informa pero no impide
    crear el honeyfile: sigue existiendo y vigilado."""

    if not _is_privileged():
        return False
    parent = os.path.dirname(os.path.abspath(path))

    try:
        if platform.system() == "Linux":
            parent_stat = os.stat(parent)
            current = os.lstat(path)
            if (current.st_uid, current.st_gid) == (parent_stat.st_uid, parent_stat.st_gid):
                return False
            os.lchown(path, parent_stat.st_uid, parent_stat.st_gid)
            return True

        if platform.system() == "Windows" and newly_created:
            owner = _windows_owner(parent)
            if not owner:
                return False
            # icacls actúa sobre el propio enlace/junction, no sobre su destino
            # (/L); aun así, quien llama ya rechazó enlaces antes de crear.
            subprocess.run(
                ["icacls", path, "/setowner", owner, "/L", "/Q"],
                capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=True,
            )
            return True
    except (OSError, subprocess.SubprocessError) as error:
        print(f"⚠ No se pudo asignar el dueño de la carpeta a {path}: {error}")
    return False


def make_dirs_owned(directory):
    """Como os.makedirs(directory, exist_ok=True), pero cada carpeta que
    crea toma el dueño de su carpeta padre. La carpeta final no puede
    ser un enlace (el agente escribiría en otro lugar)."""

    directory = os.path.abspath(directory)
    missing = []
    current = directory
    while not os.path.lexists(current):
        missing.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    for path in reversed(missing):
        try:
            os.mkdir(path)
        except FileExistsError:
            pass
        adopt_parent_owner(path, newly_created=True)

    if is_link_or_junction(directory):
        raise OSError(f"{directory} es un enlace simbólico o junction; el agente no escribe a través de enlaces.")
    if not os.path.isdir(directory):
        raise OSError(f"{directory} existe pero no es una carpeta.")

    # Carpeta que ya existía (p. ej. ALFA_ARCHIVOS creada por una versión
    # anterior a nombre de root): se corrige en Linux.
    if not missing:
        adopt_parent_owner(directory, newly_created=False)
    return directory


def open_new_file_for_write(path):
    """Crea un archivo NUEVO para escribir. Falla si ya existe algo en esa
    ruta, incluido un enlace simbólico: nunca escribe a través de él."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    return os.fdopen(os.open(path, flags, 0o644), "wb")


def open_for_read_no_follow(path):
    """Abre para leer sin seguir enlaces simbólicos (en Linux); evita que
    el agente privilegiado lea, por ejemplo, el hash de un archivo del
    sistema a través de un enlace plantado."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    return os.fdopen(os.open(path, flags), "rb")
