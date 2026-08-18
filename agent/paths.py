"""Resolución de rutas del agente -- rutas lógicas de honeyfiles
(2026-08-17) y raíces globales de monitorización del endpoint
(2026-08-17, ampliado -- ver PENDIENTES.md, "Honeyfiles + monitorización
completa del endpoint + detección por comportamiento anómalo +
correlación de indicadores + despliegue, reconciliación y HR-03/HR-08").
Único punto del código donde se decide "¿dónde vive físicamente esta
ruta lógica en ESTA máquina, en ESTE modo?" -- ni honeyfile_deployer.py,
ni file_monitor.py, ni ningún otro módulo del agente contienen ifs de
desarrollo/producción por su cuenta, todos llaman a las funciones de
este módulo.

Las plantillas ('honeyfile_templates.file_path' en la base) guardan
una RUTA LÓGICA (DOCUMENTS, DESKTOP, DOWNLOADS, PICTURES), no una ruta
absoluta ni un nombre de usuario concreto -- la misma plantilla sirve
para cualquier endpoint, sea cual sea el usuario real que esté logueado
ahí. Ver database/schema.sql, tabla honeyfile_templates.
"""

import os
import platform


# Las 4 rutas lógicas que puede usar una plantilla de honeyfile
# (sección 19 de la especificación) -- coinciden con las carpetas de
# usuario más realistas para un señuelo (documentos, escritorio,
# descargas, imágenes). No se define todavía una lista obligatoria de
# CUÁNTOS honeyfiles debe haber en cada una -- eso lo decide
# honeyfile_templates + auto_deploy + asignación, no este módulo.
LOGICAL_PATHS = {"DOCUMENTS", "DESKTOP", "DOWNLOADS", "PICTURES"}

# Superset para la MONITORIZACIÓN GLOBAL del endpoint (sección 3/26 de
# la especificación de monitorización completa): el agente observa
# actividad en TODO el endpoint, no solo en las 4 carpetas donde puede
# haber honeyfiles -- Videos y Music se agregan acá porque el ejemplo
# de la propia especificación (sección 4) describe ransomware
# modificando archivos en Videos sin tocar ningún honeyfile.
GLOBAL_MONITORED_LOGICAL_KEYS = LOGICAL_PATHS | {"VIDEOS", "MUSIC"}

# Nombre real de la subcarpeta por SO -- Windows y Linux usan el mismo
# nombre en inglés para estas 6 carpetas estándar, así que no hace
# falta una tabla separada por plataforma; se deja como función (no
# dict plano) por si algún día hiciera falta una excepción puntual (ej.
# localización regional).
def _subfolder_for(logical_key):
    return {
        "DOCUMENTS": "Documents",
        "DESKTOP": "Desktop",
        "DOWNLOADS": "Downloads",
        "PICTURES": "Pictures",
        "VIDEOS": "Videos",
        "MUSIC": "Music",
    }[logical_key]


# Carpeta donde se agrupan los honeyfiles dentro de la ruta lógica que
# le corresponda a cada plantilla (sección 5 de la especificación:
# "Esta carpeta representa ZONA ADMINISTRADA DE HONEYFILES. NO
# representa un único honeyfile"). Por ejemplo, en producción Windows
# con la ruta lógica DOCUMENTS: C:\Users\<usuario>\Documents\ALFA_ARCHIVOS\.
# "Solo UNA por endpoint/ruta lógica" (sección 17): se crea como
# subcarpeta de la ruta lógica correspondiente, nunca una carpeta
# global única compartida entre las 4 rutas lógicas.
ALFA_ARCHIVOS_FOLDER_NAME = "ALFA_ARCHIVOS"

# Carpeta de pruebas para HONEYFILES -- SOLO para
# ALFA_SENTINEL_ENV=development (secciones 8/14 de la especificación:
# ruta explícita pedida por el usuario, "agent\\honeyfiles\\ALFA_ARCHIVOS\\").
# Ruta relativa a este archivo (agent/paths.py), no hardcodeada a la
# máquina de un usuario puntual -- en el checkout del repo esto
# resuelve a 'agent/honeyfiles', sea cual sea la carpeta donde esté
# clonado. Las 4 rutas lógicas de honeyfile colapsan TODAS acá en
# desarrollo (a propósito, sin cambios respecto a como ya funcionaba) --
# la separación por carpeta distinta solo importa en producción.
_DEV_HONEYFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "honeyfiles")

# Carpeta de pruebas para la MONITORIZACIÓN GLOBAL del resto del
# endpoint (sección 35: "reducir el ruido en development" -- antes el
# agente vigilaba '.', su propio directorio de trabajo, lo que incluía
# .venv/__pycache__/.git; ahora vigila carpetas dedicadas, una por cada
# ruta lógica, igual que pasaría en un endpoint real con Documents/
# Desktop/Downloads/Videos/Pictures/Music separados). Deliberadamente
# SEPARADA de _DEV_HONEYFILES_DIR: son dos carpetas de prueba con
# propósitos distintos (una es "dónde viven los honeyfiles hoy en
# dev", la otra es "cómo simulo las demás carpetas del usuario para
# probar detección de comportamiento anómalo lejos de los honeyfiles").
_DEV_ENDPOINT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_endpoint")

_env_mode_announced = False


def get_env_mode():
    """'development' o 'production', leído de la variable de entorno
    ALFA_SENTINEL_ENV. Sin variable definida, el valor por defecto es
    'development' -- a propósito, porque HOY el proyecto está en fase
    de desarrollo local (ver especificación, sección 44: "estoy
    actualmente en .venv... primero validación funcional local") y se
    pidió explícitamente que los honeyfiles aparezcan en la carpeta de
    pruebas sin que haga falta configurar nada extra. Antes de un
    despliegue real hay que setear ALFA_SENTINEL_ENV=production
    explícitamente -- se imprime bien visible en qué modo arrancó el
    agente (ver _announce_env_mode) para que esto nunca pase
    desapercibido."""

    return os.environ.get("ALFA_SENTINEL_ENV", "development").strip().lower()


def _announce_env_mode():
    """Se imprime UNA sola vez por proceso, apenas se resuelve la
    primera ruta -- no en cada honeyfile, para no inundar la consola,
    pero sí siempre, para que nunca sea una sorpresa silenciosa en qué
    modo está corriendo el agente."""

    global _env_mode_announced
    if _env_mode_announced:
        return
    _env_mode_announced = True

    mode = get_env_mode()
    if mode == "production":
        print(f"ALFA-Sentinel: modo PRODUCTION -- rutas reales del sistema operativo ({platform.system()}).")
    else:
        print(
            f"ALFA-Sentinel: modo DEVELOPMENT -- honeyfiles en '{_DEV_HONEYFILES_DIR}', "
            f"resto del endpoint simulado en '{_DEV_ENDPOINT_ROOT}'. Para producción, definí "
            f"ALFA_SENTINEL_ENV=production antes de arrancar el agente."
        )


def _user_home():
    """Carpeta personal del usuario real que corre el agente -- nunca
    un nombre de usuario hardcodeado (sección 12/13 de la
    especificación de honeyfiles: "NO usar C:\\Users\\ALDAHIR FA\\...
    como ruta de producción", "no hardcodear /home/aldahir/").
    os.path.expanduser('~') ya resuelve esto de forma nativa por SO: en
    Windows lee %USERPROFILE%, en Linux/macOS $HOME."""

    return os.path.expanduser("~")


def _ensure_dir(directory):
    os.makedirs(directory, exist_ok=True)
    return directory


def resolve_logical_path(raw_path):
    """Traduce lo que trae 'honeyfile_templates.file_path' al
    directorio real en ESTA máquina donde deben vivir los HONEYFILES de
    esa plantilla -- ya anidado dentro de ALFA_ARCHIVOS (sección 17 de
    la especificación de monitorización completa: "la carpeta debe
    crearse automáticamente si no existe"), no la ruta lógica directa.

    Dos casos:
    1. Es una de las 4 rutas lógicas conocidas para honeyfiles
       (DOCUMENTS/DESKTOP/DOWNLOADS/PICTURES, sin importar mayúsculas/
       minúsculas ni espacios alrededor) -- se resuelve la carpeta BASE
       según el modo (development -> carpeta de pruebas única;
       production -> perfil real del usuario en este SO) y se le
       agrega '/ALFA_ARCHIVOS', creándola si no existe.
    2. Cualquier otro valor -- plantillas creadas ANTES de esta tarea
       pueden traer una ruta libre con %USERPROFILE%/$HOME/~ (el
       formato viejo, ver PENDIENTES.md). Se resuelve con la misma
       sustitución de siempre, SIN el subdirectorio ALFA_ARCHIVOS (no
       se les puede aplicar retroactivamente sin arriesgar que un
       honeyfile ya existente en producción deje de encontrarse) -- no
       se fuerza una migración de datos por esto."""

    _announce_env_mode()

    key = (raw_path or "").strip().upper()

    if key in LOGICAL_PATHS:
        base = _DEV_HONEYFILES_DIR if get_env_mode() != "production" else os.path.join(_user_home(), _subfolder_for(key))
        return _ensure_dir(os.path.join(base, ALFA_ARCHIVOS_FOLDER_NAME))

    # Formato legado (pre-2026-08-17): ruta libre con placeholders.
    home = _user_home()
    resolved = (raw_path or "").replace("%USERPROFILE%", home).replace("$HOME", home)
    if resolved.startswith("~"):
        resolved = home + resolved[1:]
    return os.path.normpath(resolved)


def get_monitored_roots():
    """Las carpetas que el agente debe vigilar de forma GLOBAL en este
    endpoint (secciones 3/26/27/40 de la especificación: "el agente
    debe monitorizar TODO el endpoint... ALFA_ARCHIVOS es SOLO una zona
    de decepción, no es el perímetro del monitor"). Devuelve una lista
    de rutas absolutas ÚNICAS, cada una ya creada si no existía.

    - Las 6 carpetas lógicas (Documents/Desktop/Downloads/Pictures/
      Videos/Music) -- en producción, las reales del usuario que corre
      el agente; en desarrollo, carpetas de prueba dedicadas separadas
      de la carpeta de honeyfiles (sección 35: reducir ruido, ya no se
      vigila '.' completo).
    - En desarrollo, ADEMÁS la carpeta de honeyfiles (_DEV_HONEYFILES_DIR)
      -- ahí es donde vive ALFA_ARCHIVOS en este modo (ver
      resolve_logical_path), y tiene que quedar vigilada igual que
      cualquier otra carpeta real del endpoint. En producción esto no
      hace falta aparte: ALFA_ARCHIVOS ya queda DENTRO de una de las 6
      carpetas de arriba (ej. Documents), que ya se está vigilando."""

    _announce_env_mode()

    roots = []
    seen = set()

    def add(path):
        absolute = os.path.abspath(_ensure_dir(path))
        if absolute not in seen:
            seen.add(absolute)
            roots.append(absolute)

    production = get_env_mode() == "production"

    for key in sorted(GLOBAL_MONITORED_LOGICAL_KEYS):
        if production:
            add(os.path.join(_user_home(), _subfolder_for(key)))
        else:
            add(os.path.join(_DEV_ENDPOINT_ROOT, _subfolder_for(key)))

    if not production:
        add(_DEV_HONEYFILES_DIR)

    return roots
