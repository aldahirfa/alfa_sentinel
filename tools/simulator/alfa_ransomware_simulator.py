#!/usr/bin/env python3
"""
ALFA-Sentinel | Simulador seguro de comportamientos tipo ransomware
====================================================================

Este programa NO ES RANSOMWARE. No cifra archivos reales, no exfiltra datos,
no crea persistencia ni se propaga por red. Todo lo que hace ocurre dentro de
una carpeta de laboratorio aislada (LAB_ROOT), creada y destruida por el propio
programa. Su único propósito es generar, de forma controlada y reproducible,
los PATRONES DE COMPORTAMIENTO que un sistema de detección heurística debería
reconocer (modificación masiva, renombrado anómalo, escritura intensiva,
consumo de CPU, borrado masivo, etc.), para poder validar reglas de detección
propias en un entorno de pruebas.

Funciona igual en Windows y en Ubuntu (usa tkinter + pathlib + subprocess,
todos multiplataforma). En Ubuntu puede requerir instalar el paquete del
sistema para Tk:  sudo apt install python3-tk

Flujo de uso:
    1. Se introduce la clave de laboratorio (visible para todo el equipo,
       ver DEMO_KEY / botón "Mostrar clave") para "desbloquear" la interfaz,
       replicando la UX de una nota de rescate sin ocultar nada al equipo
       de pruebas.
    2. Se marcan una o más reglas (HR-01 .. HR-12) en la lista.
    3. Se pulsa "OK - Ejecutar seleccionadas".
    4. El programa ejecuta, en orden, las acciones asociadas a cada regla
       marcada, deja un registro en pantalla y un reporte de ejecución en
       LAB_ROOT/reports/, para poder correlacionar después contra las
       alertas que genere el sistema de detección.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# ---------------------------------------------------------------------------
# Configuración del laboratorio seguro
# ---------------------------------------------------------------------------
DEMO_KEY = "ALFA-2026"
LAB_ROOT = Path.home() / "ALFA_RANSOMWARE_LAB"
WORK_ROOT = LAB_ROOT / "work"
REPORTS_ROOT = LAB_ROOT / "reports"
LOG_FILE = LAB_ROOT / "execution_log.txt"
HONEYFILE = LAB_ROOT / "HONEYFILE_Documento_Confidencial.txt"
RANSOM_NOTE = LAB_ROOT / "README_RESCATE_SIMULADO.txt"

# Cada regla apunta al nombre de un método de App que la ejecuta.
# HR-12 no tiene acción propia: es una correlación que calcula el servidor
# de detección a partir de que 2+ reglas se disparen juntas, así que aquí
# solo se valida que, si se marca, haya al menos otras dos reglas marcadas.
RULES = [
    ("HR-01", "Modificación masiva", "20+ archivos modificados / 10 s", "mod_mass"),
    ("HR-02", "Renombrado anómalo", "5+ renombrados / 15 s", "rename"),
    ("HR-03", "Acceso honeyfile", "1 interacción", "honeyfile"),
    ("HR-04", "Escritura intensiva", "50+ escrituras / 10 s", "write_intensive"),
    ("HR-05", "Proceso sospechoso", "ruta/contexto atípico", "suspicious"),
    ("HR-06", "CPU elevado", "80%+ durante ~10 s", "cpu"),
    ("HR-07", "Recursos compartidos", "20+ ops / 15 s", "shared"),
    ("HR-08", "Temporales masivos", "30+ archivos / 15 s", "tempfiles"),
    ("HR-09", "Eliminación anómala", "20+ archivos / 15 s", "delete"),
    ("HR-10", "Actividad archivos usuario", "30+ ops / 20 s", "user_activity"),
    ("HR-11", "Actividad repetitiva", "40+ ops mismo proceso", "repetitive"),
    ("HR-12", "Correlación múltiple", "2+ reglas; la calcula el servidor", None),
]


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("ALFA-Sentinel | Simulador seguro de ransomware")
        root.geometry("960x780")
        root.minsize(860, 680)
        self.unlocked = False
        self.running = False
        self.key = tk.StringVar()
        self.status = tk.StringVar(value="Bloqueado. Introduce la clave.")
        self.progress = tk.DoubleVar(value=0)
        self.rule_vars: dict[str, tk.BooleanVar] = {}
        self.actionable_widgets: list[tk.Widget] = []
        self.build()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def build(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="ALFA-Sentinel", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Simulador seguro de comportamientos asociados a ransomware").pack(anchor="w", pady=(0, 10))

        safe = ttk.LabelFrame(main, text="Laboratorio aislado", padding=10)
        safe.pack(fill="x", pady=(0, 10))
        ttk.Label(safe, text=(
            f"Solo se modifica esta carpeta:\n{LAB_ROOT}\n\n"
            "No cifra, elimina ni modifica archivos fuera del laboratorio. "
            "No crea persistencia ni propagación de red."
        ), wraplength=890).pack(anchor="w")

        auth = ttk.LabelFrame(main, text="Clave de laboratorio", padding=10)
        auth.pack(fill="x", pady=(0, 10))
        row = ttk.Frame(auth)
        row.pack(fill="x")
        ttk.Label(row, text="Clave:").pack(side="left")
        ent = ttk.Entry(row, textvariable=self.key, show="*", width=28)
        ent.pack(side="left", padx=8)
        ent.bind("<Return>", lambda _e: self.unlock())
        ttk.Button(row, text="Desbloquear", command=self.unlock).pack(side="left")
        ttk.Button(row, text="Mostrar clave", command=self.show_key).pack(side="left", padx=8)
        ttk.Label(
            auth,
            text=f"La clave es conocida por todo el equipo de pruebas: {DEMO_KEY}",
            foreground="#555555",
        ).pack(anchor="w", pady=(6, 0))

        # ---- Selección de reglas -------------------------------------------------
        frame = ttk.LabelFrame(main, text="Selecciona una o más reglas a probar (HR-01 .. HR-12)", padding=10)
        frame.pack(fill="both", expand=True)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 6))
        b_all = ttk.Button(toolbar, text="Seleccionar todo", command=self.select_all, state="disabled")
        b_none = ttk.Button(toolbar, text="Ninguna", command=self.select_none, state="disabled")
        b_all.pack(side="left")
        b_none.pack(side="left", padx=6)
        self.actionable_widgets += [b_all, b_none]

        canvas = tk.Canvas(frame, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for i, (code, name, threshold, _fn) in enumerate(RULES):
            var = tk.BooleanVar(value=False)
            self.rule_vars[code] = var
            cb = ttk.Checkbutton(inner, variable=var, state="disabled")
            cb.grid(row=i, column=0, padx=(5, 0), pady=4, sticky="w")
            self.actionable_widgets.append(cb)
            ttk.Label(inner, text=code, width=8, font=("Segoe UI", 10, "bold")).grid(row=i, column=1, padx=5, sticky="w")
            ttk.Label(inner, text=name, width=26).grid(row=i, column=2, padx=5, sticky="w")
            ttk.Label(inner, text=threshold, foreground="#666666").grid(row=i, column=3, padx=5, sticky="w")
        inner.columnconfigure(3, weight=1)

        # ---- Botón principal OK + utilidades --------------------------------------
        run_row = ttk.Frame(main)
        run_row.pack(fill="x", pady=(10, 4))
        self.ok_button = ttk.Button(run_row, text="OK  ▶  Ejecutar seleccionadas", command=self.run_selected, state="disabled")
        self.ok_button.pack(side="left")
        self.actionable_widgets.append(self.ok_button)

        cleanup_btn = ttk.Button(run_row, text="Limpiar laboratorio", command=self.cleanup, state="disabled")
        cleanup_btn.pack(side="right")
        self.actionable_widgets.append(cleanup_btn)

        ttk.Label(main, textvariable=self.status).pack(anchor="w", pady=(8, 3))
        ttk.Progressbar(main, maximum=100, variable=self.progress).pack(fill="x")

        # ---- Registro de ejecución -------------------------------------------------
        log_frame = ttk.LabelFrame(main, text="Registro de ejecución", padding=6)
        log_frame.pack(fill="both", expand=False, pady=(10, 0))
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Autenticación / desbloqueo
    # ------------------------------------------------------------------
    def show_key(self):
        messagebox.showinfo("Clave", f"Clave de laboratorio:\n\n{DEMO_KEY}")

    def unlock(self):
        if self.key.get() != DEMO_KEY:
            self.status.set("Clave incorrecta.")
            messagebox.showerror("Acceso denegado", "Clave incorrecta.")
            return
        self.unlocked = True
        self.prepare_lab()
        for w in self.actionable_widgets:
            w.configure(state="normal")
        self.status.set(f"Desbloqueado. Laboratorio: {LAB_ROOT}")
        messagebox.showinfo("Listo", f"Clave aceptada.\n\nLaboratorio seguro:\n{LAB_ROOT}")

    # ------------------------------------------------------------------
    # Selección de reglas
    # ------------------------------------------------------------------
    def select_all(self):
        for var in self.rule_vars.values():
            var.set(True)

    def select_none(self):
        for var in self.rule_vars.values():
            var.set(False)

    def selected_codes(self) -> list[str]:
        return [code for code, var in self.rule_vars.items() if var.get()]

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------
    def guard(self) -> bool:
        if not self.unlocked:
            messagebox.showwarning("Bloqueado", "Primero introduce la clave.")
            return False
        if self.running:
            messagebox.showwarning("En ejecución", "Espera a que termine la prueba actual.")
            return False
        return True

    def prepare_lab(self):
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
        (LAB_ROOT / ".ALFA_SAFE_LAB").write_text("safe test lab\n", encoding="utf-8")
        if not HONEYFILE.exists():
            HONEYFILE.write_text("HONEYFILE DE PRUEBA - SIN INFORMACIÓN REAL\n", encoding="utf-8")

    def run_selected(self):
        if not self.guard():
            return
        codes = self.selected_codes()
        if not codes:
            messagebox.showwarning("Sin selección", "Marca al menos una regla antes de pulsar OK.")
            return
        non_correlation = [c for c in codes if c != "HR-12"]
        if "HR-12" in codes and len(non_correlation) < 2:
            messagebox.showwarning(
                "HR-12 requiere combinación",
                "HR-12 (Correlación múltiple) la calcula el servidor de detección a partir de "
                "que 2 o más reglas se disparen juntas. Marca al menos otras dos reglas además "
                "de HR-12 antes de ejecutar.",
            )
            return

        self.prepare_lab()
        self.progress.set(0)
        self.running = True
        for w in self.actionable_widgets:
            w.configure(state="disabled")
        threading.Thread(target=self._run_thread, args=(codes,), daemon=True).start()

    def _run_thread(self, codes: list[str]):
        by_code = {c: (name, threshold, fn) for c, name, threshold, fn in RULES}
        results = []
        start = datetime.now()
        self.log(f"=== Inicio de ejecución — reglas seleccionadas: {', '.join(codes)} ===")
        total = len([c for c in codes if by_code[c][2]])
        done = 0
        try:
            for code in codes:
                name, threshold, fn_name = by_code[code]
                if fn_name is None:
                    self.log(f"{code} ({name}): sin acción directa — se evalúa por correlación del resto de reglas ejecutadas.")
                    results.append((code, name, "correlación (sin acción propia)"))
                    continue
                self.root.after(0, lambda c=code, n=name: self.status.set(f"Ejecutando {c} — {n}..."))
                self.log(f"{code} ({name}): iniciando — umbral esperado: {threshold}")
                t0 = time.time()
                try:
                    getattr(self, fn_name)()
                    elapsed = time.time() - t0
                    self.log(f"{code} ({name}): completado en {elapsed:.1f} s")
                    results.append((code, name, f"ok ({elapsed:.1f}s)"))
                except Exception as e:
                    self.log(f"{code} ({name}): ERROR — {e}")
                    results.append((code, name, f"error: {e}"))
                done += 1
                self.progress.set(done / max(total, 1) * 100)

            self.write_run_report(codes, results, start)
            self.root.after(0, lambda: self.status.set(
                "Ejecución finalizada. Revisa eventos, alertas, riesgo e incidentes en tu sistema de detección."
            ))
            self.log("=== Fin de ejecución ===\n")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.status.set("La ejecución terminó con error."))
        finally:
            self.running = False
            self.root.after(0, lambda: self.progress.set(100))
            self.root.after(0, self._enable)

    def _enable(self):
        for w in self.actionable_widgets:
            w.configure(state="normal" if self.unlocked else "disabled")

    # ------------------------------------------------------------------
    # Registro / reportes
    # ------------------------------------------------------------------
    def log(self, msg: str):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, append)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def write_run_report(self, codes: list[str], results: list[tuple[str, str, str]], start: datetime):
        end = datetime.now()
        report = {
            "inicio": start.isoformat(timespec="seconds"),
            "fin": end.isoformat(timespec="seconds"),
            "duracion_s": round((end - start).total_seconds(), 1),
            "reglas_seleccionadas": codes,
            "resultados": [{"regla": c, "nombre": n, "resultado": r} for c, n, r in results],
            "laboratorio": str(LAB_ROOT),
        }
        path = REPORTS_ROOT / f"run_{start.strftime('%Y%m%d_%H%M%S')}.json"
        try:
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.log(f"Reporte de ejecución guardado en: {path}")
        except OSError as e:
            self.log(f"No se pudo guardar el reporte: {e}")

    # ------------------------------------------------------------------
    # Utilidades de archivos
    # ------------------------------------------------------------------
    def files(self, count, name):
        d = WORK_ROOT / name
        d.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(count):
            p = d / f"document_{i:03d}.txt"
            p.write_text("ARCHIVO DE PRUEBA ALFA-Sentinel\n", encoding="utf-8")
            out.append(p)
        return out

    # ------------------------------------------------------------------
    # Acciones — una por regla
    # ------------------------------------------------------------------
    def honeyfile(self):
        # HR-03: 1 interacción con el archivo señuelo
        HONEYFILE.write_text(HONEYFILE.read_text(encoding="utf-8") + "SIMULATED ACCESS\n", encoding="utf-8")

    def mod_mass(self):
        # HR-01: modificación masiva (20+ archivos existentes reescritos en <10s)
        fs = self.files(25, "mod_mass_activity")
        for i, p in enumerate(fs, 1):
            p.write_text("SIMULATED MASS MODIFICATION\n" + "X" * 800, encoding="utf-8")
            self.progress.set(i / len(fs) * 100)

    def write_intensive(self):
        # HR-04: escritura intensiva (50+ escrituras en <10s)
        fs = self.files(55, "write_intensive_activity")
        for i, p in enumerate(fs, 1):
            p.write_text("SIMULATED INTENSIVE WRITE\n" + "X" * 1200, encoding="utf-8")
            self.progress.set(i / len(fs) * 100)

    def rename(self):
        # HR-02: renombrado anómalo (5+ renombrados, sin cifrar contenido)
        fs = self.files(7, "rename_activity")
        for i, p in enumerate(fs, 1):
            p.rename(p.with_suffix(p.suffix + ".locked"))
            self.progress.set(i / len(fs) * 100)

    def suspicious(self):
        # HR-05: proceso desde contexto atípico (best effort)
        worker = WORK_ROOT / "suspicious_context_worker.py"
        worker.write_text("import time\nprint('simulated suspicious worker')\ntime.sleep(8)\n", encoding="utf-8")
        subprocess.run([sys.executable, str(worker)], check=True)

    def cpu(self):
        # HR-06: consumo de CPU elevado (~10-12s)
        worker = WORK_ROOT / "cpu_worker.py"
        worker.write_text(
            "import time\nend=time.time()+12\nx=0\nwhile time.time()<end:\n x=(x*1664525+1013904223)%4294967296\nprint(x)\n",
            encoding="utf-8",
        )
        subprocess.run([sys.executable, str(worker)], check=True)

    def shared(self):
        # HR-07: recursos compartidos (diagnóstico local; no crea SMB/NFS real)
        d = WORK_ROOT / "shared_resources_simulation"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(22):
            (d / f"shared_{i:03d}.txt").write_text("SIMULATED SHARED RESOURCE\n", encoding="utf-8")
        self.root.after(0, lambda: messagebox.showinfo(
            "HR-07",
            "Se creó una zona local de diagnóstico.\n\nLa aplicación NO crea SMB/NFS ni modifica la red. "
            "La activación real de HR-07 depende de que el agente supervise un recurso compartido.",
        ))

    def tempfiles(self):
        # HR-08: creación masiva de temporales (30+ en <15s)
        d = WORK_ROOT / "temp_activity"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(35):
            (d / f"tmp_{i:03d}.tmp").write_text("temporary simulated ransomware data\n", encoding="utf-8")
            self.progress.set((i + 1) / 35 * 100)

    def delete(self):
        # HR-09: eliminación anómala (20+ en <15s)
        d = WORK_ROOT / "deletion_activity"
        d.mkdir(parents=True, exist_ok=True)
        fs = []
        for i in range(25):
            p = d / f"delete_{i:03d}.txt"
            p.write_text("safe deletion test\n", encoding="utf-8")
            fs.append(p)
        for i, p in enumerate(fs, 1):
            p.unlink(missing_ok=True)
            self.progress.set(i / len(fs) * 100)

    def user_activity(self):
        # HR-10: actividad mixta sobre "archivos de usuario" (30+ ops en <20s):
        # combina creación, reescritura y renombrado en una carpeta simulada
        d = WORK_ROOT / "user_documents_activity"
        d.mkdir(parents=True, exist_ok=True)
        fs = []
        for i in range(15):
            p = d / f"user_doc_{i:03d}.txt"
            p.write_text("ARCHIVO DE USUARIO SIMULADO\n", encoding="utf-8")
            fs.append(p)
        ops = 0
        for p in fs:
            p.write_text(p.read_text(encoding="utf-8") + "EDITADO\n", encoding="utf-8")
            ops += 1
        for p in fs:
            p.rename(p.with_suffix(".bak"))
            ops += 1
        self.progress.set(100)

    def repetitive(self):
        # HR-11: actividad repetitiva del mismo proceso (40+ ops)
        fs = self.files(8, "repetitive_activity")
        for i in range(45):
            p = fs[i % len(fs)]
            p.write_text(f"REPETITIVE SIMULATION {i}\n" + "R" * 500, encoding="utf-8")
            self.progress.set((i + 1) / 45 * 100)

    # ------------------------------------------------------------------
    # Limpieza
    # ------------------------------------------------------------------
    def cleanup(self):
        if not self.unlocked or self.running:
            return
        if not messagebox.askyesno("Limpiar laboratorio", f"Eliminar únicamente:\n{LAB_ROOT}\n\n¿Continuar?"):
            return
        import shutil
        shutil.rmtree(LAB_ROOT, ignore_errors=True)
        self.progress.set(0)
        self.status.set("Laboratorio eliminado.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
