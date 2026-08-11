import bcrypt


def hash_password(plain_password: str) -> str:
    """Convierte una contraseña en texto plano en un hash para guardar
    en users.password_hash. bcrypt genera una sal aleatoria en cada
    llamada, así que la misma contraseña nunca produce el mismo hash
    dos veces."""

    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Compara una contraseña recién escrita contra el hash guardado."""

    password_bytes = plain_password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")

    return bcrypt.checkpw(password_bytes, hash_bytes)
