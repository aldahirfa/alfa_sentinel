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
simula el SO con un "iptables falso" (FakeIptables) que intercepta
subprocess.run para poder probar honestamente la LÓGICA de Python
(orden de comandos, idempotencia vía -C, verificación posterior) sin
necesitar privilegios reales ni arriesgar la red del sandbox -- misma
técnica que ya se usó para CPU sintética (test_hr06_unit_synthetic.py,
FakeProcess/psutil fabricado) y para fanotify (test_fanotify_parsing_synthetic.py).

Ejecutar: python3 tests/heuristic/test_isolation_executor_modos.py
"""
import os
import subprocess
import sys

for _proxy_var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    os.environ.pop(_proxy_var, None)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import isolation_executor as ie  # noqa: E402


class FakeIptables:
    """Simula lo suficiente del comportamiento REAL de iptables como
    para ejercer honestamente la lógica de idempotencia/verificación de
    isolation_executor.py, sin tocar el sistema real. Registra cada
    invocación para poder afirmar sobre idempotencia (¿se insertó de
    nuevo una regla que ya estaba?)."""

    def __init__(self):
        self.rules = set()  # {(chain, tuple(match_args))}
        self.policy = {"OUTPUT": "ACCEPT", "INPUT": "ACCEPT"}
        self.insert_calls = 0
        self.delete_calls = 0
        self.calls = []

    def run(self, command, capture_output=True, text=True, timeout=None, check=False):
        self.calls.append(list(command))
        assert command[0] == "iptables"

        if command[1] == "-C":
            chain = command[2]
            match = tuple(command[3:])
            rc = 0 if (chain, match) in self.rules else 1
            return _FakeResult(rc, "", "")

        if command[1] == "-I":
            chain = command[2]
            # ["iptables", "-I", chain, "1", *match]
            match = tuple(command[4:])
            self.rules.add((chain, match))
            self.insert_calls += 1
            return _FakeResult(0, "", "")

        if command[1] == "-D":
            chain = command[2]
            match = tuple(command[3:])
            self.delete_calls += 1
            if (chain, match) in self.rules:
                self.rules.discard((chain, match))
                return _FakeResult(0, "", "")
            if check:
                raise subprocess.CalledProcessError(1, command, output="", stderr="Bad rule (does a matching rule exist in that chain?).")
            return _FakeResult(1, "", "Bad rule (does a matching rule exist in that chain?).")

        if command[1] == "-P":
            chain, target = command[2], command[3]
            self.policy[chain] = target
            return _FakeResult(0, "", "")

        if command[1] == "-S":
            chain = command[2]
            lines = [f"-P {chain} {self.policy[chain]}"]
            for (c, match) in self.rules:
                if c == chain:
                    lines.append(f"-A {chain} {' '.join(match)}")
            return _FakeResult(0, "\n".join(lines), "")

        raise AssertionError(f"Comando iptables no simulado: {command}")


class _FakeResult:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _install_fake(monkeypatch_target, fake):
    def fake_run(command, capture_output=True, text=True, timeout=None, check=False):
        result = fake.run(command, capture_output, text, timeout, check)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
        return result
    monkeypatch_target.run = fake_run


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

# ================= MH-04/05/06/07/08: ejecución real simulada con FakeIptables =================

if sys.platform.startswith("linux"):

    # MH-04: aislar con privilegios (fabricados) -- inserta reglas, política DROP, verificado.
    fake = FakeIptables()
    with _RealRun():
        _install_fake(ie.subprocess, fake)
        original_priv = ie._has_elevated_privileges
        ie._has_elevated_privileges = lambda: (True, "fake root para prueba")
        try:
            ok, msg = ie.execute_isolation("NETWORK")
            check("MH-04: CONTROLLED_TEST + privilegios fabricados -> success=True", ok is True, str((ok, msg)))
            check("MH-04: mensaje declara simulation=FALSE (ejecución real)", "simulation=FALSE" in msg, msg)
            check("MH-04: política OUTPUT quedó en DROP", fake.policy["OUTPUT"] == "DROP", str(fake.policy))
            check("MH-04: política INPUT quedó en DROP", fake.policy["INPUT"] == "DROP", str(fake.policy))
            check("MH-04: se insertaron las 4 reglas de excepción esperadas", len(fake.rules) == 4, str(fake.rules))
            check("MH-04: hubo exactamente 4 inserciones (-I)", fake.insert_calls == 4, str(fake.insert_calls))

            # MH-05: idempotencia -- ejecutar de nuevo NO debe insertar reglas duplicadas.
            ok2, msg2 = ie.execute_isolation("NETWORK")
            check("MH-05: segunda ejecución -> success=True también", ok2 is True, str((ok2, msg2)))
            check("MH-05: idempotencia -- sigue habiendo exactamente 4 reglas (no duplicadas)", len(fake.rules) == 4, str(fake.rules))
            check("MH-05: idempotencia -- NO hubo una segunda tanda de inserciones (-C evitó los -I)", fake.insert_calls == 4, str(fake.insert_calls))

            # MH-07: liberar -- borra reglas, restaura ACCEPT, verificado.
            ok3, msg3 = ie.execute_release("NETWORK")
            check("MH-07: release con privilegios fabricados -> success=True", ok3 is True, str((ok3, msg3)))
            check("MH-07: política OUTPUT restaurada a ACCEPT", fake.policy["OUTPUT"] == "ACCEPT", str(fake.policy))
            check("MH-07: política INPUT restaurada a ACCEPT", fake.policy["INPUT"] == "ACCEPT", str(fake.policy))
            check("MH-07: las reglas de excepción ya no están", len(fake.rules) == 0, str(fake.rules))
        finally:
            ie._has_elevated_privileges = original_priv

    # MH-06: verificación real -- si el comando de política "miente" (termina
    # sin error pero -S nunca refleja DROP), execute_isolation debe FALLAR
    # en vez de confiar ciegamente en que el comando no lanzó excepción
    # (sección 14 de la especificación: "no devolver EXECUTED simplemente
    # porque el comando terminó sin excepción").
    class FlakyIptables(FakeIptables):
        def run(self, command, capture_output=True, text=True, timeout=None, check=False):
            if command[1] == "-P":
                # Acepta el comando (no lanza error) pero NO aplica el cambio de verdad.
                return _FakeResult(0, "", "")
            return super().run(command, capture_output, text, timeout, check)

    flaky = FlakyIptables()
    with _RealRun():
        _install_fake(ie.subprocess, flaky)
        original_priv = ie._has_elevated_privileges
        ie._has_elevated_privileges = lambda: (True, "fake root para prueba")
        try:
            ok, msg = ie.execute_isolation("NETWORK")
            check("MH-06: política que no se aplicó de verdad -> execute_isolation detecta el fallo (success=False)", ok is False, str((ok, msg)))
            check("MH-06: mensaje explica que no se pudo confirmar", "no se pudo confirmar" in msg, msg)
        finally:
            ie._has_elevated_privileges = original_priv

    # MH-08: falla real al liberar (ej. comando de política falla) -- nunca debe reportarse éxito.
    class FailingReleaseIptables(FakeIptables):
        def run(self, command, capture_output=True, text=True, timeout=None, check=False):
            if command[1] == "-P" and command[3] == "ACCEPT":
                raise subprocess.CalledProcessError(1, command, output="", stderr="firewall ocupado (simulado)")
            return super().run(command, capture_output, text, timeout, check)

    failing = FailingReleaseIptables()
    with _RealRun():
        _install_fake(ie.subprocess, failing)
        original_priv = ie._has_elevated_privileges
        ie._has_elevated_privileges = lambda: (True, "fake root para prueba")
        try:
            ok, msg = ie.execute_release("NETWORK")
            check("MH-08: fallo real al liberar -> success=False (nunca finge éxito)", ok is False, str((ok, msg)))
        finally:
            ie._has_elevated_privileges = original_priv

else:
    print("(MH-04..08 omitidas -- requieren simular el adaptador Linux, este sistema no es Linux)")

os.environ.pop("ALFA_SENTINEL_ENV", None)

print()
total = len(RESULTS)
passed = sum(1 for _, ok in RESULTS if ok)
print(f"{passed}/{total} pruebas pasaron")
if passed != total:
    sys.exit(1)
