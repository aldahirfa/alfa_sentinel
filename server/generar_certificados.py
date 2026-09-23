"""Genera la PKI propia de ALFA-Sentinel para cifrar agente <-> servidor.

Crea (si no existen) dos cosas en server/certs/:

  ca.crt / ca.key         Autoridad certificadora PROPIA del despliegue.
                          ca.key es el secreto más importante: con ella se
                          puede emitir un certificado que los agentes
                          aceptarían. No sale nunca de la máquina servidor.
  server.crt / server.key Certificado TLS que presenta uvicorn, firmado por
                          la CA anterior, válido para las IP/nombres que se
                          pasen con --ip / --dns (más localhost y 127.0.0.1).

Y copia ca.crt (solo la parte PÚBLICA) a agent/certs/ca.crt: el agente
confía únicamente en esa CA -- no en el almacén de certificados de
Windows -- así que un atacante en la red no puede presentar otro
certificado aunque sea "válido" para una CA comercial (pinning de CA).

Si la CA ya existe se reutiliza: volver a correr el script con otra IP
solo re-emite server.crt, y los agentes ya instalados siguen confiando.

Uso (desde server/, con el venv del servidor activado):
    python generar_certificados.py --ip 192.168.81.1
    python generar_certificados.py --ip 192.168.81.1 --dns alfa-sentinel.local
    python generar_certificados.py --ip 10.0.0.5 --force-server   (re-emitir)
"""

import argparse
import datetime
import ipaddress
import os
import shutil
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
AGENT_CERTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "agent", "certs")

CA_CERT = os.path.join(CERTS_DIR, "ca.crt")
CA_KEY = os.path.join(CERTS_DIR, "ca.key")
SERVER_CERT = os.path.join(CERTS_DIR, "server.crt")
SERVER_KEY = os.path.join(CERTS_DIR, "server.key")

CA_DAYS = 3650          # 10 años: la CA se distribuye con cada agente
SERVER_DAYS = 825       # máximo aceptado por navegadores para certificados de servidor


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _write_key(path, key):
    data = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # Se crea con permisos restringidos desde el inicio (en Linux; en
    # Windows NTFS hereda los permisos de la carpeta del usuario).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _write_cert(path, cert):
    with open(path, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))


def _load_ca():
    with open(CA_KEY, "rb") as fh:
        key = serialization.load_pem_private_key(fh.read(), password=None)
    with open(CA_CERT, "rb") as fh:
        cert = x509.load_pem_x509_certificate(fh.read())
    return key, cert


def create_ca():
    key = ec.generate_private_key(ec.SECP384R1())
    name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ALFA-Sentinel"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ALFA-Sentinel CA interna"),
    ])
    now = _now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA384())
    )
    _write_key(CA_KEY, key)
    _write_cert(CA_CERT, cert)
    return key, cert


def create_server_cert(ca_key, ca_cert, ips, dns_names):
    key = ec.generate_private_key(ec.SECP256R1())

    san = [x509.DNSName("localhost")] + [x509.DNSName(d) for d in dns_names]
    all_ips = ["127.0.0.1"] + [ip for ip in ips if ip != "127.0.0.1"]
    san += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in all_ips]

    common_name = dns_names[0] if dns_names else (ips[0] if ips else "localhost")
    now = _now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ALFA-Sentinel"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=SERVER_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=False, key_agreement=False,
                key_cert_sign=False, crl_sign=False, content_commitment=False,
                data_encipherment=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(SERVER_KEY, key)
    _write_cert(SERVER_CERT, cert)
    return cert


def main():
    parser = argparse.ArgumentParser(description="Genera la CA y el certificado TLS de ALFA-Sentinel")
    parser.add_argument("--ip", action="append", default=[],
                        help="IP con la que los agentes llegan al servidor (repetible)")
    parser.add_argument("--dns", action="append", default=[],
                        help="Nombre DNS del servidor (repetible, opcional)")
    parser.add_argument("--force-server", action="store_true",
                        help="Re-emite server.crt aunque ya exista (la CA se conserva)")
    args = parser.parse_args()

    for ip in args.ip:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            sys.exit(f"IP inválida: {ip}")

    if not args.ip and not args.dns:
        print("⚠ No se indicó --ip ni --dns: el certificado solo servirá para localhost/127.0.0.1.")
        print("  Los agentes en otros equipos necesitan la IP real, ej: --ip 192.168.81.1")

    os.makedirs(CERTS_DIR, exist_ok=True)

    if os.path.exists(CA_CERT) and os.path.exists(CA_KEY):
        ca_key, ca_cert = _load_ca()
        print(f"CA existente reutilizada: {CA_CERT}")
    else:
        ca_key, ca_cert = create_ca()
        print(f"CA nueva creada:          {CA_CERT}")

    if os.path.exists(SERVER_CERT) and not args.force_server:
        print(f"server.crt ya existe (usa --force-server para re-emitirlo): {SERVER_CERT}")
    else:
        cert = create_server_cert(ca_key, ca_cert, args.ip, args.dns)
        fp = cert.fingerprint(hashes.SHA256()).hex(":").upper()
        print(f"Certificado de servidor:  {SERVER_CERT}")
        extra = [x for x in args.ip + args.dns if x not in ("127.0.0.1", "localhost")]
        print(f"  válido para: localhost, 127.0.0.1{''.join(', ' + x for x in extra)}")
        print(f"  vence:       {cert.not_valid_after_utc:%Y-%m-%d}")
        print(f"  SHA-256:     {fp}")

    os.makedirs(AGENT_CERTS_DIR, exist_ok=True)
    shutil.copyfile(CA_CERT, os.path.join(AGENT_CERTS_DIR, "ca.crt"))
    print(f"CA pública copiada al agente: {os.path.join(AGENT_CERTS_DIR, 'ca.crt')}")
    print()
    print("IMPORTANTE: certs/ca.key y certs/server.key son secretos -- no se suben a git")
    print("ni se copian a los endpoints. A cada agente solo se le entrega ca.crt.")


if __name__ == "__main__":
    main()
