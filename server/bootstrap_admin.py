"""
Script de un solo uso: crea el primer usuario administrador.

Por qué hace falta ANTES que nada más: la tabla enrollment_tokens
exige un created_by que apunte a un usuario real (users.id). Sin al
menos un usuario en la base, no se puede generar un token de
enrolamiento válido, y sin token el agente no puede registrarse.

Uso (con el venv de server/ activado):
    python bootstrap_admin.py
"""

import getpass

from database import get_connection
from security import hash_password


def ensure_admin_role(cursor) -> int:

    cursor.execute(
        "SELECT id FROM roles WHERE name = 'admin';"
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO roles (name, description)
        VALUES ('admin', 'Acceso total al sistema')
        RETURNING id;
        """
    )

    return cursor.fetchone()[0]


def main():

    print("=== Creación del primer usuario administrador ===")

    username = input("Usuario: ").strip()
    full_name = input("Nombre completo: ").strip()
    email = input("Email (opcional, Enter para omitir): ").strip() or None

    password = getpass.getpass("Contraseña: ")
    password_confirm = getpass.getpass("Confirma la contraseña: ")

    if password != password_confirm:
        print("Las contraseñas no coinciden. No se creó nada.")
        return

    if len(password) < 8:
        print("Usa una contraseña de al menos 8 caracteres. No se creó nada.")
        return

    password_hash = hash_password(password)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id FROM users WHERE username = %s;",
                (username,)
            )

            if cursor.fetchone():
                print(f"Ya existe un usuario '{username}'. No se creó nada.")
                return

            role_id = ensure_admin_role(cursor)

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, full_name, email)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (username, password_hash, full_name, email)
            )

            user_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES (%s, %s);
                """,
                (user_id, role_id)
            )

            connection.commit()

        print()
        print(f"Usuario '{username}' creado con id={user_id} y rol 'admin'.")
        print("Guarda ese id: lo vas a necesitar para generar el token de enrolamiento.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
