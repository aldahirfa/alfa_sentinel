# Versión de este agente -- se manda en el enrollment porque
# agents.agent_version es NOT NULL en la nueva estructura de la base
# (alfa_sentinel). Subir esto a mano cuando cambie algo relevante del
# agente; no hay todavía un mecanismo automático de versionado.
AGENT_VERSION = "1.0.0"

import json
import os

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración del equipo, escrita por el instalador (instalar.sh /
# instalar.ps1) junto al agente. Un servicio del sistema no recibe
# argumentos ni variables de entorno de quien lo instaló, así que todo lo
# que antes se pasaba a mano (--server, ALFA_SENTINEL_ENV, HOME) queda acá.
#   {"server_url": "...", "env_mode": "production", "protected_user": "..."}
# Las variables de entorno y los argumentos siguen teniendo prioridad.
LOCAL_CONFIG_FILE = os.path.join(AGENT_DIR, "agent_config.json")
try:
    with open(LOCAL_CONFIG_FILE, encoding="utf-8") as _f:
        LOCAL_CONFIG = json.load(_f)
except (OSError, ValueError):
    LOCAL_CONFIG = {}

if LOCAL_CONFIG.get("env_mode"):
    os.environ.setdefault("ALFA_SENTINEL_ENV", LOCAL_CONFIG["env_mode"])
if LOCAL_CONFIG.get("protected_user"):
    os.environ.setdefault("ALFA_SENTINEL_USER", LOCAL_CONFIG["protected_user"])

# HTTPS obligatorio (ver agent/transport.py y server/TLS_README.md).
SERVER_URL = (LOCAL_CONFIG.get("server_url") or "https://192.168.81.1:8000").rstrip("/")

# CA propia de ALFA-Sentinel -- la única en la que confía el agente.
# Relativa a la carpeta del agente; se puede cambiar con --ca o con la
# variable de entorno ALFA_SENTINEL_CA_FILE.
CA_CERT_FILE = "certs/ca.crt"

ENROLLMENT_URL = f"{SERVER_URL}/enrollment"

AUTHENTICATION_URL = f"{SERVER_URL}/agent/test"

HEARTBEAT_URL = f"{SERVER_URL}/agent/heartbeat"

EVENTS_URL = f"{SERVER_URL}/agent/events"

ALERTS_URL = f"{SERVER_URL}/agent/alerts"

HONEYFILE_POLICY_URL = f"{SERVER_URL}/agent/honeyfile-policy"

HONEYFILE_POLICY_REPORT_URL = f"{SERVER_URL}/agent/honeyfile-policy/report"

RULE_POLICY_URL = f"{SERVER_URL}/agent/rule-policy"

# Aislamiento real (2026-08-17, ver PENDIENTES.md, "Corrección
# definitiva del motor heurístico..."): agent/isolation_sync.py.
ISOLATION_STATUS_URL = f"{SERVER_URL}/agent/isolation-status"

ISOLATION_STATUS_REPORT_URL = f"{SERVER_URL}/agent/isolation-status/report"

# El código de enrolamiento NO se guarda en el repositorio. La consola
# central genera uno temporal con formato XXXX-XXXX, válido 15 minutos
# y de un solo uso. main.py lo recibe con --enroll y lo asigna acá solo
# durante esa ejecución.
ENROLLMENT_TOKEN = ""

# Junto al agente, no en la carpeta desde donde se lanza (un servicio
# arranca en otra carpeta de trabajo).
CREDENTIAL_FILE = os.path.join(AGENT_DIR, "agent_credential.json")
