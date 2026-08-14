import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

# La contraseña real vive en .env (no se sube a git).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:220922@localhost:5432/alfa_sentinel"
)


def get_connection():
    return psycopg.connect(DATABASE_URL)
