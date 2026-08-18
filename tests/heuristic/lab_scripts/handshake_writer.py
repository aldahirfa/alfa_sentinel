"""Proceso de laboratorio: abre un único archivo, lo mantiene abierto
hasta recibir la señal 'go' del proceso de prueba, y recién ahí lo
cierra. No es una simulación de datos -- es un proceso Python real con
un PID real y un archivo realmente abierto; el handshake con archivos
'.ready'/'.go' existe solo para que la prueba sepa CUÁNDO consultar la
atribución sin depender de sleeps adivinados (que en un entorno
compartido pueden fallar por lentitud puntual del sistema).

Uso: python handshake_writer.py <ruta_archivo>
"""
import os
import sys
import time

file_path = sys.argv[1]
ready_marker = file_path + ".ready"
go_marker = file_path + ".go"

f = open(file_path, "w")
f.write("laboratorio ALFA-Sentinel")
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
