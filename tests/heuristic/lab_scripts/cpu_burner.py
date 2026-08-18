"""Proceso de laboratorio: ocupa un núcleo de CPU al ~100% durante
'duration_seconds' -- carga real medida por psutil como la de
cualquier proceso, nada simulado. Usado para probar HR-06 (Consumo CPU
Elevado) con un proceso de verdad en vez de solo muestras sintéticas.

Uso: python cpu_burner.py <duration_seconds>
"""
import sys
import time

duration_seconds = float(sys.argv[1])
end = time.time() + duration_seconds
x = 0
while time.time() < end:
    x += 1
