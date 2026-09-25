#!/usr/bin/env bash
# Instalador del agente ALFA-Sentinel para Linux.
#
#   sudo ./instalar.sh
#
# Pregunta la dirección del servidor y el código de registro, y hace el
# resto: copia el agente a /opt/alfa-sentinel (solo root puede
# modificarlo), instala dependencias, registra el agente, guarda la
# configuración y lo deja como servicio que arranca con el equipo.
set -euo pipefail

DEST="/opt/alfa-sentinel"
SERVICE="alfa-sentinel"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

verde() { printf '\033[32m%s\033[0m\n' "$*"; }
rojo() { printf '\033[31m%s\033[0m\n' "$*"; }
paso() { printf '\n\033[1m[%s] %s\033[0m\n' "$1" "$2"; }
falla() { rojo "✗ $*"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

echo "=============================================="
echo "   Instalación del agente ALFA-Sentinel"
echo "=============================================="

# --- 1. Requisitos -------------------------------------------------------
paso 1/6 "Verificando requisitos"
command -v python3 >/dev/null || falla "Falta Python 3. Instálalo con: apt install python3 python3-venv"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || falla "Se necesita Python 3.10 o superior (hay $(python3 --version))."
if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    if command -v apt-get >/dev/null; then
        echo "Falta el módulo venv de Python; se instala python3-venv..."
        apt-get install -y python3-venv >/dev/null || falla "No se pudo instalar python3-venv."
    else
        falla "Falta el módulo venv de Python (paquete python3-venv)."
    fi
fi
command -v iptables >/dev/null || rojo "⚠ No se encontró iptables: el aislamiento de red no funcionará en este equipo."
command -v systemctl >/dev/null || falla "Este equipo no usa systemd; no se puede instalar el servicio."
[[ -f "$SRC/certs/ca.crt" ]] || falla "Falta certs/ca.crt junto al instalador. Cópialo desde server/certs/ca.crt."
verde "✓ Requisitos correctos"

# --- 2. Datos ------------------------------------------------------------
paso 2/6 "Datos de instalación"
CONSERVAR_REGISTRO=0
if [[ -f "$DEST/agent_credential.json" ]]; then
    read -rp "Este equipo ya está registrado. ¿Conservar el registro actual? [S/n]: " r
    [[ "${r,,}" != "n" ]] && CONSERVAR_REGISTRO=1
fi

SERVIDOR_ACTUAL="$(python3 -c "import json;print(json.load(open('$DEST/agent_config.json')).get('server_url',''))" 2>/dev/null || true)"
while true; do
    read -rp "Dirección del servidor [${SERVIDOR_ACTUAL:-https://192.168.81.1:8000}]: " SERVIDOR
    SERVIDOR="${SERVIDOR:-${SERVIDOR_ACTUAL:-https://192.168.81.1:8000}}"
    [[ "$SERVIDOR" =~ ^https://[^/]+$ ]] && break
    rojo "Debe ser https://IP:puerto, por ejemplo https://192.168.81.1:8000"
done

USUARIO_DEFECTO="${SUDO_USER:-$(logname 2>/dev/null || true)}"
while true; do
    read -rp "Usuario del equipo a proteger [${USUARIO_DEFECTO}]: " USUARIO
    USUARIO="${USUARIO:-$USUARIO_DEFECTO}"
    [[ -n "$USUARIO" && "$USUARIO" != "root" ]] && id "$USUARIO" >/dev/null 2>&1 && break
    rojo "Indica un usuario existente del equipo (no root)."
done

# --- 3. Copia ------------------------------------------------------------
paso 3/6 "Copiando el agente a $DEST"
systemctl stop "$SERVICE" 2>/dev/null || true
mkdir -p "$DEST"
tar -C "$SRC" \
    --exclude=.venv --exclude=__pycache__ --exclude=agent_credential.json --exclude=agent_config.json \
    --exclude=isolation_state.json --exclude=logs --exclude=honeyfiles --exclude=test_endpoint \
    --exclude=test_files --exclude='*.pyc' -cf - . | tar -C "$DEST" -xf -
cat > "$DEST/agent_config.json" <<EOF
{"server_url": "$SERVIDOR", "env_mode": "production", "protected_user": "$USUARIO"}
EOF
chown -R root:root "$DEST"
chmod 755 "$DEST"
chmod 600 "$DEST/agent_config.json"
verde "✓ Agente copiado"

# --- 4. Dependencias -----------------------------------------------------
paso 4/6 "Instalando dependencias (puede tardar un minuto)"
[[ -x "$DEST/.venv/bin/python" ]] || python3 -m venv "$DEST/.venv"
"$DEST/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$DEST/requirements.txt" \
    || falla "No se pudieron instalar las dependencias (¿hay conexión a internet?)."
verde "✓ Dependencias instaladas"

# --- 5. Registro ---------------------------------------------------------
paso 5/6 "Registrando el equipo en el servidor"
if [[ $CONSERVAR_REGISTRO -eq 1 ]]; then
    verde "✓ Se conserva el registro existente"
else
    rm -f "$DEST/agent_credential.json"
    for intento in 1 2 3; do
        read -rp "Código de registro (Consola > Administración > Agentes, ej. ABCD-EFGH): " CODIGO
        if (cd "$DEST" && .venv/bin/python main.py --enroll "$CODIGO" >/tmp/alfa-registro.log 2>&1); then
            verde "✓ Equipo registrado"
            break
        fi
        rojo "✗ $(grep -E 'rechazó|contactar|certificado|⚠' /tmp/alfa-registro.log | tail -1)"
        [[ $intento -eq 3 ]] && falla "No se pudo registrar el equipo. Detalle en /tmp/alfa-registro.log"
        echo "Genera un código nuevo en la consola e inténtalo otra vez."
    done
    chmod 600 "$DEST/agent_credential.json"
fi

# --- 6. Servicio ---------------------------------------------------------
paso 6/6 "Instalando el servicio"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Agente ALFA-Sentinel (detección temprana de ransomware)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DEST
ExecStart=$DEST/.venv/bin/python $DEST/main.py --service
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now "$SERVICE" >/dev/null 2>&1
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    verde "✓ Servicio en ejecución"
else
    falla "El servicio no arrancó. Revisa: journalctl -u $SERVICE -n 50"
fi

echo
verde "=============================================="
verde "   Instalación completa"
verde "=============================================="
echo "El equipo aparecerá 'En línea' en la consola en unos segundos."
echo "  Estado:      systemctl status $SERVICE"
echo "  Registro:    $DEST/logs/agente.log"
echo "  Desinstalar: sudo $DEST/desinstalar.sh"
