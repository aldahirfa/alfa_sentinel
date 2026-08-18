"""HR-05 / HR-11 -- casos límite con datos SINTÉTICOS (process_info
armado a mano, sin procesos reales) -- complemento rápido y
determinístico de test_hr05_proceso_sospechoso.py y
test_hr11_actividad_repetitiva.py (que sí usan procesos de laboratorio
reales, más lentos por naturaleza al depender de subprocesos de SO).
Corre FileActivityAnalyzer directamente, sin servidor ni BD -- ideal
para correr en cada cambio de heuristic_engine.py sin esperar a que
arranquen procesos externos.

Ejecutar: python3 tests/heuristic/test_hr05_hr11_unit_synthetic.py
"""
import os
import sys

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))

from heuristic_engine import FileActivityAnalyzer

results = []


def check(name, condition):
    results.append((name, condition))
    print(("PASS" if condition else "FAIL"), "-", name)


# ---- HR-05: Proceso Sospechoso ----

# Caso 1: proceso normal (ruta estándar) -> no dispara
a = FileActivityAnalyzer.from_policy([
    {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
])
matched = a.register_event(
    "C:/Users/user/Documents/informe.docx", "file_modified",
    process_info={"process_id": 100, "process_name": "winword.exe", "executable_path": "C:/Program Files/Microsoft Office/winword.exe"},
)
check("HR-05 proceso normal (Program Files) no dispara", "Proceso Sospechoso" not in matched)

# Caso 2: proceso sospechoso (ruta temporal) -> dispara con threshold=1
a2 = FileActivityAnalyzer.from_policy([
    {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
])
matched2 = a2.register_event(
    "C:/Users/user/Documents/informe.docx", "file_modified",
    process_info={"process_id": 200, "process_name": "raro.exe", "executable_path": "C:/Users/user/AppData/Local/Temp/raro.exe"},
)
check("HR-05 proceso sospechoso (Temp) dispara", "Proceso Sospechoso" in matched2)

# Caso 3: proceso sospechoso + actividad de archivos simultánea (ambas reglas coexisten)
a3 = FileActivityAnalyzer.from_policy([
    {"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30},
    {"name": "Modificacion Masiva Archivos", "threshold": 2, "window_seconds": 10},
])
a3.register_event("C:/Users/user/a.txt", "file_modified", process_info={"process_id": 300, "process_name": "raro.exe", "executable_path": "C:/Users/user/AppData/Local/Temp/raro.exe"})
matched3 = a3.register_event("C:/Users/user/b.txt", "file_modified", process_info={"process_id": 300, "process_name": "raro.exe", "executable_path": "C:/Users/user/AppData/Local/Temp/raro.exe"})
check("HR-05+HR-01 combinadas: ambas reglas coinciden", "Proceso Sospechoso" in matched3 and "Modificacion Masiva Archivos" in matched3)

# Caso: process_info None -> HR-05 no evalúa nada (no se cuenta como "no sospechoso")
a4 = FileActivityAnalyzer.from_policy([{"name": "Proceso Sospechoso", "threshold": 1, "window_seconds": 30}])
matched4 = a4.register_event("C:/x.txt", "file_modified", process_info=None)
check("HR-05 sin process_info no dispara ni rompe", "Proceso Sospechoso" not in matched4)

# Caso: HR-05 no está en la política efectiva (desactivada) -> no evalúa aunque el proceso sea sospechoso
a5 = FileActivityAnalyzer.from_policy([])  # lista vacía real del servidor, no None
matched5 = a5.register_event("C:/x.txt", "file_modified", process_info={"process_id": 1, "process_name": "raro.exe", "executable_path": "C:/Temp/raro.exe"})
check("HR-05 fuera de policy_rules (desactivada) no dispara", "Proceso Sospechoso" not in matched5)
check("policy_rules=[] no rellena con DEFAULT_RULES (self.rules vacío)", a5.rules == {})


# ---- HR-11: Actividad Repetitiva Automatizada ----

# Caso 1: mismo PID, operaciones alcanzan el umbral -> dispara
a6 = FileActivityAnalyzer.from_policy([{"name": "Actividad Repetitiva Automatizada", "threshold": 3, "window_seconds": 15}])
pid = 500
m = []
for i in range(3):
    m = a6.register_event(f"C:/f{i}.txt", "file_modified", process_info={"process_id": pid, "process_name": "script.exe", "executable_path": "C:/x/script.exe"})
check("HR-11 mismo PID alcanza umbral exacto -> dispara", "Actividad Repetitiva Automatizada" in m)

# Caso 2: threshold-1 (una operación menos que el umbral) -> NO dispara
a7 = FileActivityAnalyzer.from_policy([{"name": "Actividad Repetitiva Automatizada", "threshold": 3, "window_seconds": 15}])
m7 = []
for i in range(2):
    m7 = a7.register_event(f"C:/f{i}.txt", "file_modified", process_info={"process_id": 501, "process_name": "script.exe", "executable_path": "C:/x/script.exe"})
check("HR-11 threshold-1 no dispara", "Actividad Repetitiva Automatizada" not in m7)

# Caso 3: procesos DISTINTOS, cada uno por debajo del umbral individualmente -> ninguno dispara
a8 = FileActivityAnalyzer.from_policy([{"name": "Actividad Repetitiva Automatizada", "threshold": 3, "window_seconds": 15}])
any_matched = False
for i in range(3):
    m8 = a8.register_event(f"C:/f{i}.txt", "file_modified", process_info={"process_id": 600 + i, "process_name": "x.exe", "executable_path": "C:/x/x.exe"})
    if "Actividad Repetitiva Automatizada" in m8:
        any_matched = True
check("HR-11 procesos distintos (1 op c/u) no dispara -- no se confunde con HR-01/04 (endpoint-wide)", not any_matched)

# Caso 4: ventana vencida -- eventos viejos se podan, no cuentan
import heuristic_engine as he
a9 = FileActivityAnalyzer.from_policy([{"name": "Actividad Repetitiva Automatizada", "threshold": 3, "window_seconds": 15}])
# Simula 2 eventos "viejos" insertando directamente en el deque con timestamp fuera de ventana
old_ts = he.time() - 100
a9._process_activity[700] = he.deque([old_ts, old_ts])
m9 = a9.register_event("C:/f.txt", "file_modified", process_info={"process_id": 700, "process_name": "x.exe", "executable_path": "C:/x/x.exe"})
check("HR-11 ventana vencida: eventos viejos podados, 1 evento nuevo no alcanza umbral", "Actividad Repetitiva Automatizada" not in m9)


ok = all(c for _, c in results)
print()
print(f"{sum(1 for _, c in results if c)}/{len(results)} pruebas OK (test_hr05_hr11_unit_synthetic.py)")
sys.exit(0 if ok else 1)
