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

import os
import platform
import subprocess
from urllib.parse import urlparse

import config


# Tiempo máximo que se le da a cada comando de sistema antes de darlo
# por fallido -- un netsh/iptables colgado no debe dejar al agente
# esperando indefinidamente.
COMMAND_TIMEOUT_SECONDS = 15

# Nombres de las reglas de Windows Firewall -- fijos y reconocibles,
# así delete-then-add (idempotencia, ver _isolate_windows) y la
# verificación posterior (sección 14) siempre apuntan a las mismas
# reglas, sin importar cuántas veces se haya ejecutado antes.
WIN_RULE_ALLOW_OUT = "ALFA_SENTINEL_ALLOW_OUT"
WIN_RULE_ALLOW_IN = "ALFA_SENTINEL_ALLOW_IN"

# Modos que ejecutan de verdad -- CONTROLLED_TEST (alias LABORATORY) y
# PRODUCTION. Cualquier otro valor (incluido "development", el
# default) queda simulado. Ver agent/paths.py::get_env_mode() -- sigue
# siendo la única fuente del modo, esto solo interpreta su valor con 3
# resultados posibles en vez de 2.
REAL_EXECUTION_ENV_MODES = {"controlled_test", "laboratory", "production"}


def _server_host():
    """El host (sin puerto ni esquema) de ALFA_SENTINEL -- el único
    destino que debe seguir permitido durante el aislamiento (sección
    9 de la especificación de host: "mantener, cuando corresponda, la
    comunicación mínima necesaria con ALFA_SENTINEL SERVER"). Se lee
    de config.SERVER_URL en vez de hardcodear una IP -- ya viene
    resuelto igual que el resto de las URLs del agente (incluye el
    override de --server, ver agent/main.py::apply_cli_overrides)."""

    return urlparse(config.SERVER_URL).hostname


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


def _iptables_rule_exists(rule_args):
    """iptables -C (--check) -- a diferencia de netsh, tiene un
    resultado de existencia confiable y no dependiente del idioma del
    sistema (exit 0 = la regla existe tal cual, cualquier otro código =
    no existe). Se reutiliza para dos cosas (sección 17 y sección 14 de
    la especificación de host): decidir si hace falta insertar (
    idempotencia) y, después de insertar, confirmar que de verdad quedó
    (verificación real, no asumida solo porque el comando no lanzó
    error)."""

    try:
        result = subprocess.run(
            ["iptables", "-C"] + rule_args,
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return result.returncode == 0
    except Exception:
        return False


def _isolate_windows(server_host):
    """netsh advfirewall -- primero la excepción hacia ALFA_SENTINEL y
    loopback, RECIÉN DESPUÉS la política por defecto de bloqueo. El
    orden importa: si se bloqueara primero, una sesión de
    administración remota sobre la misma máquina podría cortarse a sí
    misma antes de que la excepción llegue a aplicarse (sección 10 de
    la especificación de host: "orden defensivo").

    Idempotencia (sección 17/27): antes de agregar cada regla nombrada,
    se borra cualquier regla previa con ese mismo nombre (best-effort,
    no falla si no existía) -- así, sin importar cuántas veces se
    ejecute esto, queda EXACTAMENTE una regla de cada una, nunca
    acumulando duplicados. netsh no ofrece un chequeo de existencia
    confiable independiente del idioma del sistema (el texto de "no se
    encontraron reglas" cambia según el idioma de Windows) -- borrar
    primero es la forma robusta de lograr el mismo resultado."""

    _run_allow_failure(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={WIN_RULE_ALLOW_OUT}"])
    _run_allow_failure(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={WIN_RULE_ALLOW_IN}"])

    steps = [
        ["netsh", "advfirewall", "firewall", "add", "rule",
         f"name={WIN_RULE_ALLOW_OUT}", "dir=out", "action=allow",
         f"remoteip={server_host}"],
        ["netsh", "advfirewall", "firewall", "add", "rule",
         f"name={WIN_RULE_ALLOW_IN}", "dir=in", "action=allow",
         f"remoteip={server_host}"],
        ["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy",
         "blockinbound,blockoutbound"],
    ]

    for step in steps:
        ok, detail = _run(step)
        if not ok:
            return False, detail

    # Verificación real (sección 14: "no devolver EXECUTED simplemente
    # porque el comando terminó sin excepción" -- comprobar que las
    # reglas esperadas de verdad existen).
    ok_out, out_detail = _run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={WIN_RULE_ALLOW_OUT}"])
    ok_in, in_detail = _run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={WIN_RULE_ALLOW_IN}"])
    ok_policy, policy_detail = _run(["netsh", "advfirewall", "show", "currentprofile"])

    if not (ok_out and WIN_RULE_ALLOW_OUT in out_detail):
        return False, f"Los comandos terminaron sin error pero la regla '{WIN_RULE_ALLOW_OUT}' no se pudo confirmar después: {out_detail}"
    if not (ok_in and WIN_RULE_ALLOW_IN in in_detail):
        return False, f"Los comandos terminaron sin error pero la regla '{WIN_RULE_ALLOW_IN}' no se pudo confirmar después: {in_detail}"
    if not (ok_policy and "block" in policy_detail.lower()):
        return False, f"Los comandos terminaron sin error pero la política de bloqueo no se pudo confirmar después: {policy_detail}"

    return True, f"Windows Firewall: tráfico bloqueado salvo hacia {server_host} (reglas {WIN_RULE_ALLOW_OUT}/{WIN_RULE_ALLOW_IN}), verificado tras aplicar."


def _release_windows():
    """Inverso de _isolate_windows -- borra las reglas de excepción y
    devuelve la política por defecto a permitir todo (sección 18 de la
    especificación de host: "restaurar el estado de red", nada de
    archivos). Best-effort en cada paso -- si alguna regla ya no
    estaba, no es un fallo, es justo el estado final deseado."""

    _run_allow_failure(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={WIN_RULE_ALLOW_OUT}"])
    _run_allow_failure(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={WIN_RULE_ALLOW_IN}"])

    ok, detail = _run(["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "allowinbound,allowoutbound"])
    if not ok:
        return False, detail

    ok_policy, policy_detail = _run(["netsh", "advfirewall", "show", "currentprofile"])
    if not (ok_policy and "allow" in policy_detail.lower()):
        return False, f"La política se restableció sin error pero no se pudo confirmar después: {policy_detail}"

    return True, "Windows Firewall: reglas de aislamiento retiradas, política por defecto restaurada (permitir), verificado tras aplicar."


def _isolate_linux(server_host):
    """iptables -- mismo orden defensivo que Windows: primero ACCEPT
    para el servidor real y loopback, recién después la política DROP
    por defecto. Idempotente vía -C (sección 17/27): cada regla se
    inserta solo si _iptables_rule_exists() confirma que todavía no
    está, así ejecutar esto dos veces nunca deja reglas duplicadas."""

    rules = [
        ["OUTPUT", "-d", server_host, "-j", "ACCEPT"],
        ["INPUT", "-s", server_host, "-j", "ACCEPT"],
        ["OUTPUT", "-o", "lo", "-j", "ACCEPT"],
        ["INPUT", "-i", "lo", "-j", "ACCEPT"],
    ]

    for chain, *match in rules:
        rule_args = [chain] + match
        if _iptables_rule_exists(rule_args):
            continue
        ok, detail = _run(["iptables", "-I", chain, "1"] + match)
        if not ok:
            return False, detail

    ok_out, detail_out = _run(["iptables", "-P", "OUTPUT", "DROP"])
    if not ok_out:
        return False, detail_out
    ok_in, detail_in = _run(["iptables", "-P", "INPUT", "DROP"])
    if not ok_in:
        return False, detail_in

    # Verificación real (sección 14): re-chequear con -C que las
    # reglas de excepción de verdad están, y que la política por
    # defecto quedó en DROP.
    for chain, *match in rules:
        if not _iptables_rule_exists([chain] + match):
            return False, f"Los comandos terminaron sin error pero la regla '{' '.join([chain] + match)}' no se pudo confirmar después."

    ok_s_out, policy_out = _run(["iptables", "-S", "OUTPUT"])
    ok_s_in, policy_in = _run(["iptables", "-S", "INPUT"])
    if not (ok_s_out and "-P OUTPUT DROP" in policy_out):
        return False, f"Los comandos terminaron sin error pero la política OUTPUT DROP no se pudo confirmar después: {policy_out}"
    if not (ok_s_in and "-P INPUT DROP" in policy_in):
        return False, f"Los comandos terminaron sin error pero la política INPUT DROP no se pudo confirmar después: {policy_in}"

    return True, f"iptables: tráfico bloqueado salvo hacia {server_host} y loopback (políticas OUTPUT/INPUT DROP), verificado tras aplicar."


def _release_linux(server_host):
    """Inverso de _isolate_linux -- borra (best-effort, -D tolera que
    la regla ya no exista) las reglas de excepción y devuelve las
    políticas por defecto a ACCEPT."""

    rules = [
        ["OUTPUT", "-d", server_host, "-j", "ACCEPT"],
        ["INPUT", "-s", server_host, "-j", "ACCEPT"],
        ["OUTPUT", "-o", "lo", "-j", "ACCEPT"],
        ["INPUT", "-i", "lo", "-j", "ACCEPT"],
    ]
    for chain, *match in rules:
        _run_allow_failure(["iptables", "-D", chain] + match)

    ok_out, detail_out = _run(["iptables", "-P", "OUTPUT", "ACCEPT"])
    if not ok_out:
        return False, detail_out
    ok_in, detail_in = _run(["iptables", "-P", "INPUT", "ACCEPT"])
    if not ok_in:
        return False, detail_in

    ok_s_out, policy_out = _run(["iptables", "-S", "OUTPUT"])
    ok_s_in, policy_in = _run(["iptables", "-S", "INPUT"])
    if not (ok_s_out and "-P OUTPUT ACCEPT" in policy_out):
        return False, f"La política se restableció sin error pero OUTPUT ACCEPT no se pudo confirmar después: {policy_out}"
    if not (ok_s_in and "-P INPUT ACCEPT" in policy_in):
        return False, f"La política se restableció sin error pero INPUT ACCEPT no se pudo confirmar después: {policy_in}"

    return True, "iptables: reglas de aislamiento retiradas, políticas OUTPUT/INPUT restauradas a ACCEPT, verificado tras aplicar."


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

    server_host = _server_host()
    if not server_host:
        return False, "No se pudo determinar el host de ALFA_SENTINEL (config.SERVER_URL inválida) -- se aborta para no bloquear ese canal también."

    mode, is_real = _resolve_env_mode()

    if not is_real:
        return True, (
            f"[execution_mode=DEVELOPMENT, simulation=TRUE] SIMULADO: no se ejecutó ningún comando de red real. "
            f"En CONTROLLED_TEST/PRODUCTION, este endpoint bloquearía todo el tráfico salvo hacia {server_host}."
        )

    has_privileges, privilege_detail = _has_elevated_privileges()
    if not has_privileges:
        return False, f"[execution_mode={_mode_label(mode)}] Privilegios insuficientes para aislar la red de verdad: {privilege_detail}"

    system = platform.system()
    if system == "Windows":
        ok, detail = _isolate_windows(server_host)
    elif system == "Linux":
        ok, detail = _isolate_linux(server_host)
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

    server_host = _server_host()
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
