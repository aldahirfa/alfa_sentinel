"""Pruebas A-D de atribución de procesos (sección 19 de la
especificación de atribución de procesos, 2026-08-16). Corren contra
agent/adapters/get_process_for_file_event(...) real -- en este
entorno de desarrollo (Linux sin privilegios para fanotify, ver
tests/heuristic/README.md) ejercitan la cadena completa cayendo al
FALLBACK (psutil.open_files()), que es exactamente el comportamiento
honesto esperado: fanotify no disponible -> fallback -> resultado
igual de válido.

Ejecutar: python3 tests/heuristic/test_attribution.py
"""
import os
import shutil
import sys
import tempfile

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import get_process_for_file_event  # noqa: E402
import lab_processes as lab  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


LAB_DIR = tempfile.mkdtemp(prefix="alfa_attrib_lab_")

try:
    # ---------------- Prueba A ----------------
    # Un proceso de laboratorio modifica un archivo. Esperado:
    # process_id = PID del proceso, process_name = nombre real.
    file_a = os.path.join(LAB_DIR, "prueba_a.txt")
    proc_a = lab.spawn_handshake_writer(file_a)
    try:
        ready = lab.wait_ready(file_a)
        check("A: el proceso de laboratorio señaló que el archivo está abierto", ready)

        result = get_process_for_file_event(file_a, "file_modified")
        check("A: atribución no es None mientras el archivo sigue abierto", result is not None, str(result))
        if result:
            check("A: process_id = PID real del proceso de laboratorio", result["process_id"] == proc_a.pid, f"{result['process_id']} != {proc_a.pid}")
            check("A: process_name es el nombre real del intérprete", result["process_name"] in ("python3", "python", "python3.10", "python3.12"), result["process_name"])
            check("A: incluye 'username'", "username" in result and result["username"], str(result))
    finally:
        lab.signal_go(file_a)
        proc_a.wait(timeout=10)

    # ---------------- Prueba B ----------------
    # Un proceso de laboratorio realiza múltiples operaciones.
    # Esperado: todos los eventos tienen el mismo PID.
    multi_dir = os.path.join(LAB_DIR, "prueba_b")
    OP_COUNT = 4
    proc_b = lab.spawn_multi_writer(multi_dir, OP_COUNT)
    pids_seen = []
    try:
        for i in range(OP_COUNT):
            file_path = os.path.join(multi_dir, f"op_{i}.txt")
            ready = lab.wait_ready(file_path)
            if not ready:
                pids_seen.append(None)
                continue
            result = get_process_for_file_event(file_path, "file_modified")
            pids_seen.append(result["process_id"] if result else None)
            lab.signal_go(file_path)
        proc_b.wait(timeout=15)
    finally:
        if proc_b.poll() is None:
            proc_b.kill()

    check("B: se pudo atribuir las 4 operaciones", all(p is not None for p in pids_seen), str(pids_seen))
    check("B: todas las operaciones quedan asociadas al MISMO PID (el del proceso de laboratorio)", len(set(pids_seen)) == 1 and pids_seen[0] == proc_b.pid, f"{pids_seen} vs esperado {proc_b.pid}")

    # ---------------- Prueba C ----------------
    # Un proceso de laboratorio termina antes de poder obtener
    # metadata (no usa handshake -- abre, escribe, cierra y TERMINA
    # antes de que la prueba consulte la atribución). Esperado: evento
    # válido, process_id/process_name pueden ser None -- eso es válido
    # (sección 9: "si el proceso ya terminó ... eso es válido"), no un
    # error.
    file_c = os.path.join(LAB_DIR, "prueba_c.txt")
    proc_c = lab.spawn_short_lived_writer(file_c)  # ya terminó (proc.wait() adentro)
    check("C: el proceso de laboratorio ya terminó antes de consultar", proc_c.poll() is not None)

    result_c = get_process_for_file_event(file_c, "file_modified")
    check(
        "C: atribución de un proceso ya terminado no rompe -- devuelve None (no inventa un PID)",
        result_c is None,
        str(result_c),
    )

    # ---------------- Prueba D ----------------
    # Dos procesos DISTINTOS realizan operaciones al mismo tiempo.
    # Esperado: sus eventos quedan asociados a sus respectivos PID,
    # nunca mezclados.
    file_d1 = os.path.join(LAB_DIR, "prueba_d_1.txt")
    file_d2 = os.path.join(LAB_DIR, "prueba_d_2.txt")
    proc_d1 = lab.spawn_handshake_writer(file_d1)
    proc_d2 = lab.spawn_handshake_writer(file_d2)
    try:
        ready1 = lab.wait_ready(file_d1)
        ready2 = lab.wait_ready(file_d2)
        check("D: ambos procesos de laboratorio señalaron archivo abierto", ready1 and ready2)

        result_d1 = get_process_for_file_event(file_d1, "file_modified")
        result_d2 = get_process_for_file_event(file_d2, "file_modified")

        check("D: archivo 1 atribuido al PID del proceso 1", result_d1 is not None and result_d1["process_id"] == proc_d1.pid, str(result_d1))
        check("D: archivo 2 atribuido al PID del proceso 2", result_d2 is not None and result_d2["process_id"] == proc_d2.pid, str(result_d2))
        check("D: los dos PID son distintos entre sí (no se mezclaron)", proc_d1.pid != proc_d2.pid)
    finally:
        lab.signal_go(file_d1)
        lab.signal_go(file_d2)
        proc_d1.wait(timeout=10)
        proc_d2.wait(timeout=10)

finally:
    shutil.rmtree(LAB_DIR, ignore_errors=True)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_attribution.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
