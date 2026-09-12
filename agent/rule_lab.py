#!/usr/bin/env python3
"""Laboratorio seguro de reglas para el Sistema ALFA-Sentinel.

Objetivo:
- provocar comportamientos BENIGNOS que permitan validar las reglas heurísticas;
- no ejecutar ransomware real;
- no cifrar archivos;
- no tocar documentos existentes del usuario;
- trabajar solamente dentro de una carpeta ALFA_SENTINEL_LAB creada por este script.

Uso recomendado:
1. Dejar el agente ALFA-Sentinel ejecutándose en otra terminal.
2. Ejecutar este archivo desde agent/ con el Python del .venv:
       .venv/bin/python rule_lab.py
3. Elegir UNA prueba y revisar la terminal del agente y la consola central.

HR-03 (Acceso Honeyfile) no se incluye como prueba principal porque se valida
mejor tocando un honeyfile real, que ya forma parte del flujo normal del agente.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime

AGENT_DIR = Path(__file__).resolve().parent
os.chdir(AGENT_DIR)
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import paths as agent_paths  # noqa: E402
from client import get_rule_policy  # noqa: E402
from credential import load_credential  # noqa: E402
from heuristic_engine import DEFAULT_RULES, FileActivityAnalyzer  # noqa: E402


RULES = {
    "HR01": "Modificacion Masiva Archivos",
    "HR02": "Renombrado Extension Anomala",
    "HR04": "Escritura Intensiva Archivos",
    "HR05": "Proceso Sospechoso",
    "HR06": "Consumo CPU Elevado",
    "HR07": "Acceso Recursos Compartidos",
    "HR08": "Creacion Masiva Temporales",
    "HR09": "Eliminacion Anomala Archivos",
    "HR10": "Actividad Archivos Usuario",
    "HR11": "Actividad Repetitiva Automatizada",
    "HR12": "Correlacion Multiples Indicadores",
}

MENU = [
    ("1", "HR01", "Modificación masiva de archivos"),
    ("2", "HR02", "Renombrado con extensión anómala"),
    ("3", "HR04", "Escritura intensiva de archivos"),
    ("4", "HR05", "Proceso sospechoso"),
    ("5", "HR06", "Consumo de CPU elevado"),
    ("6", "HR07", "Acceso a recursos compartidos (prueba de motor)"),
    ("7", "HR08", "Creación masiva de temporales"),
    ("8", "HR09", "Eliminación anómala de archivos"),
    ("9", "HR10", "Actividad repetitiva en carpetas de usuario"),
    ("10", "HR11", "Actividad automatizada del mismo proceso"),
    ("11", "HR12", "Correlación de múltiples indicadores"),
]

RANSOM_EXTENSION = ".locked"
OP_DELAY = 0.035


def banner():
    print("\n" + "=" * 72)
    print("  SISTEMA ALFA-SENTINEL - LABORATORIO SEGURO DE REGLAS")
    print("=" * 72)
    print("No cifra archivos, no modifica documentos existentes y no ejecuta ransomware.")
    print("Las operaciones de archivo se limitan a ALFA_SENTINEL_LAB.\n")


def monitored_documents_root() -> Path:
    """Obtiene la carpeta Documents que el agente monitorea en el modo actual."""
    roots = [Path(p).resolve() for p in agent_paths.get_monitored_roots()]
    for root in roots:
        if root.name.lower() == "documents":
            return root
    raise RuntimeError("No se encontró una raíz Documents dentro de las rutas monitoreadas por el agente.")


def lab_root() -> Path:
    documents = monitored_documents_root()
    root = documents / "ALFA_SENTINEL_LAB"

    if root.exists() and root.is_symlink():
        raise RuntimeError("ALFA_SENTINEL_LAB es un enlace simbólico. Se aborta por seguridad.")

    root.mkdir(parents=True, exist_ok=True)
    resolved = root.resolve()

    if resolved.parent != documents.resolve():
        raise RuntimeError("La carpeta de laboratorio no quedó dentro de Documents. Se aborta por seguridad.")

    return resolved


def new_case_dir(code: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    case = lab_root() / f"{code}_{stamp}"
    case.mkdir(parents=False, exist_ok=False)
    return case


def effective_policy() -> tuple[dict[str, dict], bool]:
    """Lee la política real del endpoint; si no puede, usa defaults locales."""
    credential = load_credential()

    if credential:
        response = get_rule_policy(credential)
        if response is not None and response.status_code == 200:
            rows = response.json().get("rules", [])
            return {row["name"]: row for row in rows}, True

    fallback = {
        name: {
            "name": name,
            "threshold": cfg["threshold"],
            "window_seconds": cfg["window_seconds"],
        }
        for name, cfg in DEFAULT_RULES.items()
    }
    return fallback, False


def cfg(policy: dict[str, dict], rule_name: str) -> dict | None:
    return policy.get(rule_name)


def threshold(policy: dict[str, dict], rule_name: str, default: int) -> int:
    row = cfg(policy, rule_name)
    if not row:
        return default
    return max(1, int(math.ceil(float(row.get("threshold", default)))))


def window(policy: dict[str, dict], rule_name: str, default: float) -> float:
    row = cfg(policy, rule_name)
    if not row or row.get("window_seconds") is None:
        return default
    return max(0.1, float(row["window_seconds"]))


def require_active(policy: dict[str, dict], code: str) -> bool:
    name = RULES[code]
    if name not in policy:
        print(f"\n⚠ {code} - {name} no está activa en la política efectiva de este endpoint.")
        print("Actívala desde la consola o cambia la configuración del endpoint antes de probarla.")
        return False
    return True


def touch_empty(path: Path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)


def create_empty_files(directory: Path, count: int, suffix: str = ".txt", prefix: str = "archivo") -> list[Path]:
    paths = []
    for i in range(count):
        p = directory / f"{prefix}_{i:04d}{suffix}"
        touch_empty(p)
        paths.append(p)
        time.sleep(OP_DELAY)
    return paths


def append_once(paths: list[Path], text: str = "ALFA_SENTINEL_LAB\n"):
    for p in paths:
        with p.open("a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        time.sleep(OP_DELAY)


def wait_for_old_user_activity(policy: dict[str, dict]):
    """Deja vencer la ventana de HR-10 para que el preparado no contamine la prueba."""
    user_rule = RULES["HR10"]
    seconds = window(policy, user_rule, 20.0) + 1.0
    print(f"Preparación terminada. Esperando {seconds:.0f}s para que venza la ventana de actividad previa...")
    time.sleep(seconds)


def test_hr01(policy: dict[str, dict]):
    if not require_active(policy, "HR01"):
        return
    n = threshold(policy, RULES["HR01"], 20)
    d = new_case_dir("HR01")
    print(f"\nHR01: preparando {n} archivos únicos en {d}")
    files = create_empty_files(d, n)
    wait_for_old_user_activity(policy)
    print(f"Modificando {n} archivos únicos rápidamente...")
    append_once(files)
    print("✓ Actividad generada. Esperado: 'Modificacion Masiva Archivos'.")


def test_hr02(policy: dict[str, dict]):
    if not require_active(policy, "HR02"):
        return
    n = threshold(policy, RULES["HR02"], 5)
    d = new_case_dir("HR02")
    print(f"\nHR02: creando y renombrando {n} archivos dentro de {d}")
    files = create_empty_files(d, n, suffix=".txt", prefix="documento")
    for p in files:
        p.rename(p.with_name(p.name + RANSOM_EXTENSION))
        time.sleep(OP_DELAY)
    print(f"✓ Actividad generada. Esperado: 'Renombrado Extension Anomala' ({RANSOM_EXTENSION}).")


def test_hr04(policy: dict[str, dict]):
    if not require_active(policy, "HR04"):
        return
    n = threshold(policy, RULES["HR04"], 50)
    d = new_case_dir("HR04")
    print(f"\nHR04: realizando al menos {n} modificaciones dentro de {d}")
    files = create_empty_files(d, n, suffix=".dat", prefix="write")
    append_once(files, "x\n")
    print("✓ Actividad generada. Esperado: 'Escritura Intensiva Archivos'.")
    print("  Nota: en una prueba E2E esta carga también puede superar HR01 y HR10; eso es coherente")
    print("  con las reglas actuales, porque 50 modificaciones también son actividad masiva de usuario.")


def test_hr05(policy: dict[str, dict]):
    if not require_active(policy, "HR05"):
        return
    d = new_case_dir("HR05")
    relocated_dir = d / "ruta_atipica"
    relocated_dir.mkdir()
    relocated_python = relocated_dir / "python_lab"
    shutil.copy2(sys.executable, relocated_python)
    relocated_python.chmod(0o700)

    target = d / "archivo_controlado.txt"
    helper = d / "writer_hold.py"
    helper.write_text(
        "import sys, time\n"
        "p=sys.argv[1]\n"
        "with open(p,'w',encoding='utf-8') as f:\n"
        "    f.write('ALFA_SENTINEL_LAB\\n'); f.flush()\n"
        "    time.sleep(5)\n",
        encoding="utf-8",
    )

    print(f"\nHR05: ejecutando un Python real desde una ruta atípica controlada:\n  {relocated_python}")
    proc = subprocess.Popen([str(relocated_python), str(helper), str(target)])
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    print("✓ Proceso de laboratorio finalizado. Esperado: 'Proceso Sospechoso' si la atribución del SO fue exitosa.")


def test_hr06(policy: dict[str, dict]):
    if not require_active(policy, "HR06"):
        return
    seconds = window(policy, RULES["HR06"], 10.0) + 5.0
    print(f"\nHR06: se utilizará aproximadamente un núcleo de CPU durante {seconds:.0f}s.")
    print("No se escribe ni borra ningún archivo del usuario.")
    code = (
        "import time\n"
        f"end=time.time()+{seconds!r}\n"
        "x=0\n"
        "while time.time()<end:\n"
        "    x=(x*1664525+1013904223)&0xffffffff\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code])
    proc.wait(timeout=seconds + 10)
    print("✓ Carga de CPU terminada. Esperado: 'Consumo CPU Elevado' si superó el umbral efectivo de CPU.")


def test_hr07(policy: dict[str, dict]):
    if not require_active(policy, "HR07"):
        return
    row = cfg(policy, RULES["HR07"])
    n = threshold(policy, RULES["HR07"], 20)
    w = row.get("window_seconds") if row else 15

    print("\nHR07: PRUEBA DE MOTOR, sin montar SMB/NFS ni tocar una red compartida real.")
    print("La implementación actual reconoce rutas compartidas por prefijo UNC //servidor/recurso.")
    analyzer = FileActivityAnalyzer.from_policy([
        {"name": RULES["HR07"], "threshold": n, "window_seconds": w}
    ])
    matched = []
    for i in range(n):
        matched = analyzer.register_event(f"//alfa-lab/recurso/archivo_{i}.txt", "file_modified")
    ok = RULES["HR07"] in matched
    print(f"{'✓' if ok else '✗'} Resultado del motor: {matched or 'ninguna regla'}")
    print("Esta prueba valida HR07 de forma aislada; no crea una alerta en la consola porque no falsifica un acceso de red real.")


def test_hr08(policy: dict[str, dict]):
    if not require_active(policy, "HR08"):
        return
    n = threshold(policy, RULES["HR08"], 30)
    d = new_case_dir("HR08")
    print(f"\nHR08: creando {n} archivos .tmp controlados en {d}")
    create_empty_files(d, n, suffix=".tmp", prefix="temp")
    print("✓ Actividad generada. Esperado: 'Creacion Masiva Temporales'.")
    print("  Puede coincidir también HR10 porque Documents es una carpeta de usuario.")


def test_hr09(policy: dict[str, dict]):
    if not require_active(policy, "HR09"):
        return
    n = threshold(policy, RULES["HR09"], 20)
    d = new_case_dir("HR09")
    print(f"\nHR09: preparando {n} archivos creados por ESTE laboratorio en {d}")
    files = create_empty_files(d, n, suffix=".dat", prefix="delete")
    wait_for_old_user_activity(policy)
    print(f"Eliminando únicamente esos {n} archivos de laboratorio...")
    for p in files:
        p.unlink()
        time.sleep(OP_DELAY)
    print("✓ Actividad generada. Esperado: 'Eliminacion Anomala Archivos'.")


def test_hr10(policy: dict[str, dict]):
    if not require_active(policy, "HR10"):
        return
    n = threshold(policy, RULES["HR10"], 30)
    d = new_case_dir("HR10")
    print(f"\nHR10: creando {n} archivos no temporales dentro de Documents: {d}")
    create_empty_files(d, n, suffix=".dat", prefix="usuario")
    print("✓ Actividad generada. Esperado: 'Actividad Archivos Usuario'.")


def test_hr11(policy: dict[str, dict]):
    if not require_active(policy, "HR11"):
        return
    n = threshold(policy, RULES["HR11"], 40)
    d = new_case_dir("HR11")
    print(f"\nHR11: un SOLO proceso hijo realizará {n} creaciones de archivos en {d}")

    child_code = (
        "import os,sys,time\n"
        "root=sys.argv[1]; n=int(sys.argv[2])\n"
        "for i in range(n):\n"
        "    p=os.path.join(root, f'op_{i:04d}.dat')\n"
        "    fd=os.open(p, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600); os.close(fd)\n"
        f"    time.sleep({OP_DELAY!r})\n"
        "time.sleep(3)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", child_code, str(d), str(n)])
    proc.wait(timeout=max(15, n * OP_DELAY + 10))
    print("✓ Proceso automatizado finalizado. Esperado: 'Actividad Repetitiva Automatizada'.")
    print("  Puede coincidir HR10 porque el mismo comportamiento ocurre dentro de Documents.")


def test_hr12(policy: dict[str, dict]):
    if not require_active(policy, "HR12"):
        return
    if not require_active(policy, "HR01") or not require_active(policy, "HR02"):
        print("HR12 necesita al menos dos indicadores activos; para esta prueba se usan HR01 + HR02.")
        return

    n_mod = threshold(policy, RULES["HR01"], 20)
    n_rename = threshold(policy, RULES["HR02"], 5)
    d = new_case_dir("HR12")
    mod_dir = d / "modificaciones"
    rename_dir = d / "renombrados"
    mod_dir.mkdir()
    rename_dir.mkdir()

    print("\nHR12: preparando dos indicadores distintos (HR01 + HR02) dentro del mismo episodio.")
    mod_files = create_empty_files(mod_dir, n_mod, suffix=".dat", prefix="mod")
    rename_files = create_empty_files(rename_dir, n_rename, suffix=".txt", prefix="ren")
    wait_for_old_user_activity(policy)

    print(f"1/2 Modificando {n_mod} archivos únicos...")
    append_once(mod_files, "correlation\n")
    print(f"2/2 Renombrando {n_rename} archivos a {RANSOM_EXTENSION}...")
    for p in rename_files:
        p.rename(p.with_name(p.name + RANSOM_EXTENSION))
        time.sleep(OP_DELAY)

    print("✓ Dos indicadores distintos generados en el mismo episodio.")
    print("Esperado en el SERVIDOR: HR12 aplica bonificación de correlación (+5 para 2 reglas distintas).")
    print("Revisa el detalle de la alerta en la consola; HR12 se calcula en el servidor, no en el agente.")


TESTS = {
    "HR01": test_hr01,
    "HR02": test_hr02,
    "HR04": test_hr04,
    "HR05": test_hr05,
    "HR06": test_hr06,
    "HR07": test_hr07,
    "HR08": test_hr08,
    "HR09": test_hr09,
    "HR10": test_hr10,
    "HR11": test_hr11,
    "HR12": test_hr12,
}


def print_policy(policy: dict[str, dict], from_server: bool):
    print("\nPolítica usada:", "servidor (efectiva del endpoint)" if from_server else "fallback local DEFAULT_RULES")
    for code, name in RULES.items():
        row = policy.get(name)
        if row:
            print(f"  {code}  {name}: umbral={row.get('threshold')} ventana={row.get('window_seconds')}")
        else:
            print(f"  {code}  {name}: INACTIVA / no recibida")


def run_one(code: str, policy: dict[str, dict]):
    code = code.upper().replace("-", "")
    if code == "HR03":
        print("HR03 se prueba tocando un honeyfile real; no se duplica aquí porque ya la validaste.")
        return
    func = TESTS.get(code)
    if not func:
        raise ValueError(f"Regla no soportada: {code}")
    func(policy)
    print("\nRevisa ahora la terminal del agente y la consola central antes de ejecutar otra prueba.")
    print("Los archivos del laboratorio se dejan intactos para no generar falsos eventos de eliminación al limpiar.")


def interactive(policy: dict[str, dict], from_server: bool):
    while True:
        banner()
        print_policy(policy, from_server)
        print("\nPruebas disponibles:")
        for number, code, label in MENU:
            print(f"  {number:>2}. {code} - {label}")
        print("   p. Volver a cargar la política desde el servidor")
        print("   q. Salir")
        choice = input("\nSelecciona una prueba: ").strip().lower()

        if choice == "q":
            return
        if choice == "p":
            policy, from_server = effective_policy()
            continue

        selected = next((code for number, code, _ in MENU if number == choice), None)
        if not selected:
            print("Opción inválida.")
            time.sleep(1)
            continue

        print("\nIMPORTANTE: ejecuta una prueba por vez y revisa el resultado antes de continuar.")
        run_one(selected, policy)
        input("\nPresiona ENTER para volver al menú...")


def main():
    parser = argparse.ArgumentParser(description="Laboratorio seguro de reglas del Sistema ALFA-Sentinel")
    parser.add_argument("--rule", help="Ejecuta directamente una regla: HR01, HR02, HR04...HR12")
    parser.add_argument("--show-policy", action="store_true", help="Muestra la política efectiva y termina")
    args = parser.parse_args()

    policy, from_server = effective_policy()

    if args.show_policy:
        print_policy(policy, from_server)
        return

    if args.rule:
        banner()
        print_policy(policy, from_server)
        run_one(args.rule, policy)
        return

    interactive(policy, from_server)


if __name__ == "__main__":
    main()
