"""Corre todos los archivos test_*.py de este directorio en secuencia
y agrega el resultado -- no usa pytest (el proyecto no lo tiene como
dependencia, ver README.md de este directorio); cada test_*.py ya es
un script standalone con sus propios asserts y sys.exit(0/1), mismo
estilo que agent/test_mass_activity.py.

Ejecutar: python3 tests/heuristic/run_all.py
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TEST_FILES = sorted(
    f for f in glob.glob(os.path.join(HERE, "test_*.py"))
)

print(f"Se van a correr {len(TEST_FILES)} archivos de prueba:\n")
for f in TEST_FILES:
    print(" -", os.path.basename(f))
print()

overall_ok = True
summary = []

for test_file in TEST_FILES:
    name = os.path.basename(test_file)
    print("=" * 70)
    print(name)
    print("=" * 70)
    result = subprocess.run([sys.executable, test_file], cwd=HERE)
    ok = result.returncode == 0
    overall_ok = overall_ok and ok
    summary.append((name, ok))
    print()

print("=" * 70)
print("RESUMEN")
print("=" * 70)
for name, ok in summary:
    print(("OK  " if ok else "FAIL"), "-", name)

print()
print(f"{sum(1 for _, ok in summary if ok)}/{len(summary)} archivos de prueba OK")
sys.exit(0 if overall_ok else 1)
