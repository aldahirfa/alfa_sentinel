"""Lanzador del servidor ALFA-Sentinel -- SOLO por HTTPS.

Reemplaza a 'uvicorn asgi:app --host ... --port ...' para uso real: lee
la configuración TLS de server/.env, exige que existan el certificado y
la clave (ver generar_certificados.py) y fuerza TLS 1.2 como mínimo.

    python run_server.py                 # HTTPS en 0.0.0.0:8000
    python run_server.py --port 8443
    python run_server.py --insecure-dev  # HTTP, SOLO escuchando en 127.0.0.1

Variables de server/.env (todas opcionales):
    SERVER_HOST=0.0.0.0
    SERVER_PORT=8000
    TLS_CERT_FILE=certs/server.crt
    TLS_KEY_FILE=certs/server.key

--insecure-dev existe para depurar en la propia máquina: nunca expone
HTTP a la red (se fuerza 127.0.0.1) y el agente, por su lado, solo
acepta http:// si el servidor es 127.0.0.1/localhost.
"""

import argparse
import os
import ssl
import sys

from dotenv import load_dotenv
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve(path):
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def main():
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    parser = argparse.ArgumentParser(description="Servidor ALFA-Sentinel (HTTPS)")
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SERVER_PORT", "8000")))
    parser.add_argument("--insecure-dev", action="store_true",
                        help="HTTP sin cifrar, solo en 127.0.0.1 (depuración local)")
    args = parser.parse_args()

    # main.py/asgi.py importan con rutas relativas (StaticFiles("static"),
    # generated_reports...) -- se arranca siempre desde server/.
    os.chdir(BASE_DIR)
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    if args.insecure_dev:
        os.environ["ALFA_TLS_ENABLED"] = "0"
        print("⚠ MODO INSEGURO (--insecure-dev): HTTP sin cifrar, solo en 127.0.0.1")
        uvicorn.run("asgi:app", host="127.0.0.1", port=args.port)
        return

    cert_file = _resolve(os.getenv("TLS_CERT_FILE", "certs/server.crt"))
    key_file = _resolve(os.getenv("TLS_KEY_FILE", "certs/server.key"))

    missing = [p for p in (cert_file, key_file) if not os.path.isfile(p)]
    if missing:
        print("No se encontró el certificado TLS del servidor:")
        for p in missing:
            print(f"  - {p}")
        print("Genéralo primero con:  python generar_certificados.py --ip <IP_DEL_SERVIDOR>")
        sys.exit(1)

    # main.py lee esta variable para activar cookie Secure + HSTS.
    os.environ["ALFA_TLS_ENABLED"] = "1"

    config = uvicorn.Config(
        "asgi:app",
        host=args.host,
        port=args.port,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
        proxy_headers=False,
    )
    # uvicorn no expone la versión mínima de TLS como opción: se carga
    # la config (crea el SSLContext) y se endurece antes de arrancar.
    # Server.serve() no vuelve a llamar a load() si ya está cargada.
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    config.ssl.options |= ssl.OP_NO_COMPRESSION
    config.ssl.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!DSS")

    print(f"ALFA-Sentinel escuchando en https://{args.host}:{args.port} (TLS >= 1.2)")
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
