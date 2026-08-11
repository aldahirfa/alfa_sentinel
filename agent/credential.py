import json
import os

from config import CREDENTIAL_FILE


def save_credential(credential):
    data = {
        "credential": credential
    }

    with open(CREDENTIAL_FILE, "w") as file:
        json.dump(data, file)


def load_credential():

    if not os.path.exists(CREDENTIAL_FILE):
        return None

    with open(CREDENTIAL_FILE, "r") as file:
        data = json.load(file)

    return data["credential"]
