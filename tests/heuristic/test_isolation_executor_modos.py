"""Pruebas unitarias de agent/isolation_executor.py -- los 3 modos de
ejecución, idempotencia y verificación real (2026-08-17, ver
PENDIENTES.md, "Aislamiento de host -- modo development, laboratorio y
producción").

No requiere servidor ni base de datos -- prueba el módulo directo.

Para los casos de ejecución REAL (CONTROLLED_TEST/PRODUCTION con
privilegios), este sandbox de desarrollo NO tiene privilegios root
reales (confirmado: `sudo -n true` falla por "no new privileges" del
contenedor) -- mismo motivo por el que ISO-05 (test_episodios_
incidentes_aislamiento.py) probó el camino de fallo por falta de
privilegios en vez de la ejecución real contra el SO. Acá, además, se
simula el SO con un firewall falso (FakeIptables para Linux,
FakeWindowsFirewall para netsh/PowerShell) que intercepta
subprocess.run para poder probar honestamente la LÓGICA de Python
(orden de comandos, idempotencia vía -C, verificación posterior) sin
necesitar privilegios reales ni arriesgar la red del sandbox -- misma
técnica que ya se usó para CPU sintética (test_hr06_unit_synthetic.py,
FakeProcess/psutil fabricado) y para fanotify (test_fanotify_parsing_synthetic.py).

Ejecutar: python3 tests/heuristic/test_isolation_executor_modos.py
"""
import ipaddress
import json
import os
import subprocess
import sys
import tempfile

for _proxy_var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    os.environ.pop(_proxy_var, None)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import isolation_executor as ie  # noqa: E402


class _FakeResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeIptables:
    """Simula iptables/ip6tables con cadenas propias (2026-09-24): lo
    suficiente para ejercer la lógica real de isolation_executor.py sin
    tocar el sistema. Cada herramienta tiene sus cadenas; una cadena es
    una lista ordenada de reglas."""

    def __init__(self, preexisting_input_rules=()):
        self.tables = {}
        for tool in ("iptables", "ip6tables"):
            self.tables[tool] = {
                "chains": {"OUTPUT": [], "INPUT": list(preexisting_input_rules)},
                "policy": {"OUTPUT": "ACCEPT", "INPUT": "ACCEPT"},
            }
        self.calls = []

    def run(self, command, check=False):
        self.calls.append(list(command))
        tool, op = command[0], command[1]
        if tool not in self.tables:
            raise AssertionError(f"Comando no simulado: {command}")
        t = self.tables[tool]
        chains = t["chains"]
        fail = _FakeResult(1, "", "iptables: No chain/target/match by that name.")

        if op == "-N":
            if command[2] in chains:
                return _FakeResult(1, "", "Chain already exists.")
            chains[command[2]] = []
            return _FakeResult(0)
        if op == "-F":
            if command[2] not in chains:
                return fail
            chains[command[2]] = []
            return _FakeResult(0)
        if op == "-X":
            if command[2] not in chains:
                return fail
            del chains[command[2]]
            return _FakeResult(0)
        if op == "-A":
            chains[command[2]].append(tuple(command[3:]))
            return _FakeResult(0)
        if op == "-I":
            chains[command[2]].insert(int(command[3]) - 1, tuple(command[4:]))
            return _FakeResult(0)
        if op == "-C":
            return _FakeResult(0 if tuple(command[3:]) in chains.get(command[2], []) else 1)
        if op == "-D":
            rule = tuple(command[3:])
            if rule in chains.get(command[2], []):
                chains[command[2]].remove(rule)
                return _FakeResult(0)
            return fail
        if op == "-P":
            t["policy"][command[2]] = command[3]
            return _FakeResult(0)
        if op == "-S":
            chain = command[2]
            lines = [f"-P {chain} {t['policy'][chain]}"] if chain in t["policy"] else [f"-N {chain}"]
            lines += [f"-A {chain} {' '.join(rule)}" for rule in chains.get(chain, [])]
            return _FakeResult(0, "\n".join(lines))
        raise AssertionError(f"Comando no simulado: {command}")

    def first_rule(self, tool, chain):
        rules = self.tables[tool]["chains"][chain]
        return rules[0] if rules else None


class FakeWindowsFirewall:
    """Simula netsh advfirewall y Get/Set-NetFirewallProfile."""

    def __init__(self, profiles=None):
        self.rules = {}
        self.profiles = profiles or {
            name: {"Enabled": "True", "In": "Block", "Out": "Allow"} for name in ("Domain", "Private", "Public")
        }
        self.calls = []

    def run(self, command, check=False):
        self.calls.append(list(command))
        if command[0] == "powershell":
            script = command[-1]
            if script.startswith("Get-NetFirewallProfile"):
                data = [{"Name": n, **p} for n, p in self.profiles.items()]
                return _FakeResult(0, json.dumps(data))
            for part in script.split("; "):
                args = part.split()
                assert args[0] == "Set-NetFirewallProfile", part
                name = args[args.index("-Name") + 1]
                self.profiles[name] = {
                    "Enabled": args[args.index("-Enabled") + 1],
                    "In": args[args.index("-DefaultInboundAction") + 1],
                    "Out": args[args.index("-DefaultOutboundAction") + 1],
                }
            return _FakeResult(0)

        assert command[:2] == ["netsh", "advfirewall"], command
        if command[2:4] == ["set", "allprofiles"]:
            if command[4] == "state":
                for p in self.profiles.values():
                    p["Enabled"] = "True"
            else:
                inbound, outbound = command[5].split(",")
                for p in self.profiles.values():
                    p["In"] = "Block" if inbound.startswith("block") else "Allow"
                    p["Out"] = "Block" if outbound.startswith("block") else "Allow"
            return _FakeResult(0)
        action = command[3]
        args = dict(a.split("=", 1) for a in command[5:])
        name = args["name"]
        if action == "add":
            self.rules[name] = args
            return _FakeResult(0, "Aceptar")
        if action == "delete":
            return _FakeResult(0 if self.rules.pop(name, None) else 1, "", "No hay reglas que coincidan.")
        if action == "show":
            return _FakeResult(0, f"Nombre de regla: {name}") if name in self.rules else _FakeResult(1, "", "No hay reglas que coincidan.")
        raise AssertionError(f"Comando no simulado: {command}")


class _Simulated:
    """Instala un firewall simulado, fija el SO y privilegios, y
    restaura todo al salir."""

    def __init__(self, fake, system):
        self.fake, self.system = fake, system

    def __enter__(self):
        self.saved = (ie.subprocess.run, ie.platform.system, ie._has_elevated_privileges, ie.ISOLATION_STATE_FILE)
        fake = self.fake

        def fake_run(command, capture_output=True, text=True, timeout=None, check=False):
            result = fake.run(command, check)
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
            return result

        ie.subprocess.run = fake_run
        ie.platform.system = lambda: self.system
        ie._has_elevated_privileges = lambda: (True, "privilegios fabricados para la prueba")
        ie.ISOLATION_STATE_FILE = os.path.join(tempfile.mkdtemp(), "isolation_state.json")
        return fake

    def __exit__(self, *a):
        ie.subprocess.run, ie.platform.system, ie._has_elevated_privileges, ie.ISOLATION_STATE_FILE = self.saved


class _RealRun:
    """Guarda subprocess.run real para restaurarlo después de cada caso."""
    def __enter__(self):
        self.original = ie.subprocess.run
        return self

    def __exit__(self, *a):
        ie.subprocess.run = self.original


# ================= MH-01/MH-0x: los 3 modos, sin privilegios reales =================

os.environ.pop("ALFA_SENTINEL_ENV", None)  # sección 29: sin variable -> DEVELOPMENT (default)

# MH-01: DEVELOPMENT -- nunca ejecuta ningún comando real.
with _RealRun():
    calls = []
    ie.subprocess.run = lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("no debería llamarse a subprocess.run en DEVELOPMENT"))
    ok, msg = ie.execute_isolation("NETWORK")
    check("MH-01: DEVELOPMENT -> execute_isolation success=True", ok is True, str((ok, msg)))
    check("MH-01: DEVELOPMENT -> mensaje declara simulation=TRUE", "simulation=TRUE" in msg, msg)
    check("MH-01: DEVELOPMENT -> mensaje declara execution_mode=DEVELOPMENT", "execution_mode=DEVELOPMENT" in msg, msg)
    check("MH-01: DEVELOPMENT -> CERO comandos de sistema reales", len(calls) == 0, str(calls))

# MH-01b: liberar en DEVELOPMENT -- mismo criterio.
with _RealRun():
    ie.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debería llamarse a subprocess.run en DEVELOPMENT"))
    ok, msg = ie.execute_release("NETWORK")
    check("MH-01b: DEVELOPMENT release -> success=True, simulado", ok is True and "simulation=TRUE" in msg, str((ok, msg)))

# MH-02: CONTROLLED_TEST sin privilegios reales (honesto -- este sandbox no tiene root).
os.environ["ALFA_SENTINEL_ENV"] = "controlled_test"
ok, msg = ie.execute_isolation("NETWORK")
check("MH-02: CONTROLLED_TEST sin privilegios -> success=False", ok is False, str((ok, msg)))
check("MH-02: mensaje declara execution_mode=CONTROLLED_TEST", "execution_mode=CONTROLLED_TEST" in msg, msg)
check("MH-02: mensaje explica falta de privilegios", "rivilegio" in msg, msg)

# MH-02b: alias 'laboratory' -- mismo comportamiento real.
os.environ["ALFA_SENTINEL_ENV"] = "laboratory"
ok, msg = ie.execute_isolation("NETWORK")
check("MH-02b: alias LABORATORY también ejecuta real (falla por privilegios, no por modo)", ok is False and "rivilegio" in msg, str((ok, msg)))

# MH-03: PRODUCTION sin privilegios reales.
os.environ["ALFA_SENTINEL_ENV"] = "production"
ok, msg = ie.execute_isolation("NETWORK")
check("MH-03: PRODUCTION sin privilegios -> success=False", ok is False, str((ok, msg)))
check("MH-03: mensaje declara execution_mode=PRODUCTION", "execution_mode=PRODUCTION" in msg, msg)

os.environ["ALFA_SENTINEL_ENV"] = "controlled_test"

# ================= MH-04..MH-12: ejecución real con firewall simulado =================
#
# El SO se fija con platform.system, así que estas pruebas corren igual
# en Windows y en Linux sin tocar la red real.

ie.config.SERVER_URL = "https://192.168.81.1:8000"
SERVER = "192.168.81.1"

# --- Linux ---
SSH_ALLOW = ("-p", "tcp", "--dport", "22", "-j", "ACCEPT")  # regla previa, como la de ufw
with _Simulated(FakeIptables(preexisting_input_rules=[SSH_ALLOW]), "Linux") as fw:
    ok, msg = ie.execute_isolation("NETWORK")
    check("MH-04: Linux aislar -> success=True, simulation=FALSE", ok and "simulation=FALSE" in msg, msg)
    for tool in ("iptables", "ip6tables"):
        check(f"MH-04: {tool} -> ALFA_ISO_OUT es la PRIMERA regla de OUTPUT", fw.first_rule(tool, "OUTPUT") == ("-j", "ALFA_ISO_OUT"), fw.tables[tool]["chains"]["OUTPUT"])
        check(f"MH-04: {tool} -> ALFA_ISO_IN es la PRIMERA regla de INPUT (antes que la regla previa de SSH)", fw.first_rule(tool, "INPUT") == ("-j", "ALFA_ISO_IN"), fw.tables[tool]["chains"]["INPUT"])
    out_rules = fw.tables["iptables"]["chains"]["ALFA_ISO_OUT"]
    in_rules = fw.tables["iptables"]["chains"]["ALFA_ISO_IN"]
    check("MH-04: salida permitida SOLO hacia servidor:8000/tcp (y loopback)",
          out_rules == [("-o", "lo", "-j", "ACCEPT"), ("-d", SERVER, "-p", "tcp", "--dport", "8000", "-j", "ACCEPT"), ("-j", "DROP")], out_rules)
    check("MH-04: entrada permitida SOLO como respuesta ESTABLISHED del servidor:8000 (y loopback)",
          in_rules == [("-i", "lo", "-j", "ACCEPT"), ("-s", SERVER, "-p", "tcp", "--sport", "8000", "-m", "conntrack", "--ctstate", "ESTABLISHED", "-j", "ACCEPT"), ("-j", "DROP")], in_rules)
    check("MH-04: IPv6 -> todo descartado salvo loopback",
          fw.tables["ip6tables"]["chains"]["ALFA_ISO_OUT"] == [("-o", "lo", "-j", "ACCEPT"), ("-j", "DROP")])
    check("MH-04: las políticas por defecto NO se tocaron", fw.tables["iptables"]["policy"] == {"OUTPUT": "ACCEPT", "INPUT": "ACCEPT"}, fw.tables["iptables"]["policy"])

    ok2, msg2 = ie.execute_isolation("NETWORK")
    check("MH-05: Linux segunda ejecución -> sin duplicar enganches ni reglas",
          ok2 and fw.tables["iptables"]["chains"]["OUTPUT"].count(("-j", "ALFA_ISO_OUT")) == 1
          and fw.tables["iptables"]["chains"]["ALFA_ISO_OUT"] == out_rules, msg2)

    ok3, msg3 = ie.execute_release("NETWORK")
    check("MH-07: Linux liberar -> success=True", ok3, msg3)
    check("MH-07: Linux liberar -> cadenas borradas y el firewall queda como antes (regla de SSH intacta)",
          "ALFA_ISO_OUT" not in fw.tables["iptables"]["chains"] and fw.tables["iptables"]["chains"]["INPUT"] == [SSH_ALLOW]
          and fw.tables["iptables"]["chains"]["OUTPUT"] == [], fw.tables["iptables"]["chains"])

# MH-06: verificación real -- si el enganche no queda primero, se informa el fallo.
class LazyIptables(FakeIptables):
    def run(self, command, check=False):
        if command[1] == "-I":  # acepta el comando pero lo pone al final
            self.calls.append(list(command))
            self.tables[command[0]]["chains"][command[2]].append(tuple(command[4:]))
            return _FakeResult(0)
        return super().run(command, check)

with _Simulated(LazyIptables(preexisting_input_rules=[SSH_ALLOW]), "Linux"):
    ok, msg = ie.execute_isolation("NETWORK")
    check("MH-06: Linux enganche que no quedó primero -> success=False (nunca finge éxito)", ok is False and "no quedó primera" in msg, msg)

# MH-08: liberar un aislamiento hecho por la versión anterior (política DROP).
legacy = FakeIptables()
legacy.tables["iptables"]["chains"]["OUTPUT"] = [("-d", SERVER, "-j", "ACCEPT"), ("-o", "lo", "-j", "ACCEPT")]
legacy.tables["iptables"]["chains"]["INPUT"] = [("-s", SERVER, "-j", "ACCEPT"), ("-i", "lo", "-j", "ACCEPT")]
legacy.tables["iptables"]["policy"] = {"OUTPUT": "DROP", "INPUT": "DROP"}
with _Simulated(legacy, "Linux") as fw:
    ok, msg = ie.execute_release("NETWORK")
    check("MH-08: Linux liberar aislamiento viejo -> reglas viejas borradas y políticas vuelven a ACCEPT",
          ok and fw.tables["iptables"]["policy"] == {"OUTPUT": "ACCEPT", "INPUT": "ACCEPT"}
          and fw.tables["iptables"]["chains"]["OUTPUT"] == [] and "versión anterior" in msg, (msg, fw.tables["iptables"]))

# --- Windows ---
original_profiles = {
    "Domain": {"Enabled": "True", "In": "Block", "Out": "Allow"},
    "Private": {"Enabled": "False", "In": "Block", "Out": "Allow"},  # perfil apagado a propósito
    "Public": {"Enabled": "True", "In": "Block", "Out": "Allow"},
}
with _Simulated(FakeWindowsFirewall({k: dict(v) for k, v in original_profiles.items()}), "Windows") as fw:
    ok, msg = ie.execute_isolation("NETWORK")
    check("MH-09: Windows aislar -> success=True", ok and "simulation=FALSE" in msg, msg)
    allow = fw.rules.get("ALFA_SENTINEL_ALLOW_OUT", {})
    check("MH-09: Windows permite SOLO salida TCP al servidor:8000",
          allow.get("action") == "allow" and allow.get("protocol") == "TCP" and allow.get("remoteip") == SERVER and allow.get("remoteport") == "8000", allow)
    check("MH-09: Windows bloquea toda conexión entrante (regla de bloqueo, pisa reglas 'permitir' previas)",
          fw.rules.get("ALFA_SENTINEL_BLOCK_IN", {}).get("action") == "block" and fw.rules["ALFA_SENTINEL_BLOCK_IN"].get("remoteip") == "any")
    others = fw.rules.get("ALFA_SENTINEL_BLOCK_OUT_OTROS", {}).get("remoteip", "")
    check("MH-09: Windows bloquea salida a toda IP que no sea el servidor (incluido IPv6)",
          "::/0" in others and not any(ipaddress.ip_address(SERVER) in ipaddress.ip_network(n) for n in others.split(",") if ":" not in n), others[:80])
    check("MH-09: Windows bloquea el servidor en los demás puertos TCP y en UDP",
          fw.rules.get("ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_TCP", {}).get("remoteport") == "1-7999,8001-65535"
          and fw.rules.get("ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_UDP", {}).get("protocol") == "UDP")
    check("MH-09: Windows -> firewall encendido y bloqueando en los 3 perfiles",
          all(p == {"Enabled": "True", "In": "Block", "Out": "Block"} for p in fw.profiles.values()), fw.profiles)
    saved = json.load(open(ie.ISOLATION_STATE_FILE, encoding="utf-8"))["windows_profiles"]
    check("MH-09: Windows guardó la configuración original antes de aislar", saved == original_profiles, saved)

    ok2, _ = ie.execute_isolation("NETWORK")
    saved2 = json.load(open(ie.ISOLATION_STATE_FILE, encoding="utf-8"))["windows_profiles"]
    check("MH-10: Windows segunda ejecución NO pisa la configuración original guardada", ok2 and saved2 == original_profiles, saved2)

    ok3, msg3 = ie.execute_release("NETWORK")
    check("MH-11: Windows liberar -> restaura EXACTAMENTE la configuración previa (no 'permitir todo')",
          ok3 and fw.profiles == original_profiles and not fw.rules, (msg3, fw.profiles, fw.rules))
    check("MH-11: Windows liberar -> borra el archivo de estado", not os.path.exists(ie.ISOLATION_STATE_FILE))

with _Simulated(FakeWindowsFirewall(), "Windows") as fw:
    fw.rules["ALFA_SENTINEL_ALLOW_IN"] = {"action": "allow"}  # aislamiento de la versión anterior
    for p in fw.profiles.values():
        p.update({"In": "Block", "Out": "Block"})
    ok, msg = ie.execute_release("NETWORK")
    check("MH-12: Windows sin estado guardado -> vuelve al valor normal (bloquear entrantes, permitir salientes)",
          ok and all(p == {"Enabled": "True", "In": "Block", "Out": "Allow"} for p in fw.profiles.values()) and not fw.rules, (msg, fw.profiles))

os.environ.pop("ALFA_SENTINEL_ENV", None)

print()
total = len(RESULTS)
passed = sum(1 for _, ok in RESULTS if ok)
print(f"{passed}/{total} pruebas pasaron")
if passed != total:
    sys.exit(1)
