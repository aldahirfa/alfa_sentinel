#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "No se encontró agent/.venv/bin/python."
  echo "Crea/activa el entorno virtual del agente antes de ejecutar el laboratorio."
  exit 1
fi

exec .venv/bin/python rule_lab.py "$@"
