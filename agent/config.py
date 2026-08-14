# Versión de este agente -- se manda en el enrollment porque
# agents.agent_version es NOT NULL en la nueva estructura de la base
# (alfa_sentinel). Subir esto a mano cuando cambie algo relevante del
# agente; no hay todavía un mecanismo automático de versionado.
AGENT_VERSION = "1.0.0"

SERVER_URL = "http://127.0.0.1:8000"

ENROLLMENT_URL = f"{SERVER_URL}/enrollment"

AUTHENTICATION_URL = f"{SERVER_URL}/agent/test"

HEARTBEAT_URL = f"{SERVER_URL}/agent/heartbeat"

EVENTS_URL = f"{SERVER_URL}/agent/events"

ALERTS_URL = f"{SERVER_URL}/agent/alerts"

HONEYFILE_POLICY_URL = f"{SERVER_URL}/agent/honeyfile-policy"

HONEYFILE_POLICY_REPORT_URL = f"{SERVER_URL}/agent/honeyfile-policy/report"

RULE_POLICY_URL = f"{SERVER_URL}/agent/rule-policy"

# PENDIENTE: reemplaza esto con el token que te devuelva
# POST /enrollment-tokens (ver instrucciones). Es de un solo uso y
# expira a los 15 minutos.
ENROLLMENT_TOKEN = "CW99LGsuVTCJN_7wfN31Teaz-dz9oKOp-kXfvmdDNtM"

CREDENTIAL_FILE = "agent_credential.json"
