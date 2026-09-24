#!/usr/bin/env python3
"""Benchmark de huella de recursos (CPU/RAM) del agente ALFA-Sentinel.

Este script NO reemplaza a benchmark_navigation.py (ese mide latencia de
APIs). Este mide si el propio AGENTE que se instala en cada endpoint es
"ligero": cuánta CPU y memoria consume mientras vigila archivos señuelo y
procesos, tanto en reposo como durante un ataque simulado, para poder
optimizarlo ANTES de desplegarlo masivamente en equipos reales.

No necesita el backend ni la base de datos levantados: se conecta al
proceso del agente por PID (o por coincidencia de línea de comandos) y
lo muestrea desde fuera con psutil, igual que se vigilaría cualquier
proceso en un Task Manager / htop, así que puede correr en paralelo a
una ejecución normal del agente.

Uso típico (en una máquina, con el agente ya corriendo en otra terminal):

    python agent/main.py --server http://127.0.0.1:8000
    # en otra terminal:
    python tests/performance/benchmark_agent_footprint.py \
        --phases "reposo:60,carga:120,reposo:60" \
        --json-out rendimiento_agente.json

Durante la fase "carga" el script avisa en pantalla cuándo lanzar, en una
tercera terminal, el simulador seguro de comportamientos tipo ransomware
(tools/simulator/alfa_ransomware_simulator.py) apuntando a una carpeta que
el agente esté vigilando.

Ver README_agente.md en esta misma carpeta para más contexto.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    print("Este benchmark requiere 'psutil' (ya es dependencia del agente, ver agent/requirements.txt).")
    print("Instálalo con: pip install psutil")
    raise SystemExit(1)


DEFAULT_PHASES = "reposo:60,carga:120,reposo:60"
DEFAULT_MATCH = "main.py"  # coincide con `python agent/main.py ...`

# Umbrales SOLO diagnósticos para clasificar si el agente se comporta
# como "ligero" en el equipo donde corre este benchmark -- no son un
# requisito formal del proyecto, igual que en benchmark_navigation.py.
# cpu_percent de psutil es relativo a UN núcleo (100% = 1 core lleno).
CPU_LIGERO = 3.0
CPU_ACEPTABLE = 8.0
RSS_LIGERO_MB = 80.0
RSS_ACEPTABLE_MB = 200.0


def classify(value: float, ligero: float, aceptable: float) -> str:
    if value <= ligero:
        return "ligero"
    if value <= aceptable:
        return "aceptable"
    return "pesado"


@dataclass
class Sample:
    t_rel_s: float
    phase: str
    cpu_percent: float
    cpu_percent_norm: float
    rss_mb: float
    vms_mb: float
    num_threads: int
    open_files: int
    io_read_mb: Optional[float]
    io_write_mb: Optional[float]


def find_agent_pid(match: str) -> Optional[int]:
    candidates = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if match.lower() in cmdline.lower():
            candidates.append((proc.info["pid"], cmdline))
    if not candidates:
        return None
    if len(candidates) > 1:
        print(f"Aviso: {len(candidates)} procesos coinciden con '{match}', se usa el primero:")
        for pid, cmdline in candidates:
            print(f"  PID {pid}: {cmdline}")
    return candidates[0][0]


def parse_phases(spec: str) -> list[tuple[str, float]]:
    phases = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, secs = chunk.partition(":")
        if not secs:
            raise ValueError(f"Fase mal formada (esperado nombre:segundos): '{chunk}'")
        phases.append((name.strip(), float(secs)))
    if not phases:
        raise ValueError("--phases no puede quedar vacío")
    return phases


def phase_hint(name: str) -> Optional[str]:
    lowered = name.lower()
    if any(word in lowered for word in ("carga", "ataque", "simul", "load", "attack")):
        return (
            "  >>> Lanza AHORA, en otra terminal, el simulador seguro de ransomware "
            "(tools/simulator/alfa_ransomware_simulator.py) contra una carpeta vigilada por el agente."
        )
    if any(word in lowered for word in ("reposo", "idle", "baseline")):
        return "  >>> No generes actividad manual: esta fase mide el agente en reposo."
    return None


def sample_process(proc: psutil.Process, cpu_count: int) -> Optional[dict]:
    try:
        with proc.oneshot():
            cpu = proc.cpu_percent(interval=None)
            mem = proc.memory_info()
            threads = proc.num_threads()
            try:
                open_files = len(proc.open_files())
            except (psutil.AccessDenied, NotImplementedError, OSError):
                open_files = -1
            io_read_mb = io_write_mb = None
            try:
                io = proc.io_counters()
                io_read_mb = io.read_bytes / (1024 * 1024)
                io_write_mb = io.write_bytes / (1024 * 1024)
            except (psutil.AccessDenied, NotImplementedError, AttributeError):
                pass
        return {
            "cpu_percent": cpu,
            "cpu_percent_norm": cpu / cpu_count if cpu_count else cpu,
            "rss_mb": mem.rss / (1024 * 1024),
            "vms_mb": mem.vms / (1024 * 1024),
            "num_threads": threads,
            "open_files": open_files,
            "io_read_mb": io_read_mb,
            "io_write_mb": io_write_mb,
        }
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def summarize(samples: list[Sample]) -> dict:
    if not samples:
        return {"samples": 0}
    cpu = [s.cpu_percent for s in samples]
    cpu_norm = [s.cpu_percent_norm for s in samples]
    rss = [s.rss_mb for s in samples]
    io_reads = [s.io_read_mb for s in samples if s.io_read_mb is not None]
    io_writes = [s.io_write_mb for s in samples if s.io_write_mb is not None]

    def p95(values: list[float]) -> float:
        ordered = sorted(values)
        idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999)))
        return ordered[idx]

    summary = {
        "samples": len(samples),
        "duration_s": round(samples[-1].t_rel_s - samples[0].t_rel_s, 1),
        "cpu_percent_avg": round(statistics.fmean(cpu), 3),
        "cpu_percent_median": round(statistics.median(cpu), 3),
        "cpu_percent_p95": round(p95(cpu), 3),
        "cpu_percent_max": round(max(cpu), 3),
        "cpu_percent_norm_avg": round(statistics.fmean(cpu_norm), 3),
        "rss_mb_avg": round(statistics.fmean(rss), 3),
        "rss_mb_max": round(max(rss), 3),
        "threads_max": max(s.num_threads for s in samples),
    }
    if io_reads and io_writes:
        summary["io_read_mb_delta"] = round(io_reads[-1] - io_reads[0], 3)
        summary["io_write_mb_delta"] = round(io_writes[-1] - io_writes[0], 3)
    summary["clasificacion_cpu"] = classify(summary["cpu_percent_avg"], CPU_LIGERO, CPU_ACEPTABLE)
    summary["clasificacion_rss"] = classify(summary["rss_mb_avg"], RSS_LIGERO_MB, RSS_ACEPTABLE_MB)
    return summary


def run(args: argparse.Namespace) -> int:
    pid = args.pid
    if pid is None:
        pid = find_agent_pid(args.match)
        if pid is None:
            print(f"No se encontró ningún proceso cuya línea de comandos contenga '{args.match}'.")
            print("Arranca el agente primero (python agent/main.py ...) o pasa --pid <PID> explícitamente.")
            return 1

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"No existe ningún proceso con PID {pid}.")
        return 1

    try:
        cmdline = " ".join(proc.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        cmdline = "(no disponible)"

    cpu_count = psutil.cpu_count(logical=True) or 1
    phases = parse_phases(args.phases)
    total_duration = sum(secs for _, secs in phases)

    print(f"Vigilando PID {pid} ({cmdline})")
    print(f"Núcleos lógicos detectados: {cpu_count} (cpu_percent es relativo a 1 núcleo)")
    print(f"Plan: {', '.join(f'{n} {s:.0f}s' for n, s in phases)} -- total {total_duration:.0f}s")
    print()

    # Llamada de calentamiento: la primera lectura de cpu_percent(interval=None)
    # no es representativa (psutil la usa como punto de referencia).
    proc.cpu_percent(interval=None)
    time.sleep(min(1.0, args.interval))

    all_samples: list[Sample] = []
    by_phase: dict[str, list[Sample]] = {}
    start = time.monotonic()

    try:
        for phase_name, phase_secs in phases:
            hint = phase_hint(phase_name)
            print(f"=== Fase '{phase_name}' ({phase_secs:.0f}s) ===")
            if hint:
                print(hint)
            phase_end = time.monotonic() + phase_secs
            phase_samples: list[Sample] = []
            while time.monotonic() < phase_end:
                metrics = sample_process(proc, cpu_count)
                if metrics is None:
                    print("El proceso vigilado terminó antes de lo previsto. Cortando el benchmark aquí.")
                    raise KeyboardInterrupt
                sample = Sample(t_rel_s=round(time.monotonic() - start, 2), phase=phase_name, **metrics)
                phase_samples.append(sample)
                all_samples.append(sample)
                time.sleep(args.interval)
            by_phase[phase_name] = by_phase.get(phase_name, []) + phase_samples
            phase_summary = summarize(phase_samples)
            print(
                f"  CPU avg {phase_summary.get('cpu_percent_avg', float('nan')):.2f}% "
                f"(p95 {phase_summary.get('cpu_percent_p95', float('nan')):.2f}%, "
                f"max {phase_summary.get('cpu_percent_max', float('nan')):.2f}%) "
                f"| RSS avg {phase_summary.get('rss_mb_avg', float('nan')):.1f} MB "
                f"(max {phase_summary.get('rss_mb_max', float('nan')):.1f} MB) "
                f"| hilos max {phase_summary.get('threads_max', '?')} "
                f"-> CPU: {phase_summary.get('clasificacion_cpu', '?')}, RAM: {phase_summary.get('clasificacion_rss', '?')}"
            )
            print()
    except KeyboardInterrupt:
        print("Interrumpido por el usuario -- se guarda lo muestreado hasta ahora.")

    overall_summary = summarize(all_samples)
    per_phase_summary = {name: summarize(samples) for name, samples in by_phase.items()}

    print("=== Resumen general ===")
    print(json.dumps(overall_summary, indent=2, ensure_ascii=False))

    if args.json_out:
        payload = {
            "pid": pid,
            "cmdline": cmdline,
            "cpu_count_logical": cpu_count,
            "interval_s": args.interval,
            "phases_plan": [{"name": n, "seconds": s} for n, s in phases],
            "overall": overall_summary,
            "per_phase": per_phase_summary,
            "samples": [asdict(s) for s in all_samples],
            "umbrales_diagnosticos": {
                "cpu_percent_ligero": CPU_LIGERO,
                "cpu_percent_aceptable": CPU_ACEPTABLE,
                "rss_mb_ligero": RSS_LIGERO_MB,
                "rss_mb_aceptable": RSS_ACEPTABLE_MB,
            },
        }
        out_path = Path(args.json_out)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nResultados guardados en {out_path}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark de huella de recursos del agente ALFA-Sentinel")
    parser.add_argument("--pid", type=int, default=None, help="PID del proceso del agente a vigilar")
    parser.add_argument(
        "--match",
        default=DEFAULT_MATCH,
        help=f"Texto a buscar en la línea de comandos para localizar el PID automáticamente (default: '{DEFAULT_MATCH}')",
    )
    parser.add_argument(
        "--phases",
        default=DEFAULT_PHASES,
        help=(
            "Lista 'nombre:segundos' separada por comas. Las fases con 'carga'/'ataque'/'simul' en el "
            f"nombre muestran un aviso para lanzar el simulador. Default: '{DEFAULT_PHASES}'"
        ),
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Segundos entre muestras (default: 1.0)")
    parser.add_argument("--json-out", default=None, help="Ruta para guardar los resultados en JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
