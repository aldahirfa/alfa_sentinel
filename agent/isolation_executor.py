"""Ejecución real de aislamiento de red (secciones 26-30 de la
especificación de corrección definitiva, 2026-08-17, ver
PENDIENTES.md: "El sistema debe EJECUTAR el aislamiento automáticamente...
no solamente recomendar").

Extendido 2026-08-17 (ver PENDIENTES.md, "Aislamiento de host -- modo
development, laboratorio y producción") con TRES modos de ejecución
explícitos, en vez del interruptor binario anterior:

- DEVELOPMENT (ALFA_SENTINEL_ENV sin definir, o cualquier valor que no
  sea uno de los dos de abajo): el flujo completo se ejerce (servidor
  ordena, agente "ejecuta", confirma, la consola muestra el resultado)
  pero la acción de red queda SIMULADA -- nunca se toca el firewall
  real de la máquina de desarrollo. Decisión consultada con el usuario
  antes de la primera implementación de esto (ver commit anterior):
  ejecutar un comando real de firewall sobre la máquina donde corre el
  agente es una acción de alto impacto -- si algo sale mal en
  desarrollo, podría cortarle el acceso de red real a quien está
  probando el sistema.
- CONTROLLED_TEST (alias aceptado: LABORATORY) -- ALFA_SENTINEL_ENV=
  controlled_test: aislamiento REAL, pensado para una VM o endpoint de
  laboratorio preparado específicamente para probar ALFA_SENTINEL antes
  de un despliegue real.
- PRODUCTION -- ALFA_SENTINEL_ENV=production: aislamiento REAL.

El modo se lee EXCLUSIVAMENTE de la variable de entorno explícita
ALFA_SENTINEL_ENV (agent/paths.py::get_env_mode()) -- nunca se infiere
"soy localhost" ni se detecta automáticamente si es una VM (pedido
explícito, sección 29: "No determinarlo simplemente por 'si soy
localhost'... No depender de detectar manualmente si estoy en una
VM"). CONTROLLED_TEST y PRODUCTION comparten exactamente la misma
lógica de ejecución real -- la única diferencia entre ambos es
operativa (qué máquina es), no de código.

Objetivo del aislamiento (sección 29 de la especificación original,
reafirmado en la de host, sección 9): impedir movimiento lateral
bloqueando comunicación general de red y acceso a recursos
compartidos, dejando pasar únicamente el canal hacia ALFA_SENTINEL
(heartbeat, confirmar aislamiento, recibir liberación, actualizar
política). NUNCA mata procesos, apaga el equipo, recupera archivos,
borra malware, ni modifica el kernel/instala drivers -- eso está fuera
de alcance a propósito, en todo el proyecto, no solo acá (secciones 11
y 12 de la especificación de host)."""

import ipaddress
import json
import os
import platform
import socket
import subprocess
from urllib.parse import urlparse

import config


# Tiempo máximo que se le da a cada comando de sistema antes de darlo
# por fallido -- un netsh/iptables colgado no debe dejar al agente
# esperando indefinidamente.
COMMAND_TIMEOUT_SECONDS = 15

# Modos que ejecutan de verdad -- CONTROLLED_TEST (alias LABORATORY) y
# PRODUCTION. Cualquier otro valor (incluido "development", el
# default) queda simulado. Ver agent/paths.py::get_env_mode() -- sigue
# siendo la única fuente del modo, esto solo interpreta su valor con 3
# resultados posibles en vez de 2.
REAL_EXECUTION_ENV_MODES = {"controlled_test", "laboratory", "production"}


def _has_elevated_privileges():
    """Nunca asumir privilegios -- se consulta el SO real, mismo
    criterio que agent/adapters/linux_fanotify.py (fanotify_init()
    devuelve EPERM en vez de simular que funciona). Devuelve
    (tiene_privilegios: bool, detalle: str)."""

    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            return is_admin, ("Proceso con privilegios de Administrador." if is_admin
                               else "El agente no corre como Administrador.")
        except Exception as error:
            return False, f"No se pudo determinar el nivel de privilegio: {error}"

    if system == "Linux":
        try:
            is_root = os.geteuid() == 0
            return is_root, ("Proceso corriendo como root." if is_root
                              else "El agente no corre como root (falta CAP_NET_ADMIN real).")
        except AttributeError:
            return False, "No se pudo determinar el UID efectivo en este sistema."

    return False, f"Aislamiento de red no implementado para este SO: {system}"


def _run(command):
    """Corre un comando real del SO, sin usar shell=True (los
    argumentos van armados a mano, nunca interpolando texto externo).
    Devuelve (ok: bool, detalle: str) -- nunca lanza, para que el
    llamador pueda seguir con el resto de las reglas incluso si una
    falla a mitad de camino."""

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=True,
        )
        return True, (result.stdout or "").strip()
    except FileNotFoundError:
        return False, f"Comando no disponible en este sistema: {command[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Comando agotó el tiempo límite ({COMMAND_TIMEOUT_SECONDS}s): {' '.join(command)}"
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        return False, f"Comando falló ({' '.join(command)}): {detail}"


def _run_allow_failure(command):
    """Igual que _run pero para pasos "mejor esfuerzo" -- delete-then-
    add (Windows) y delete al liberar: no importa si el comando falla
    porque la regla no existía todavía, eso es justo lo esperado la
    primera vez. Nunca se usa para el paso que de verdad aísla/libera,
    solo para limpiar antes de ese paso."""

    try:
        subprocess.run(command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS)
    except Exception:
        pass


def _iptables_rule_exists(rule_args, tool="iptables"):
    """iptables -C (--check) -- resultado de existencia confiable y no
    dependiente del idioma del sistema (exit 0 = la regla existe tal
    cual). Sirve para la idempotencia y para verificar después de
    aplicar (sección 14 de la especificación de host)."""

    try:
        result = subprocess.run(
            [tool, "-C"] + rule_args,
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return result.returncode == 0
    except Exception:
        return False


# --- Qué tráfico se permite durante el aislamiento (2026-09-24) -------
#
# Antes se permitía TODO el tráfico con la IP del servidor, en cualquier
# puerto: un equipo aislado e infectado podía seguir llegando al servidor
# por SMB, RDP, SSH o PostgreSQL. Además solo se cambiaba la política por
# defecto del firewall, que no pisa las reglas "permitir" que ya
# existían (Compartir archivos en Windows, una regla de ufw para SSH en
# Linux), y al liberar se dejaba "permitir todo".
#
# Ahora, durante el aislamiento, lo ÚNICO permitido es la conexión TCP
# que abre el agente hacia el puerto de ALFA_SENTINEL (HTTPS). Nadie
# puede abrir una conexión hacia el equipo, ni siquiera el servidor (el
# agente siempre inicia la comunicación). Al liberar, el firewall vuelve
# al estado que tenía antes de aislar.

def _server_endpoint():
    """(host, puerto) de ALFA_SENTINEL según config.SERVER_URL."""

    parsed = urlparse(config.SERVER_URL)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port


def _resolve_server_ips(host):
    """IPs del servidor. Se resuelven ANTES de bloquear: durante el
    aislamiento el DNS queda cortado, por eso conviene que SERVER_URL
    use directamente la IP del servidor."""

    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


# --- Linux: iptables / ip6tables ---------------------------------------
#
# Cadenas propias insertadas en la PRIMERA posición de OUTPUT e INPUT y
# terminadas en DROP: como se evalúan antes que cualquier otra regla,
# ninguna regla previa ("permitir SSH" de ufw, etc.) llega a aplicarse.
# Las políticas por defecto no se tocan, así que al quitar las cadenas el
# firewall queda exactamente como estaba.

LINUX_CHAIN_OUT = "ALFA_ISO_OUT"
LINUX_CHAIN_IN = "ALFA_ISO_IN"
LINUX_CHAINS = ((LINUX_CHAIN_OUT, "OUTPUT"), (LINUX_CHAIN_IN, "INPUT"))


def _linux_chain_rules(server_ips, port):
    """Reglas de cada cadena, por herramienta (IPv4 / IPv6)."""

    rules = {}
    for tool, version in (("iptables", 4), ("ip6tables", 6)):
        ips = [ip for ip in server_ips if ipaddress.ip_address(ip).version == version]
        out_rules = [["-o", "lo", "-j", "ACCEPT"]]
        in_rules = [["-i", "lo", "-j", "ACCEPT"]]
        for ip in ips:
            out_rules.append(["-d", ip, "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"])
            # Solo respuestas a conexiones que abrió el agente.
            in_rules.append(["-s", ip, "-p", "tcp", "--sport", str(port),
                             "-m", "conntrack", "--ctstate", "ESTABLISHED", "-j", "ACCEPT"])
        out_rules.append(["-j", "DROP"])
        in_rules.append(["-j", "DROP"])
        rules[tool] = {LINUX_CHAIN_OUT: out_rules, LINUX_CHAIN_IN: in_rules}
    return rules


def _linux_apply(tool, chain_rules):
    """Arma cada cadena completa y RECIÉN DESPUÉS la engancha primera
    (orden defensivo: el permiso hacia el servidor ya está antes de que
    la cadena empiece a filtrar). Idempotente: vaciar y volver a llenar
    la cadena siempre deja el mismo contenido, y el enganche se agrega
    solo si no estaba."""

    for chain, parent in LINUX_CHAINS:
        _run_allow_failure([tool, "-N", chain])  # falla si ya existe: es lo esperado
        ok, detail = _run([tool, "-F", chain])
        if not ok:
            return False, detail
        for rule in chain_rules[chain]:
            ok, detail = _run([tool, "-A", chain] + rule)
            if not ok:
                return False, detail
        if not _iptables_rule_exists([parent, "-j", chain], tool):
            ok, detail = _run([tool, "-I", parent, "1", "-j", chain])
            if not ok:
                return False, detail
    return True, ""


def _linux_verify(tool):
    """Verificación real: el enganche es la PRIMERA regla de OUTPUT e
    INPUT y cada cadena termina en DROP."""

    for chain, parent in LINUX_CHAINS:
        ok, listing = _run([tool, "-S", parent])
        first_rule = next((line.strip() for line in listing.splitlines() if line.startswith("-A ")), "")
        if not ok or first_rule != f"-A {parent} -j {chain}":
            return False, f"{tool}: '{chain}' no quedó primera en {parent} ({first_rule or 'sin reglas'})."
        ok, listing = _run([tool, "-S", chain])
        rules = [line.strip() for line in listing.splitlines() if line.startswith("-A ")]
        if not ok or not rules or rules[-1] != f"-A {chain} -j DROP":
            return False, f"{tool}: la cadena '{chain}' no termina en DROP."
    return True, ""


def _linux_remove(tool):
    """Desengancha y borra las cadenas (mejor esfuerzo: si no estaban,
    ya es el estado final deseado)."""

    for chain, parent in LINUX_CHAINS:
        for _ in range(10):  # por si quedó enganchada más de una vez
            if not _iptables_rule_exists([parent, "-j", chain], tool):
                break
            _run_allow_failure([tool, "-D", parent, "-j", chain])
        _run_allow_failure([tool, "-F", chain])
        _run_allow_failure([tool, "-X", chain])


def _linux_legacy_rules(server_host):
    """Reglas de la versión anterior del aislamiento (permitían todo
    con el servidor y cambiaban la política a DROP)."""

    return [
        ["OUTPUT", "-d", server_host, "-j", "ACCEPT"],
        ["INPUT", "-s", server_host, "-j", "ACCEPT"],
        ["OUTPUT", "-o", "lo", "-j", "ACCEPT"],
        ["INPUT", "-i", "lo", "-j", "ACCEPT"],
    ]


def _isolate_linux(server_ips, port):
    rules = _linux_chain_rules(server_ips, port)

    ok, detail = _linux_apply("iptables", rules["iptables"])
    if ok:
        ok, detail = _linux_verify("iptables")
    if not ok:
        return False, detail

    # IPv6 también sirve para moverse dentro de la red local. Si el
    # equipo no tiene ip6tables (IPv6 deshabilitado), se informa sin
    # deshacer el aislamiento IPv4, que ya está aplicado y verificado.
    ok6, detail6 = _linux_apply("ip6tables", rules["ip6tables"])
    if ok6:
        ok6, detail6 = _linux_verify("ip6tables")
    ipv6_note = "IPv6 bloqueado" if ok6 else f"IPv6 NO aislado ({detail6})"

    allowed = ", ".join(f"{ip}:{port}/tcp" for ip in server_ips)
    return True, (
        f"iptables: solo se permite la conexión saliente del agente a {allowed}; "
        f"toda conexión entrante y el resto del tráfico se descartan ({ipv6_note}). Verificado tras aplicar."
    )


def _release_linux(server_host):
    for tool in ("iptables", "ip6tables"):
        _linux_remove(tool)

    # Aislamiento hecho por la versión anterior: sus reglas y su
    # política DROP también hay que revertirlas, o el equipo quedaría
    # sin red al liberar.
    legacy_found = False
    if server_host:
        for rule in _linux_legacy_rules(server_host):
            if _iptables_rule_exists(rule):
                legacy_found = True
                _run_allow_failure(["iptables", "-D"] + rule)
    if legacy_found:
        for chain in ("OUTPUT", "INPUT"):
            ok, detail = _run(["iptables", "-P", chain, "ACCEPT"])
            if not ok:
                return False, detail

    for chain, parent in LINUX_CHAINS:
        if _iptables_rule_exists([parent, "-j", chain]):
            return False, f"La cadena '{chain}' sigue enganchada en {parent} después de liberar."

    legacy_note = " También se revirtió un aislamiento de la versión anterior." if legacy_found else ""
    return True, f"iptables: cadenas de aislamiento retiradas; el firewall volvió a su configuración previa.{legacy_note} Verificado tras aplicar."


# --- Windows: Windows Defender Firewall --------------------------------
#
# En Windows una regla de BLOQUEO le gana a cualquier regla "permitir"
# (por ejemplo "Compartir archivos e impresoras"), así que el
# aislamiento se arma con bloqueos explícitos. El firewall es con
# estado: bloquear toda conexión ENTRANTE no afecta a las respuestas del
# servidor a las conexiones que abre el agente.

WIN_RULE_BLOCK_IN = "ALFA_SENTINEL_BLOCK_IN"
WIN_RULE_BLOCK_OUT_OTHERS = "ALFA_SENTINEL_BLOCK_OUT_OTROS"
WIN_RULE_BLOCK_OUT_SERVER_TCP = "ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_TCP"
WIN_RULE_BLOCK_OUT_SERVER_UDP = "ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_UDP"
WIN_RULE_ALLOW_OUT = "ALFA_SENTINEL_ALLOW_OUT"
WIN_RULES = (
    WIN_RULE_BLOCK_IN, WIN_RULE_BLOCK_OUT_OTHERS, WIN_RULE_BLOCK_OUT_SERVER_TCP,
    WIN_RULE_BLOCK_OUT_SERVER_UDP, WIN_RULE_ALLOW_OUT,
)
# Regla de la versión anterior (permitía todo lo entrante desde el servidor).
WIN_LEGACY_RULE_ALLOW_IN = "ALFA_SENTINEL_ALLOW_IN"

# Estado del firewall antes de aislar, para restaurarlo al liberar.
ISOLATION_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isolation_state.json")
WIN_PROFILES = ("Domain", "Private", "Public")
_WIN_ENABLED_VALUES = {"True", "False", "NotConfigured"}
_WIN_ACTION_VALUES = {"Allow", "Block", "NotConfigured"}
# Valor normal de Windows, si no hay estado guardado.
WIN_DEFAULT_PROFILE = {"Enabled": "True", "In": "Block", "Out": "Allow"}


def _powershell(script):
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])


def _win_read_profiles():
    """Estado actual de cada perfil del firewall. Se lee con PowerShell
    (valores en inglés siempre, sin importar el idioma de Windows)."""

    ok, output = _powershell(
        "Get-NetFirewallProfile | ForEach-Object { [pscustomobject]@{ "
        "Name = \"$($_.Name)\"; Enabled = \"$($_.Enabled)\"; "
        "In = \"$($_.DefaultInboundAction)\"; Out = \"$($_.DefaultOutboundAction)\" } } "
        "| ConvertTo-Json -Compress"
    )
    if not ok:
        return None
    try:
        data = json.loads(output)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = [data]
    profiles = {}
    for item in data:
        name = item.get("Name")
        if (name in WIN_PROFILES and item.get("Enabled") in _WIN_ENABLED_VALUES
                and item.get("In") in _WIN_ACTION_VALUES and item.get("Out") in _WIN_ACTION_VALUES):
            profiles[name] = {"Enabled": item["Enabled"], "In": item["In"], "Out": item["Out"]}
    return profiles if len(profiles) == len(WIN_PROFILES) else None


def _win_save_state():
    """Guarda cómo estaba el firewall. Si ya hay un estado guardado (un
    segundo aislamiento sin liberar el primero) NO se pisa: el que vale
    es el de antes del PRIMER aislamiento."""

    if os.path.exists(ISOLATION_STATE_FILE):
        return True, ""
    profiles = _win_read_profiles()
    if profiles is None:
        return False, "No se pudo leer la configuración actual del firewall (Get-NetFirewallProfile) para poder restaurarla después."
    with open(ISOLATION_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"windows_profiles": profiles}, f)
    return True, ""


def _win_load_state():
    try:
        with open(ISOLATION_STATE_FILE, encoding="utf-8") as f:
            profiles = json.load(f).get("windows_profiles") or {}
    except (OSError, ValueError):
        return None
    # El archivo se valida antes de usarlo: sus valores terminan en un
    # comando de PowerShell.
    valid = all(
        name in profiles
        and profiles[name].get("Enabled") in _WIN_ENABLED_VALUES
        and profiles[name].get("In") in _WIN_ACTION_VALUES
        and profiles[name].get("Out") in _WIN_ACTION_VALUES
        for name in WIN_PROFILES
    )
    return profiles if valid else None


def _win_port_ranges_except(port):
    ranges = []
    if port > 1:
        ranges.append(f"1-{port - 1}" if port > 2 else "1")
    if port < 65535:
        ranges.append(f"{port + 1}-65535" if port < 65534 else "65535")
    return ",".join(ranges)


def _win_other_addresses(server_ips):
    """Todas las direcciones IPv4 e IPv6 salvo las del servidor, en
    notación CIDR (netsh no tiene "todas menos X")."""

    networks = []
    for full in (ipaddress.ip_network("0.0.0.0/0"), ipaddress.ip_network("::/0")):
        parts = [full]
        for ip in server_ips:
            server_net = ipaddress.ip_network(ip)
            if server_net.version != full.version:
                continue
            parts = [piece for part in parts
                     for piece in (part.address_exclude(server_net) if server_net.subnet_of(part) else [part])]
        networks.extend(parts)
    return ",".join(str(net) for net in networks)


def _win_rule_exists(name):
    ok, detail = _run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"])
    return ok and name in detail


def _win_delete_rules(names):
    for name in names:
        _run_allow_failure(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"])


def _isolate_windows(server_ips, port):
    ok, detail = _win_save_state()
    if not ok:
        return False, detail

    servers = ",".join(server_ips)
    add = ["netsh", "advfirewall", "firewall", "add", "rule"]
    # Primero la excepción hacia ALFA_SENTINEL, después los bloqueos y
    # recién al final la política (orden defensivo, como antes).
    steps = [
        add + [f"name={WIN_RULE_ALLOW_OUT}", "dir=out", "action=allow",
               "protocol=TCP", f"remoteip={servers}", f"remoteport={port}"],
        add + [f"name={WIN_RULE_BLOCK_IN}", "dir=in", "action=block", "remoteip=any"],
        add + [f"name={WIN_RULE_BLOCK_OUT_OTHERS}", "dir=out", "action=block",
               f"remoteip={_win_other_addresses(server_ips)}"],
        add + [f"name={WIN_RULE_BLOCK_OUT_SERVER_UDP}", "dir=out", "action=block",
               "protocol=UDP", f"remoteip={servers}"],
        # Si el firewall estaba apagado, ninguna regla tendría efecto.
        ["netsh", "advfirewall", "set", "allprofiles", "state", "on"],
        ["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,blockoutbound"],
    ]
    other_ports = _win_port_ranges_except(port)
    if other_ports:
        steps.insert(3, add + [f"name={WIN_RULE_BLOCK_OUT_SERVER_TCP}", "dir=out", "action=block",
                               "protocol=TCP", f"remoteip={servers}", f"remoteport={other_ports}"])

    # Idempotencia: se borran antes las reglas con estos nombres (netsh no
    # tiene un chequeo de existencia que no dependa del idioma).
    _win_delete_rules(WIN_RULES + (WIN_LEGACY_RULE_ALLOW_IN,))
    for step in steps:
        ok, detail = _run(step)
        if not ok:
            return False, detail

    # Verificación real (sección 14).
    expected = [r for r in WIN_RULES if other_ports or r != WIN_RULE_BLOCK_OUT_SERVER_TCP]
    missing = [name for name in expected if not _win_rule_exists(name)]
    if missing:
        return False, f"Los comandos terminaron sin error pero no se pudieron confirmar las reglas: {', '.join(missing)}."
    profiles = _win_read_profiles()
    if profiles is None or any(p["Enabled"] != "True" or p["In"] != "Block" or p["Out"] != "Block" for p in profiles.values()):
        return False, f"Los comandos terminaron sin error pero el estado de los perfiles no se pudo confirmar: {profiles}"

    allowed = ", ".join(f"{ip}:{port}/tcp" for ip in server_ips)
    return True, (
        f"Windows Firewall: solo se permite la conexión saliente del agente a {allowed}; "
        "se bloquea toda conexión entrante y el resto del tráfico, por encima de las reglas previas. Verificado tras aplicar."
    )


def _release_windows():
    _win_delete_rules(WIN_RULES + (WIN_LEGACY_RULE_ALLOW_IN,))

    saved = _win_load_state()
    target = saved or {name: dict(WIN_DEFAULT_PROFILE) for name in WIN_PROFILES}
    script = "; ".join(
        f"Set-NetFirewallProfile -Name {name} -Enabled {p['Enabled']} "
        f"-DefaultInboundAction {p['In']} -DefaultOutboundAction {p['Out']}"
        for name, p in target.items()
    )
    ok, detail = _powershell(script)
    if not ok:
        return False, detail

    leftover = [name for name in WIN_RULES if _win_rule_exists(name)]
    if leftover:
        return False, f"Siguen existiendo reglas de aislamiento después de liberar: {', '.join(leftover)}."
    if _win_read_profiles() != target:
        return False, "La configuración del firewall se restauró sin error pero no se pudo confirmar después."

    try:
        os.remove(ISOLATION_STATE_FILE)
    except OSError:
        pass

    origin = ("la configuración que tenía antes de aislar" if saved
              else "la configuración normal de Windows (bloquear entrantes, permitir salientes)")
    return True, f"Windows Firewall: reglas de aislamiento retiradas y restaurada {origin}. Verificado tras aplicar."


def _resolve_env_mode():
    """Interpreta agent/paths.py::get_env_mode() (el único origen del
    modo, siempre explícito vía ALFA_SENTINEL_ENV -- sección 29 de la
    especificación de host) con 3 resultados posibles en vez de 2:
    devuelve el modo crudo en minúsculas y si corresponde ejecutar de
    verdad."""

    import paths as agent_paths

    mode = agent_paths.get_env_mode()
    return mode, mode in REAL_EXECUTION_ENV_MODES


def _mode_label(mode):
    return {
        "production": "PRODUCTION",
        "controlled_test": "CONTROLLED_TEST",
        "laboratory": "CONTROLLED_TEST (alias 'laboratory')",
    }.get(mode, "DEVELOPMENT")


def execute_isolation(isolation_type):
    """Punto de entrada único para AISLAR, llamado por
    agent/isolation_sync.py. Devuelve (success: bool, result_message:
    str) -- el mensaje se manda tal cual al servidor (POST
    /agent/isolation-status/report, campo 'result') para que quede
    registrado qué pasó de verdad, tanto si funcionó como si no.

    El mensaje SIEMPRE deja explícito el modo de ejecución (sección 7
    de la especificación de host: "debe quedar registrado que la
    ejecución fue simulada... execution_mode/simulation trazable") --
    no se agregó una columna nueva a host_isolations para esto (el
    campo 'result' ya es de texto libre y ya se usaba exactamente así
    desde la implementación anterior; agregar una columna hubiera
    exigido una migración manual sobre la base real ya en uso, fuera de
    lo que pide esta tarea)."""

    if isolation_type != "NETWORK":
        return False, f"Tipo de aislamiento no soportado por este agente: {isolation_type}"

    server_host, server_port = _server_endpoint()
    if not server_host:
        return False, "No se pudo determinar el host de ALFA_SENTINEL (config.SERVER_URL inválida) -- se aborta para no bloquear ese canal también."

    mode, is_real = _resolve_env_mode()

    if not is_real:
        return True, (
            f"[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO: no se ejecutó ningún comando de red real. "
            f"En CONTROLLED_TEST/PRODUCTION, este endpoint bloquearía todo el tráfico salvo la conexión del agente a {server_host}:{server_port}/tcp."
        )

    has_privileges, privilege_detail = _has_elevated_privileges()
    if not has_privileges:
        return False, f"[execution_mode={_mode_label(mode)}] Privilegios insuficientes para aislar la red de verdad: {privilege_detail}"

    try:
        server_ips = _resolve_server_ips(server_host)
    except OSError as error:
        return False, f"[execution_mode={_mode_label(mode)}] No se pudo resolver la IP de ALFA_SENTINEL ({server_host}): {error} -- se aborta para no cortar ese canal."
    if not server_ips:
        return False, f"[execution_mode={_mode_label(mode)}] {server_host} no resolvió a ninguna IP -- se aborta para no cortar ese canal."

    system = platform.system()
    if system == "Windows":
        ok, detail = _isolate_windows(server_ips, server_port)
    elif system == "Linux":
        ok, detail = _isolate_linux(server_ips, server_port)
    else:
        return False, f"[execution_mode={_mode_label(mode)}] Aislamiento de red no implementado para este SO: {system}"

    return ok, f"[execution_mode={_mode_label(mode)}, simulation=FALSE] {detail}"


def execute_release(isolation_type):
    """Punto de entrada único para LIBERAR un aislamiento ya aplicado
    (sección 18 de la especificación de host: "UNISOLATE"). Misma
    forma que execute_isolation() -- (success: bool, result_message:
    str). En DEVELOPMENT queda simulado por el mismo motivo que aislar;
    en CONTROLLED_TEST/PRODUCTION remueve de verdad las reglas
    aplicadas y restaura la política por defecto. No toca archivos, no
    recupera nada -- solo estado de red (pedido explícito)."""

    if isolation_type != "NETWORK":
        return False, f"Tipo de aislamiento no soportado por este agente: {isolation_type}"

    server_host, _server_port = _server_endpoint()
    mode, is_real = _resolve_env_mode()

    if not is_real:
        return True, "[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO: no se ejecutó ningún comando de red real -- no había ningún aislamiento real que revertir."

    has_privileges, privilege_detail = _has_elevated_privileges()
    if not has_privileges:
        return False, f"[execution_mode={_mode_label(mode)}] Privilegios insuficientes para liberar la red de verdad: {privilege_detail}"

    system = platform.system()
    if system == "Windows":
        ok, detail = _release_windows()
    elif system == "Linux":
        ok, detail = _release_linux(server_host or "")
    else:
        return False, f"[execution_mode={_mode_label(mode)}] Liberación de red no implementada para este SO: {system}"

    return ok, f"[execution_mode={_mode_label(mode)}, simulation=FALSE] {detail}"
