from pathlib import Path
import time


# Antes de 2026-08-17 el agente vigilaba '.' completo, así que
# cualquier carpeta local (como la vieja 'test_files/') quedaba
# cubierta. Desde la monitorización global del endpoint (ver
# PENDIENTES.md, "Honeyfiles + monitorización completa del endpoint...")
# el agente vigila carpetas específicas -- se apunta acá a la carpeta
# de pruebas DOCUMENTS (agent/paths.py::get_monitored_roots(), modo
# development) para que este script siga generando actividad real
# dentro de lo que el agente efectivamente vigila.
TEST_DIRECTORY = Path(__file__).resolve().parent / "test_endpoint" / "Documents"


TEST_DIRECTORY.mkdir(
    exist_ok=True
)


print("Generando actividad de prueba...")

for i in range(25):

    file_path = TEST_DIRECTORY / f"test_{i}.txt"

    with open(file_path, "w") as file:

        file.write(
            f"Archivo de prueba {i}"
        )

    print(
        f"Creado: {file_path}"
    )

    time.sleep(0.1)


print()
print("Prueba terminada.")
