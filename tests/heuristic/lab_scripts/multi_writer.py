"""Proceso de laboratorio: UN solo proceso que escribe varios archivos
en secuencia dentro de 'directory', con el mismo handshake '.ready'/
'.go' por cada archivo -- para probar que la atribución ve el MISMO
PID en múltiples operaciones consecutivas del mismo proceso (Prueba B
de la especificación de atribución de procesos).

Uso: python multi_writer.py <directorio> <cantidad>
"""
import os
import sys
import time

directory = sys.argv[1]
count = int(sys.argv[2])

os.makedirs(directory, exist_ok=True)

for i in range(count):
    file_path = os.path.join(directory, f"op_{i}.txt")
    ready_marker = file_path + ".ready"
    go_marker = file_path + ".go"

    f = open(file_path, "w")
    f.write("laboratorio")
    f.flush()

    open(ready_marker, "w").close()

    deadline = time.time() + 30
    while not os.path.exists(go_marker) and time.time() < deadline:
        time.sleep(0.02)

    f.close()

    for marker in (ready_marker, go_marker):
        try:
            os.remove(marker)
        except OSError:
            pass
