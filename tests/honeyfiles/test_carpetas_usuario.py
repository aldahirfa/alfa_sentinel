"""Qué usuario protege el agente y dónde están sus carpetas reales
(agent/user_folders.py, 2026-09-25). No requiere servidor.

Se simulan los datos del SO (usuarios de Linux, registro de Windows) para
probar en cualquier máquina los casos que importan en el sistema final:
agente lanzado con sudo, agente como servicio (root / SYSTEM), Ubuntu en
español (~/Escritorio) y Windows con OneDrive.

Ejecutar: python tests/honeyfiles/test_carpetas_usuario.py
"""
import os
import shutil
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import user_folders as uf  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


def pw(name, uid, home, shell="/bin/bash"):
    return types.SimpleNamespace(pw_name=name, pw_uid=uid, pw_dir=home, pw_shell=shell)


class LinuxSim:
    def __init__(self, users, euid, env):
        self.users, self.euid, self.env = users, euid, env

    def __enter__(self):
        fake_pwd = types.ModuleType("pwd")
        fake_pwd.getpwall = lambda: list(self.users)
        fake_pwd.getpwnam = lambda n: next(u for u in self.users if u.pw_name == n)
        fake_pwd.getpwuid = lambda i: next(u for u in self.users if u.pw_uid == i)
        self.saved = (sys.modules.get("pwd"), uf.platform.system, getattr(os, "geteuid", None), dict(os.environ))
        sys.modules["pwd"] = fake_pwd
        uf.platform.system = lambda: "Linux"
        os.geteuid = lambda: self.euid
        for k in ("ALFA_SENTINEL_USER", "SUDO_USER"):
            os.environ.pop(k, None)
        os.environ.update(self.env)
        uf.get_target_user.cache_clear()
        return self

    def __exit__(self, *a):
        pwd_mod, uf.platform.system, geteuid, env = self.saved
        if pwd_mod is None:
            sys.modules.pop("pwd", None)
        else:
            sys.modules["pwd"] = pwd_mod
        if geteuid is None:
            del os.geteuid
        else:
            os.geteuid = geteuid
        os.environ.clear()
        os.environ.update(env)
        uf.get_target_user.cache_clear()


tmp = tempfile.mkdtemp(prefix="alfa_users_")
try:
    home_es = os.path.join(tmp, "home", "aldahir")
    home_otro = os.path.join(tmp, "home", "invitado")
    root_home = os.path.join(tmp, "root")
    for d in (home_es, home_otro, root_home):
        os.makedirs(d)
    os.makedirs(os.path.join(home_es, ".config"))
    with open(os.path.join(home_es, ".config", "user-dirs.dirs"), "w", encoding="utf-8") as f:
        f.write('# generado por xdg-user-dirs-update\n'
                'XDG_DESKTOP_DIR="$HOME/Escritorio"\n'
                'XDG_DOCUMENTS_DIR="$HOME/Documentos"\n'
                'XDG_DOWNLOAD_DIR="$HOME/Descargas"\n'
                'XDG_PICTURES_DIR="$HOME/Imágenes"\n'
                'XDG_VIDEOS_DIR="$HOME/"\n')  # carpeta deshabilitada -> nombre estándar

    users = [
        pw("root", 0, root_home),
        pw("daemon", 1, "/usr/sbin", "/usr/sbin/nologin"),
        pw("aldahir", 1000, home_es),
        pw("invitado", 1001, home_otro),
        pw("nobody", 65534, "/nonexistent", "/usr/sbin/nologin"),
    ]

    # CU-01: lanzado con sudo (sin HOME="$HOME") -> el usuario que lanzó sudo, no root.
    with LinuxSim(users, euid=0, env={"SUDO_USER": "aldahir", "HOME": root_home}):
        name, home, folders = uf.get_target_user()
        check("CU-01: Linux con sudo -> protege a SUDO_USER, no a root", name == "aldahir" and home == home_es, (name, home))
        check("CU-02: Ubuntu en español -> Escritorio real (no un 'Desktop' falso)",
              folders["DESKTOP"] == os.path.join(home_es, "Escritorio"), folders["DESKTOP"])
        check("CU-02: Documentos, Descargas e Imágenes con su nombre real",
              folders["DOCUMENTS"].endswith("Documentos") and folders["DOWNLOADS"].endswith("Descargas")
              and folders["PICTURES"].endswith("Imágenes"), folders)
        check("CU-03: carpeta deshabilitada en user-dirs.dirs ($HOME/) -> nombre estándar",
              folders["VIDEOS"] == os.path.join(home_es, "Videos"), folders["VIDEOS"])
        check("CU-03: carpeta no listada -> nombre estándar", folders["MUSIC"] == os.path.join(home_es, "Music"), folders["MUSIC"])

    # CU-04: como servicio (root, sin SUDO_USER) -> usuario real más antiguo; ignora cuentas de sistema.
    with LinuxSim(users, euid=0, env={"HOME": root_home}):
        name, home, _ = uf.get_target_user()
        check("CU-04: Linux como servicio -> usuario real (UID 1000), nunca root/daemon/nobody", name == "aldahir", name)

    # CU-05: ALFA_SENTINEL_USER tiene prioridad.
    with LinuxSim(users, euid=0, env={"SUDO_USER": "aldahir", "ALFA_SENTINEL_USER": "invitado"}):
        name, _, folders = uf.get_target_user()
        check("CU-05: ALFA_SENTINEL_USER tiene prioridad", name == "invitado", name)
        check("CU-05: sin user-dirs.dirs -> nombres estándar", folders["DESKTOP"] == os.path.join(home_otro, "Desktop"), folders["DESKTOP"])

    # CU-06: sin privilegios -> el propio usuario.
    with LinuxSim(users, euid=1001, env={}):
        check("CU-06: Linux sin sudo -> el propio usuario", uf.get_target_user()[0] == "invitado")

    # --- Windows como servicio (SYSTEM) ---
    profile_a = os.path.join(tmp, "Users", "Usuario Antiguo")
    profile_b = os.path.join(tmp, "Users", "Ana Perez")
    for d in (profile_a, profile_b):
        os.makedirs(d)
    registry = {
        ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"): {
            "_subkeys": ["S-1-5-18", "S-1-5-21-1-1001", "S-1-5-21-1-1002"],
        },
        ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\S-1-5-21-1-1001"): {
            "ProfileImagePath": profile_a, "LocalProfileLoadTimeHigh": 1, "LocalProfileLoadTimeLow": 5},
        ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\S-1-5-21-1-1002"): {
            "ProfileImagePath": profile_b, "LocalProfileLoadTimeHigh": 2, "LocalProfileLoadTimeLow": 0},
        ("HKU", r"S-1-5-21-1-1002\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"): {
            "Desktop": r"%USERPROFILE%\OneDrive\Escritorio",
            "Personal": r"%USERPROFILE%\OneDrive\Documentos",
        },
    }

    class Handle:
        def __init__(self, hive, path):
            self.hive, self.path = hive, path
            if (hive, path) not in registry:
                raise OSError("no existe")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    fake_winreg = types.ModuleType("winreg")
    fake_winreg.HKEY_LOCAL_MACHINE, fake_winreg.HKEY_USERS = "HKLM", "HKU"
    fake_winreg.OpenKey = lambda parent, sub: Handle(parent.hive, parent.path + "\\" + sub) if isinstance(parent, Handle) else Handle(parent, sub)

    def enum_key(handle, i):
        subkeys = registry[(handle.hive, handle.path)].get("_subkeys", [])
        if i >= len(subkeys):
            raise OSError("no hay más")
        return subkeys[i]

    def query_value(handle, name):
        values = registry[(handle.hive, handle.path)]
        if name not in values:
            raise OSError("no existe")
        return values[name], 1

    fake_winreg.EnumKey, fake_winreg.QueryValueEx = enum_key, query_value

    saved = (sys.modules.get("winreg"), uf.platform.system, uf._windows_is_system_account)
    sys.modules["winreg"] = fake_winreg
    uf.platform.system = lambda: "Windows"
    uf._windows_is_system_account = lambda: True
    os.environ.pop("ALFA_SENTINEL_USER", None)
    uf.get_target_user.cache_clear()
    try:
        name, home, folders = uf.get_target_user()
        check("CU-07: Windows como SYSTEM -> perfil usado más recientemente (no systemprofile)", home == profile_b, (name, home))
        check("CU-08: Windows con OneDrive -> escritorio real dentro de OneDrive",
              folders["DESKTOP"] == os.path.join(profile_b, "OneDrive", "Escritorio"), folders["DESKTOP"])
        check("CU-08: %USERPROFILE% se reemplaza por el perfil del usuario, no el del servicio",
              folders["DOCUMENTS"] == os.path.join(profile_b, "OneDrive", "Documentos"), folders["DOCUMENTS"])
        check("CU-09: carpeta sin valor en el registro -> nombre estándar",
              folders["DOWNLOADS"] == os.path.join(profile_b, "Downloads"), folders["DOWNLOADS"])
    finally:
        winreg_mod, uf.platform.system, uf._windows_is_system_account = saved
        if winreg_mod is None:
            sys.modules.pop("winreg", None)
        else:
            sys.modules["winreg"] = winreg_mod
        uf.get_target_user.cache_clear()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
total = len(RESULTS)
passed = sum(1 for _, ok in RESULTS if ok)
print(f"{passed}/{total} pruebas pasaron")
if passed != total:
    sys.exit(1)
