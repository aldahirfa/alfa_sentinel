# Versión de este agente -- se manda en el enrollment porque
# agents.agent_version es NOT NULL en la nueva estructura de la base
# (alfa_sentinel). Subir esto a mano cuando cambie algo relevante del
# agente; no hay todavía un mecanismo automático de versionado.
AGENT_VERSION = "1.0.0"

SERVER_URL = "http://192.168.81.1:8000"

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

CREDENTIAL_FILE = "agent_credential.json"
