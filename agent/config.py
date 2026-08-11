SERVER_URL = "http://127.0.0.1:8000"

ENROLLMENT_URL = f"{SERVER_URL}/enrollment"

AUTHENTICATION_URL = f"{SERVER_URL}/agent/test"

HEARTBEAT_URL = f"{SERVER_URL}/agent/heartbeat"

EVENTS_URL = f"{SERVER_URL}/agent/events"

ALERTS_URL = f"{SERVER_URL}/agent/alerts"

# PENDIENTE: reemplaza esto con el token que te devuelva
# POST /enrollment-tokens (ver instrucciones). Es de un solo uso y
# expira a los 15 minutos.
ENROLLMENT_TOKEN = "CW99LGsuVTCJN_7wfN31Teaz-dz9oKOp-kXfvmdDNtM"

CREDENTIAL_FILE = "agent_credential.json"
