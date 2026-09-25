"""Qué usuario protege el agente y dónde están realmente sus carpetas.

El agente vigila las carpetas principales del usuario del equipo
(Documentos, Escritorio, Descargas, Imágenes, Videos, Música). Dos
cosas no se pueden suponer:

1. QUIÉN es ese usuario. El agente corre con privilegios (sudo / root,
   Administrador) y, más adelante, como servicio del sistema: ahí la
   carpeta personal del proceso es la de root o SYSTEM, no la del
   usuario. Antes había que lanzarlo con HOME="$HOME" para evitarlo.
2. CÓMO se llaman sus carpetas. No siempre "Desktop", "Documents"...:
   un Ubuntu en español usa ~/Escritorio, ~/Documentos; un Windows con
   OneDrive suele tener el escritorio en ~\\OneDrive\\Desktop.

Orden para elegir el usuario (se informa siempre cuál se eligió):
  a) ALFA_SENTINEL_USER, si se definió (lo fijará el instalador).
  b) Si el agente no corre como root/SYSTEM: el propio usuario.
  c) Linux: SUDO_USER (quien lanzó el agente con sudo).
  d) El usuario real con sesión abierta; si no hay o hay varios, el
     usuario real más antiguo (Linux: menor UID) o con el perfil usado
     más recientemente (Windows).
"""

import os
import platform
from functools import lru_cache

# Carpetas que se resuelven, con el nombre en inglés que se usa si el
# sistema no informa otra ubicación.
FOLDER_KEYS = ("DOCUMENTS", "DESKTOP", "DOWNLOADS", "PICTURES", "VIDEOS", "MUSIC")
_DEFAULT_NAMES = {
    "DOCUMENTS": "Documents",
    "DESKTOP": "Desktop",
    "DOWNLOADS": "Downloads",
    "PICTURES": "Pictures",
    "VIDEOS": "Videos",
    "MUSIC": "Music",
}

# Linux: claves de ~/.config/user-dirs.dirs (estándar XDG).
_XDG_KEYS = {
    "DOCUMENTS": "XDG_DOCUMENTS_DIR",
    "DESKTOP": "XDG_DESKTOP_DIR",
    "DOWNLOADS": "XDG_DOWNLOAD_DIR",
    "PICTURES": "XDG_PICTURES_DIR",
    "VIDEOS": "XDG_VIDEOS_DIR",
    "MUSIC": "XDG_MUSIC_DIR",
}

# Windows: valores de ...\Explorer\User Shell Folders (respetan OneDrive
# y carpetas movidas por el usuario o por una política del dominio).
_WINDOWS_SHELL_VALUES = {
    "DOCUMENTS": "Personal",
    "DESKTOP": "Desktop",
    "DOWNLOADS": "{374DE290-123F-4565-9164-39C4925E467B}",
    "PICTURES": "My Pictures",
    "VIDEOS": "My Video",
    "MUSIC": "My Music",
}

_NOLOGIN_SHELLS = ("nologin", "false", "sync", "shutdown", "halt")


# --- Linux --------------------------------------------------------------

def _linux_uid_min():
    try:
        with open("/etc/login.defs", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0] == "UID_MIN":
                    return int(parts[1])
    except (OSError, ValueError):
        pass
    return 1000


def _linux_human_users():
    import pwd

    uid_min = _linux_uid_min()
    users = []
    for entry in pwd.getpwall():
        if entry.pw_uid < uid_min or entry.pw_uid == 65534:
            continue
        if os.path.basename(entry.pw_shell or "") in _NOLOGIN_SHELLS:
            continue
        if os.path.isdir(entry.pw_dir):
            users.append(entry)
    return sorted(users, key=lambda e: e.pw_uid)


def _linux_target_user():
    import pwd

    requested = os.environ.get("ALFA_SENTINEL_USER", "").strip()
    if requested:
        entry = pwd.getpwnam(requested)
        return entry.pw_name, entry.pw_dir, "ALFA_SENTINEL_USER"

    if os.geteuid() != 0:
        entry = pwd.getpwuid(os.geteuid())
        return entry.pw_name, entry.pw_dir, "usuario que ejecuta el agente"

    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user and sudo_user != "root":
        entry = pwd.getpwnam(sudo_user)
        return entry.pw_name, entry.pw_dir, "SUDO_USER (quien lanzó el agente con sudo)"

    humans = _linux_human_users()
    if not humans:
        raise RuntimeError("No se encontró ningún usuario real en el equipo; define ALFA_SENTINEL_USER.")
    # /run/user/<uid> existe mientras el usuario tiene una sesión abierta.
    logged_in = [e for e in humans if os.path.isdir(f"/run/user/{e.pw_uid}")]
    if len(logged_in) == 1:
        return logged_in[0].pw_name, logged_in[0].pw_dir, "único usuario con sesión abierta"
    chosen = humans[0]
    return chosen.pw_name, chosen.pw_dir, "usuario real más antiguo (menor UID)"


def _linux_folder(home, key):
    """Lee ~/.config/user-dirs.dirs: XDG_DESKTOP_DIR="$HOME/Escritorio"."""

    path = os.path.join(home, ".config", "user-dirs.dirs")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                name, sep, value = line.partition("=")
                if sep and name == _XDG_KEYS[key]:
                    value = value.strip().strip('"')
                    value = value.replace("$HOME", home)
                    if os.path.isabs(value) and os.path.normpath(value) != os.path.normpath(home):
                        return os.path.normpath(value)
    except OSError:
        pass
    return os.path.join(home, _DEFAULT_NAMES[key])


# --- Windows ------------------------------------------------------------

def _windows_profiles():
    """Perfiles de usuarios reales (SID S-1-5-21-...) registrados en el
    equipo: [(sid, ruta, última carga)]."""

    import winreg

    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
    profiles = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
        index = 0
        while True:
            try:
                sid = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            if not sid.startswith("S-1-5-21-"):
                continue
            try:
                with winreg.OpenKey(root, sid) as key:
                    path = os.path.expandvars(winreg.QueryValueEx(key, "ProfileImagePath")[0])
                    try:
                        high = winreg.QueryValueEx(key, "LocalProfileLoadTimeHigh")[0]
                        low = winreg.QueryValueEx(key, "LocalProfileLoadTimeLow")[0]
                        last_load = (high << 32) | low
                    except OSError:
                        last_load = 0
            except OSError:
                continue
            if os.path.isdir(path):
                profiles.append((sid, path, last_load))
    return profiles


def _windows_is_system_account():
    home = os.path.normcase(os.path.expanduser("~"))
    windir = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows"))
    return home.startswith(windir) or os.environ.get("USERNAME", "").upper().endswith("$")


def _windows_target_user():
    profiles = _windows_profiles()

    requested = os.environ.get("ALFA_SENTINEL_USER", "").strip()
    if requested:
        for sid, path, _ in profiles:
            if os.path.basename(path).lower() == requested.lower():
                return os.path.basename(path), path, sid, "ALFA_SENTINEL_USER"
        raise RuntimeError(f"ALFA_SENTINEL_USER={requested!r} no corresponde a ningún perfil del equipo.")

    if not _windows_is_system_account():
        home = os.path.expanduser("~")
        sid = next((s for s, p, _ in profiles if os.path.normcase(p) == os.path.normcase(home)), None)
        return os.path.basename(home), home, sid, "usuario que ejecuta el agente"

    if not profiles:
        raise RuntimeError("No se encontró ningún perfil de usuario en el equipo; define ALFA_SENTINEL_USER.")
    sid, path, _ = max(profiles, key=lambda p: p[2])
    return os.path.basename(path), path, sid, "perfil usado más recientemente"


def _windows_folder(home, sid, key):
    """Ubicación registrada de la carpeta en el perfil de ESE usuario
    (HKEY_USERS\\<SID>): está disponible mientras el usuario tiene la
    sesión abierta; si no, se usa el nombre estándar."""

    if sid:
        import winreg

        subkey = sid + r"\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        try:
            with winreg.OpenKey(winreg.HKEY_USERS, subkey) as key_handle:
                value = winreg.QueryValueEx(key_handle, _WINDOWS_SHELL_VALUES[key])[0]
            # %USERPROFILE% es el del usuario, no el del proceso del agente.
            value = value.replace("%USERPROFILE%", home).replace("%userprofile%", home)
            value = os.path.expandvars(value)
            if os.path.isabs(value):
                return os.path.normpath(value)
        except OSError:
            pass
    return os.path.join(home, _DEFAULT_NAMES[key])


# --- Interfaz -----------------------------------------------------------

@lru_cache(maxsize=1)
def get_target_user():
    """(nombre, carpeta personal, carpetas {clave: ruta}). Se resuelve una
    vez por ejecución del agente y se informa por consola."""

    system = platform.system()
    if system == "Linux":
        name, home, reason = _linux_target_user()
        folders = {key: _linux_folder(home, key) for key in FOLDER_KEYS}
    elif system == "Windows":
        name, home, sid, reason = _windows_target_user()
        folders = {key: _windows_folder(home, sid, key) for key in FOLDER_KEYS}
    else:
        name, home, reason = os.path.basename(os.path.expanduser("~")), os.path.expanduser("~"), "usuario que ejecuta el agente"
        folders = {key: os.path.join(home, _DEFAULT_NAMES[key]) for key in FOLDER_KEYS}

    print(f"ALFA-Sentinel: usuario protegido '{name}' ({reason}), carpeta {home}")
    return name, home, folders


def user_home():
    return get_target_user()[1]


def user_folder(key):
    return get_target_user()[2][key]
