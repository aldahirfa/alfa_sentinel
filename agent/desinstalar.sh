#!/usr/bin/env bash
# Desinstalador del agente ALFA-Sentinel para Linux.
#
#   sudo /opt/alfa-sentinel/desinstalar.sh
#
# Detiene y elimina el servicio, levanta el aislamiento de red si el
# equipo quedó aislado (para no dejarlo sin red) y borra el agente.
# Los honeyfiles de las carpetas del usuario (ALFA_ARCHIVOS) no se tocan.
set -uo pipefail

DEST="/opt/alfa-sentinel"
SERVICE="alfa-sentinel"

if [[ $EUID -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

read -rp "¿Desinstalar el agente ALFA-Sentinel de este equipo? [s/N]: " r
[[ "${r,,}" == "s" ]] || { echo "Cancelado."; exit 0; }

systemctl disable --now "$SERVICE" >/dev/null 2>&1
rm -f "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload

if [[ -x "$DEST/.venv/bin/python" ]]; then
    echo "Levantando el aislamiento de red (si estaba activo)..."
    (cd "$DEST" && .venv/bin/python -c "import isolation_executor as ie; print(ie.release_if_isolated())") || true
fi

rm -rf "$DEST"
echo "✓ Agente desinstalado."
echo "  El equipo sigue figurando en la consola: puedes revocarlo desde allí."
