from pathlib import Path
import time


TEST_DIRECTORY = Path("test_files")


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
