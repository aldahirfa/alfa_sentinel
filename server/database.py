import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

# La conexión (con su contraseña) vive solo en server/.env, que no se
# sube a git. Sin valor por defecto a propósito: una contraseña escrita
# en el código queda en el historial del repositorio para siempre.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError(
        "Falta DATABASE_URL. Cópiala en server/.env, por ejemplo:\n"
        "  DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/alfa_sentinel"
    )


def get_connection():
    return psycopg.connect(DATABASE_URL)
