#!/usr/bin/env bash
# Guardián del agente ALFA-Sentinel para Linux (2026-10-06).
#
# Mismo objetivo que guardian.ps1 en Windows: en una prueba con LockBit real,
# el ransomware terminó el agente ANTES de cifrar y no hubo alerta ni
# aislamiento. Si el agente muere sin un cierre normal, este script:
#   1. aísla el equipo (mismas cadenas de iptables que isolation_executor.py,
#      así la consola lo libera igual que cualquier otro aislamiento);
#   2. avisa al servidor con la regla "Agente Detenido Inesperadamente"
#      (peso 100 -> CRÍTICO -> incidente y orden de aislamiento);
#   3. deja estado/agente_terminado.json por si el aviso no llegó: el agente
#      lo reporta al volver a iniciarse.
#
# Lo ejecuta systemd en el instante en que el servicio se detiene
# (ExecStopPost=, ver instalar.sh), con SERVICE_RESULT, EXIT_CODE y
# EXIT_STATUS. NO actúa si:
#   - el equipo se está apagando o reiniciando;
#   - alguien pidió detenerlo (systemctl stop/restart, instalador,
#     desinstalador): hay un trabajo "stop" o "restart" del servicio en curso;
#   - el agente terminó por su cuenta con un error (p. ej. sin servidor).
# Matarlo con una señal, o mandarle SIGTERM sin que nadie haya pedido la
# detención, se trata como un ataque.
#
#   --simular: pruebas. Hace todo salvo tocar el firewall y avisar al servidor.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="alfa-sentinel"
LOG="$DIR/logs/guardian.log"
ESTADO="$DIR/estado"
REGLA="Agente Detenido Inesperadamente"
SIMULAR=0
[[ "${1:-}" == "--simular" ]] && SIMULAR=1

log() { mkdir -p "$DIR/logs"; echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

campo_json() {  # campo_json archivo clave  (valores simples de una línea)
    sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$1" 2>/dev/null | head -n 1
}

# --- 1. ¿Cierre normal o terminación forzada? ----------------------------
RESULTADO="${SERVICE_RESULT:-desconocido}"
SALIDA="${EXIT_CODE:-desconocido}"
ESTADO_SALIDA="${EXIT_STATUS:-}"

if [[ "$RESULTADO" == "watchdog" ]]; then
    log "El agente estaba congelado (sin latido) y systemd lo reinicia: no es un ataque, no se aísla."
    exit 0
fi
if [[ "$(systemctl is-system-running 2>/dev/null)" == "stopping" ]]; then
    log "El agente se detuvo porque el equipo se está apagando."
    exit 0
fi
if systemctl list-jobs --no-legend 2>/dev/null | grep -Eq "[[:space:]]$SERVICE\.service[[:space:]]+(stop|restart)[[:space:]]"; then
    log "El agente se detuvo a pedido (systemctl, instalador o desinstalador)."
    exit 0
fi
if [[ "$SALIDA" == "exited" && "$ESTADO_SALIDA" != "0" ]]; then
    log "El agente terminó por su cuenta con un error (código $ESTADO_SALIDA): no es un ataque."
    exit 0
fi

log "ALERTA: el agente fue terminado de forma inesperada (systemd: $RESULTADO, $SALIDA ${ESTADO_SALIDA}). Aislando el equipo y avisando al servidor."

# --- 2. Configuración ----------------------------------------------------
URL="$(campo_json "$DIR/agent_config.json" server_url)"
MODO="$(campo_json "$DIR/agent_config.json" env_mode)"
CRED="$(campo_json "$DIR/agent_credential.json" credential)"
URL="${URL%/}"
HOSTPORT="${URL#https://}"
HOST="${HOSTPORT%%:*}"
PUERTO="${HOSTPORT##*:}"
[[ "$PUERTO" == "$HOSTPORT" ]] && PUERTO=443

if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    IPS="$HOST"
else
    IPS="$(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
fi

REAL=0
case "${MODO,,}" in production|controlled_test|laboratory) REAL=1 ;; esac
[[ $SIMULAR -eq 1 ]] && REAL=0

# --- 3. Aislamiento (equivalente a isolation_executor.py::_isolate_linux) -
aislar() {
    if [[ -z "$HOST" || -z "${IPS// /}" ]]; then
        echo "FALLÓ: no se pudo determinar la IP del servidor desde agent_config.json"
        return
    fi
    if [[ $REAL -eq 0 ]]; then
        echo "SIMULADO: se habría dejado solo ${IPS% }:$PUERTO/tcp."
        return
    fi
    local tool cadena padre ip
    for tool in iptables ip6tables; do
        command -v "$tool" >/dev/null 2>&1 || continue
        for cadena in ALFA_ISO_OUT ALFA_ISO_IN; do
            "$tool" -N "$cadena" 2>/dev/null
            "$tool" -F "$cadena"
        done
        "$tool" -A ALFA_ISO_OUT -o lo -j ACCEPT
        "$tool" -A ALFA_ISO_IN -i lo -j ACCEPT
        if [[ "$tool" == "iptables" ]]; then
            for ip in $IPS; do
                "$tool" -A ALFA_ISO_OUT -d "$ip" -p tcp --dport "$PUERTO" -j ACCEPT
                "$tool" -A ALFA_ISO_IN -s "$ip" -p tcp --sport "$PUERTO" -m conntrack --ctstate ESTABLISHED -j ACCEPT
            done
        fi
        "$tool" -A ALFA_ISO_OUT -j DROP
        "$tool" -A ALFA_ISO_IN -j DROP
        for par in "ALFA_ISO_OUT OUTPUT" "ALFA_ISO_IN INPUT"; do
            cadena="${par% *}"; padre="${par#* }"
            "$tool" -C "$padre" -j "$cadena" 2>/dev/null || "$tool" -I "$padre" 1 -j "$cadena"
        done
    done
    if iptables -S OUTPUT 2>/dev/null | grep -m1 '^-A ' | grep -q -- "-j ALFA_ISO_OUT"; then
        echo "aplicado por el guardián: solo se permite ${IPS% }:$PUERTO/tcp."
    else
        echo "FALLÓ: la cadena ALFA_ISO_OUT no quedó primera en OUTPUT"
    fi
}

DETALLE="$(aislar 2>&1 | tail -n 1)"
log "Aislamiento: $DETALLE"

# --- 4. Marca y aviso al servidor ----------------------------------------
AHORA="$(date '+%Y-%m-%d %H:%M:%S')"
marca() {
    mkdir -p "$ESTADO"
    printf '{"detected_at": "%s", "isolation": "%s", "reported": %s}\n' "$AHORA" "${DETALLE//\"/\'}" "$1" > "$ESTADO/agente_terminado.json"
}
marca false

if [[ $SIMULAR -eq 1 ]]; then
    log "SIMULADO: no se envió la alerta al servidor."
    exit 0
fi
if ! command -v curl >/dev/null 2>&1; then
    log "curl no está instalado: el agente enviará la alerta al volver a iniciarse."
    exit 0
fi

CUERPO="$(printf '{"title": "Agente detenido de forma inesperada", "description": "El guardián del equipo detectó que el agente fue terminado sin un cierre normal a las %s (no fue un apagado, una actualización ni una desinstalación). Aislamiento local: %s", "matched_rules": ["%s"]}' \
    "${AHORA#* }" "${DETALLE//\"/\'}" "$REGLA")"
# --cacert: solo se confía en la CA propia de ALFA-Sentinel (como el agente).
CODIGO="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 --cacert "$DIR/certs/ca.crt" \
    -X POST "$URL/agent/alerts" -H "X-Agent-Credential: $CRED" -H "Content-Type: application/json" \
    --data "$CUERPO" 2>>"$LOG")"
if [[ "$CODIGO" =~ ^2 ]]; then
    marca true
    log "Alerta CRÍTICA enviada al servidor."
else
    log "El servidor no aceptó la alerta (HTTP ${CODIGO:-sin respuesta}); el agente la enviará al volver a iniciarse."
fi
exit 0
