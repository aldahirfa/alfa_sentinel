"""Regresión de las reglas de archivos preexistentes -- HR-01, HR-02,
HR-03, HR-04, HR-07, HR-08, HR-09, HR-10 (sección 17/23 de la
especificación de atribución de procesos, 2026-08-16: "conservar...
la nueva atribución debe integrarse sin romperlas" / "los scripts
deben leer la configuración real cuando sea posible, no duplicar
permanentemente threshold/window en múltiples archivos de prueba").

Por eso este archivo NO hardcodea los números de umbral/ventana: los
lee de agent/heuristic_engine.py::DEFAULT_RULES (la misma fuente que
usa el agente real cuando no hay política del servidor) vía
FileActivityAnalyzer.from_policy(None). Si algún día cambian los
valores por defecto en el código real, esta prueba se ajusta sola en
vez de quedar comparando contra un número copiado a mano que puede
quedar desactualizado.

No usa atribución de proceso (HR-01/02/03/04/07/08/09/10 no la
necesitan -- son las mismas reglas de antes de la especificación de
atribución de procesos) ni ransomware real -- solo llama a
FileActivityAnalyzer.register_event(...) directamente, la misma
función que usa agent/file_monitor.py en producción.

Ejecutar: python3 tests/heuristic/test_file_rules_regression.py
"""
import os
import sys

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))

from heuristic_engine import FileActivityAnalyzer, RANSOMWARE_EXTENSIONS  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


def cfg_of(rule_name):
    """Lee threshold/window_seconds real de DEFAULT_RULES -- no se
    duplica el número acá."""
    analyzer = FileActivityAnalyzer.from_policy(None)
    return analyzer.rules[rule_name]


def fresh_analyzer():
    return FileActivityAnalyzer.from_policy(None)


# ---------------- HR-01: Modificacion Masiva Archivos ----------------
rule_name = "Modificacion Masiva Archivos"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"/tmp/hr01_{i}.txt", "file_modified")
check(f"HR-01: {threshold} archivos ÚNICOS modificados -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = []
for i in range(threshold - 1):
    matched_neg = analyzer_neg.register_event(f"/tmp/hr01_neg_{i}.txt", "file_modified")
check(f"HR-01: {threshold - 1} archivos únicos (threshold-1) -> NO dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-02: Renombrado Extension Anomala ----------------
rule_name = "Renombrado Extension Anomala"
threshold = int(cfg_of(rule_name)["threshold"])
ransomware_ext = sorted(RANSOMWARE_EXTENSIONS)[0]
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"/tmp/hr02_{i}{ransomware_ext}", "file_renamed")
check(f"HR-02: {threshold} renombrados con extensión de ransomware conocida -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = analyzer_neg.register_event("/tmp/hr02_normal.docx", "file_renamed")
check("HR-02: renombrado a una extensión NO asociada a ransomware -> no dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-03: Acceso Honeyfile ----------------
rule_name = "Acceso Honeyfile"
analyzer = fresh_analyzer()
matched = analyzer.register_event("/tmp/honeyfiles/HOLA.txt", "file_modified", is_honeyfile=True)
check("HR-03: interacción con un honeyfile -> dispara de inmediato (sin ventana ni umbral)", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = analyzer_neg.register_event("/tmp/normal.txt", "file_modified", is_honeyfile=False)
check("HR-03: archivo normal (no honeyfile) -> no dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-04: Escritura Intensiva Archivos ----------------
rule_name = "Escritura Intensiva Archivos"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
# Mismo archivo repetido a propósito: HR-04 cuenta operaciones
# TOTALES, no archivos únicos (a diferencia de HR-01) -- reusar la
# misma ruta aísla la prueba de HR-01 (que no llegaría a su propio
# umbral con un solo archivo único).
for i in range(threshold):
    matched = analyzer.register_event("/tmp/hr04_same_file.txt", "file_modified")
check(f"HR-04: {threshold} escrituras sobre el MISMO archivo -> dispara (cuenta operaciones, no únicos)", rule_name in matched, str(matched))
check("HR-04: HR-01 no interfiere (solo 1 archivo único tocado)", "Modificacion Masiva Archivos" not in matched, str(matched))

# ---------------- HR-07: Acceso Recursos Compartidos ----------------
rule_name = "Acceso Recursos Compartidos"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"//servidor/recurso/archivo_{i}.txt", "file_modified")
check(f"HR-07: {threshold} operaciones sobre una ruta UNC compartida -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = analyzer_neg.register_event("/tmp/local.txt", "file_modified")
check("HR-07: ruta local (no UNC) -> no dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-08: Creacion Masiva Temporales ----------------
rule_name = "Creacion Masiva Temporales"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"/tmp/temp/archivo_{i}.tmp", "file_created")
check(f"HR-08: {threshold} archivos temporales creados -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = analyzer_neg.register_event("/tmp/documento.docx", "file_created")
check("HR-08: creación de un archivo NO temporal -> no dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-09: Eliminacion Anomala Archivos ----------------
rule_name = "Eliminacion Anomala Archivos"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"/tmp/hr09_{i}.txt", "file_deleted")
check(f"HR-09: {threshold} eliminaciones -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = []
for i in range(threshold - 1):
    matched_neg = analyzer_neg.register_event(f"/tmp/hr09_neg_{i}.txt", "file_deleted")
check(f"HR-09: {threshold - 1} eliminaciones (threshold-1) -> no dispara", rule_name not in matched_neg, str(matched_neg))

# ---------------- HR-10: Actividad Archivos Usuario ----------------
rule_name = "Actividad Archivos Usuario"
threshold = int(cfg_of(rule_name)["threshold"])
analyzer = fresh_analyzer()
matched = []
for i in range(threshold):
    matched = analyzer.register_event(f"/home/usuario/Documents/archivo_{i}.txt", "file_modified")
check(f"HR-10: {threshold} operaciones en carpetas de usuario (Documents) -> dispara", rule_name in matched, str(matched))

analyzer_neg = fresh_analyzer()
matched_neg = analyzer_neg.register_event("/opt/app/data.bin", "file_modified")
check("HR-10: ruta fuera de carpetas de usuario -> no dispara", rule_name not in matched_neg, str(matched_neg))

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_file_rules_regression.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
