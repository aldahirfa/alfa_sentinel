# Prueba de rendimiento del agente (huella de CPU / RAM)

Esta prueba responde a la pregunta "¿el agente es ligero, o va a causar
problemas de rendimiento en los equipos donde se instale?". A diferencia
de `benchmark_navigation.py` (que mide la velocidad de la consola web),
`benchmark_agent_footprint.py` mide el propio proceso `agent/main.py`:
cuánta CPU y memoria consume mientras vigila archivos señuelo, carpetas
del usuario y procesos, tanto en reposo como durante un ataque simulado.

## 1. Cómo funciona

No necesita el backend ni la base de datos levantados para medir -- solo
necesita que el agente ya esté ejecutándose. El script se engancha al
proceso por PID (o lo busca automáticamente por texto en su línea de
comandos) y lo muestrea desde fuera con `psutil`, igual que lo haría un
Administrador de tareas / htop, sin tocar el código del agente.

## 2. Preparación

En una terminal, arranca el agente normalmente (idealmente con el
backend levantado y el agente ya enrolado, para medir el escenario real):

```bash
cd agent
python main.py --server http://127.0.0.1:8000
```

En otra terminal, desde la raíz del repositorio:

```bash
python tests/performance/benchmark_agent_footprint.py --json-out rendimiento_agente.json
```

Por defecto busca un proceso cuya línea de comandos contenga `main.py`;
si hay ambigüedad o no lo encuentra, pásale el PID directamente:

```bash
python tests/performance/benchmark_agent_footprint.py --pid 12345 --json-out rendimiento_agente.json
```

## 3. Fases: reposo vs. carga

Por defecto corre 3 fases: `reposo` (60s) -> `carga` (120s) -> `reposo`
(60s). Al entrar en una fase de "carga" el script imprime un aviso para
que, en una TERCERA terminal, lances el simulador seguro:

```bash
python tools/simulator/alfa_ransomware_simulator.py
```

y marques ahí las reglas HR-01..HR-12 que quieras disparar contra una
carpeta que el agente esté vigilando. Así se compara el consumo del
agente cuando no pasa nada frente a cuando está procesando actividad
sospechosa real.

Puedes cambiar la duración y el número de fases:

```bash
python tests/performance/benchmark_agent_footprint.py \
    --phases "reposo:120,carga:180,reposo:60" --interval 0.5 \
    --json-out rendimiento_agente.json
```

## 4. Qué mide cada muestra

- `cpu_percent`: % de UN núcleo (100% = 1 core lleno; psutil no lo topa
  en 100 aunque el proceso reparta hilos entre varios núcleos).
- `cpu_percent_norm`: el mismo valor dividido entre el número de núcleos
  lógicos de la máquina (más comparable entre equipos distintos).
- `rss_mb` / `vms_mb`: memoria residente / virtual.
- `num_threads`, `open_files`, `io_read_mb` / `io_write_mb` (delta
  acumulado de E/S de disco desde el inicio del muestreo).

## 5. Cómo interpretar los resultados

La clasificación que imprime el script (ligero / aceptable / pesado) es
SOLO diagnóstica, con umbrales por defecto pensados para un agente que
debe convivir con el uso normal de un equipo de oficina (no un servidor
dedicado):

- CPU promedio: ligero ≤ 3 %, aceptable ≤ 8 %, pesado > 8 % (de un núcleo).
- RAM promedio: ligero ≤ 80 MB, aceptable ≤ 200 MB, pesado > 200 MB.

Puedes ajustarlos directamente en las constantes `CPU_LIGERO`,
`CPU_ACEPTABLE`, `RSS_LIGERO_MB`, `RSS_ACEPTABLE_MB` al principio del
script si tu criterio de "equipo típico" es distinto.

Para decidir qué optimizar:

- Si el promedio en **reposo** ya es alto, el agente está haciendo
  trabajo innecesario todo el tiempo (revisar primero la frecuencia de
  sondeo en `file_monitor.py`, `honeyfile_sync.py` e `isolation_sync.py`,
  y el intervalo de `heartbeat.py`).
- Si el reposo es bajo pero el pico en **carga** es muy alto y sostenido
  (no solo un par de segundos), el cuello de botella probablemente está
  en `heuristic_engine.py` al procesar ráfagas de eventos.
- Vigila también `num_threads` y `open_files` a lo largo del tiempo: si
  crecen sin parar en vez de estabilizarse, es señal de fuga de
  hilos/descriptores -- más preocupante a largo plazo que un pico
  puntual de CPU o RAM.

## 6. Importante: valida en el equipo real de destino

El script corre igual en Windows y Linux (usa `psutil`), pero el
comportamiento del agente sí depende de la plataforma: en Windows puede
usar el adaptador ETW (`agent/adapters/windows_etw.py`) para atribución
de procesos, con una sobrecarga distinta a la del adaptador de fanotify
en Linux (`agent/adapters/linux_fanotify.py`). Para tener una cifra
confiable de "cuánto va a pesar esto en los equipos donde lo vamos a
instalar", corre este benchmark en una máquina Windows representativa
del parque real (misma versión de Windows, antivirus/EDR corporativo
activo si lo hay), no solo en el equipo de desarrollo.
