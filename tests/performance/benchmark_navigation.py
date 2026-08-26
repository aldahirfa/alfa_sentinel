"""Benchmark reproducible de las APIs usadas al navegar por ALFA-Sentinel.

No modifica datos. Inicia sesión y mide únicamente peticiones GET.

Ejemplos:
    python tests/performance/benchmark_navigation.py --username admin --password "..."
    python tests/performance/benchmark_navigation.py --base-url http://127.0.0.1:5173 --username admin --password "..."

También acepta ALFA_TEST_USER y ALFA_TEST_PASSWORD como variables de entorno.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


@dataclass(frozen=True)
class Target:
    name: str
    path: str
    group: str = "pantalla"


TARGETS = [
    Target("Dashboard / overview", "/api/dashboard/overview", "global"),
    Target("Dashboard / actividad 24 h", "/api/dashboard/activity-series?period=24h", "dashboard"),
    Target("Endpoints", "/api/endpoints?page=1&page_size=10"),
    Target("Alertas", "/api/alerts?view=activas&page=1&page_size=15"),
    Target("Incidentes", "/api/incidentes?view=activas&page=1"),
    Target("Honeyfiles", "/api/honeyfiles"),
    Target("Reglas heurísticas", "/api/rules"),
    Target("Acciones de respuesta", "/api/respuesta"),
    Target("Reportes", "/api/reportes?page=1"),
    Target("Administración / usuarios", "/api/users", "administracion"),
    Target("Administración / configuración", "/api/config/agentes", "administracion"),
    Target("Administración / auditoría", "/api/audit-logs?page=1", "administracion"),
    Target("Perfil", "/api/perfil"),
    Target("Alertas abiertas (poll 3 s)", "/alerts/open", "global"),
]


@dataclass
class Result:
    target: Target
    samples_ms: list[float]
    errors: list[str]

    @property
    def avg(self) -> float:
        return statistics.fmean(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def median(self) -> float:
        return statistics.median(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def minimum(self) -> float:
        return min(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def maximum(self) -> float:
        return max(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def p95(self) -> float:
        if not self.samples_ms:
            return float("nan")
        ordered = sorted(self.samples_ms)
        index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999)))
        return ordered[index]


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value


def request_json(opener, base_url: str, path: str, *, timeout: float) -> tuple[float, int]:
    url = urljoin(base_url + "/", path.lstrip("/"))
    req = Request(url, method="GET", headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    started = time.perf_counter()
    with opener.open(req, timeout=timeout) as response:
        response.read()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return elapsed_ms, response.status


def login(opener, base_url: str, username: str, password: str, *, timeout: float) -> float:
    url = urljoin(base_url + "/", "login")
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    started = time.perf_counter()
    with opener.open(req, timeout=timeout) as response:
        response.read()
        if response.status >= 400:
            raise RuntimeError(f"Login devolvió HTTP {response.status}")
    return (time.perf_counter() - started) * 1000.0


def classify(ms: float) -> str:
    # Clasificación de diagnóstico, no un requisito formal del proyecto.
    if ms <= 200:
        return "rápido"
    if ms <= 500:
        return "aceptable"
    if ms <= 1000:
        return "lento"
    return "muy lento"


def format_ms(value: float) -> str:
    if value != value:  # NaN
        return "—"
    return f"{value:8.1f}"


def run_target(opener, base_url: str, target: Target, *, warmup: int, runs: int, timeout: float) -> Result:
    errors: list[str] = []

    for _ in range(warmup):
        try:
            request_json(opener, base_url, target.path, timeout=timeout)
        except Exception:
            # El calentamiento no entra en las estadísticas; el error real
            # volverá a aparecer durante las rondas medidas.
            break

    samples: list[float] = []
    for _ in range(runs):
        try:
            elapsed_ms, status = request_json(opener, base_url, target.path, timeout=timeout)
            if not 200 <= status < 300:
                errors.append(f"HTTP {status}")
            else:
                samples.append(elapsed_ms)
        except HTTPError as exc:
            errors.append(f"HTTP {exc.code}")
        except URLError as exc:
            errors.append(f"red: {exc.reason}")
        except TimeoutError:
            errors.append("timeout")
        except Exception as exc:  # pragma: no cover - diagnóstico interactivo
            errors.append(f"{type(exc).__name__}: {exc}")

    return Result(target=target, samples_ms=samples, errors=errors)


def print_results(results: list[Result]) -> None:
    print()
    print("Latencia por endpoint (milisegundos)")
    print("-" * 113)
    print(f"{'Pantalla / consulta':38} {'mediana':>9} {'p95':>9} {'promedio':>9} {'mínimo':>9} {'máximo':>9}  {'diagnóstico':12}  errores")
    print("-" * 113)

    for result in results:
        diag = classify(result.p95) if result.samples_ms else "sin datos"
        errors = str(len(result.errors)) if result.errors else "0"
        print(
            f"{result.target.name[:38]:38} "
            f"{format_ms(result.median)} "
            f"{format_ms(result.p95)} "
            f"{format_ms(result.avg)} "
            f"{format_ms(result.minimum)} "
            f"{format_ms(result.maximum)}  "
            f"{diag:12}  {errors}"
        )

    print("-" * 113)

    admin = [r for r in results if r.target.group == "administracion" and r.samples_ms]
    if admin:
        # Administración lanza estas consultas al montar la página. Como el
        # navegador puede solaparlas, el endpoint individual más lento es
        # una mejor aproximación a la espera visible que sumar los tres.
        slowest = max(admin, key=lambda r: r.p95)
        print(
            "Administración: actualmente dispara usuarios, configuración y auditoría al entrar. "
            f"El más lento en p95 fue '{slowest.target.name}' ({slowest.p95:.1f} ms)."
        )

    slow = sorted((r for r in results if r.samples_ms), key=lambda r: r.p95, reverse=True)[:3]
    if slow:
        print("Cuellos de botella principales (por p95):")
        for result in slow:
            print(f"  - {result.target.name}: {result.p95:.1f} ms ({classify(result.p95)})")


def build_json_report(base_url: str, login_ms: float, results: list[Result], runs: int, warmup: int) -> dict:
    return {
        "base_url": base_url,
        "login_ms": round(login_ms, 3),
        "runs": runs,
        "warmup": warmup,
        "results": [
            {
                "name": r.target.name,
                "path": r.target.path,
                "group": r.target.group,
                "samples": len(r.samples_ms),
                "median_ms": None if not r.samples_ms else round(r.median, 3),
                "p95_ms": None if not r.samples_ms else round(r.p95, 3),
                "avg_ms": None if not r.samples_ms else round(r.avg, 3),
                "min_ms": None if not r.samples_ms else round(r.minimum, 3),
                "max_ms": None if not r.samples_ms else round(r.maximum, 3),
                "errors": r.errors,
            }
            for r in results
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mide la latencia de las APIs usadas durante la navegación de ALFA-Sentinel.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI (:8000) o Vite (:5173).")
    parser.add_argument("--username", default=os.getenv("ALFA_TEST_USER"), help="Usuario de consola. También ALFA_TEST_USER.")
    parser.add_argument("--password", default=os.getenv("ALFA_TEST_PASSWORD"), help="Contraseña. También ALFA_TEST_PASSWORD.")
    parser.add_argument("--runs", type=int, default=10, help="Muestras medidas por endpoint (default: 10).")
    parser.add_argument("--warmup", type=int, default=2, help="Peticiones de calentamiento no medidas (default: 2).")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout por petición en segundos.")
    parser.add_argument("--json-out", help="Ruta opcional donde guardar también el resultado en JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.username or not args.password:
        print("Faltan credenciales. Usa --username/--password o ALFA_TEST_USER/ALFA_TEST_PASSWORD.", file=sys.stderr)
        return 2
    if args.runs < 1 or args.warmup < 0:
        print("--runs debe ser >= 1 y --warmup >= 0.", file=sys.stderr)
        return 2

    base_url = normalize_base_url(args.base_url)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    print(f"Base: {base_url}")
    print(f"Muestras: {args.runs} medidas + {args.warmup} calentamiento por endpoint")

    try:
        login_ms = login(opener, base_url, args.username, args.password, timeout=args.timeout)
    except HTTPError as exc:
        print(f"No se pudo iniciar sesión: HTTP {exc.code}.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"No se pudo iniciar sesión: {exc}", file=sys.stderr)
        return 1

    print(f"Login: {login_ms:.1f} ms")

    results = [
        run_target(
            opener,
            base_url,
            target,
            warmup=args.warmup,
            runs=args.runs,
            timeout=args.timeout,
        )
        for target in TARGETS
    ]
    print_results(results)

    if args.json_out:
        report = build_json_report(base_url, login_ms, results, args.runs, args.warmup)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"Resultado JSON guardado en: {args.json_out}")

    return 0 if all(not result.errors for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
