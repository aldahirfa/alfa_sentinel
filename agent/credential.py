import json
import os

from config import CREDENTIAL_FILE


def save_credential(credential):
    data = {
        "credential": credential
    }

    # Solo el dueño (root / Administrador, que es quien corre el agente)
    # puede leerla. En Windows el instalador además restringe el acceso
    # con permisos del sistema de archivos.
    fd = os.open(CREDENTIAL_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as file:
        json.dump(data, file)


def load_credential():

    if not os.path.exists(CREDENTIAL_FILE):
        return None

    with open(CREDENTIAL_FILE, "r") as file:
        data = json.load(file)

    return data["credential"]
