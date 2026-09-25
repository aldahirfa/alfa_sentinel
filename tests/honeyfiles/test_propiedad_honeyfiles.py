"""Dueño de las carpetas y honeyfiles que crea el agente privilegiado
(agent/file_ownership.py, 2026-09-25) y protección contra enlaces
simbólicos. No requiere servidor ni base de datos.

- El cambio de dueño en Linux (necesita root) se prueba con os.stat /
  os.lstat / os.lchown simulados: se verifica la lógica (quién pasa a
  ser dueño, que nunca se sigan enlaces) sin privilegios reales.
- La protección contra enlaces se prueba con enlaces REALES: symlink en
  Linux y junction en Windows (mklink /J no requiere Administrador).
- En Windows se prueba de verdad la lectura del dueño (Get-Acl) y el
  comando icacls /setowner, asignando el mismo dueño actual (no requiere
  Administrador).

Ejecutar: python tests/honeyfiles/test_propiedad_honeyfiles.py
"""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "agent"))

import file_ownership as fo  # noqa: E402
import honeyfile_deployer as hd  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


def make_link(link, target):
    """Enlace real a una carpeta: symlink en Linux, junction en Windows."""
    if platform.system() == "Windows":
        subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True, check=True)
    else:
        os.symlink(target, link)


def make_file_link(link, target):
    """Enlace real a un archivo (o a un archivo que no existe)."""
    if platform.system() == "Windows":
        # Un symlink de archivo en Windows requiere privilegios; un
        # junction dentro de la ruta sirve para el mismo propósito:
        # ocupar la ruta con algo que no es un archivo propio.
        subprocess.run(["cmd", "/c", "mklink", "/J", link, os.path.dirname(target)], capture_output=True, check=True)
    else:
        os.symlink(target, link)


class LinuxOwnershipSim:
    """Simula un Linux con root: dueños por ruta, os.lchown registrado."""

    def __init__(self, owners):
        self.owners = dict(owners)  # ruta absoluta -> (uid, gid)
        self.lchown_calls = []

    def _wrap(self, real_fn):
        owners = self.owners

        def fake(path, *a, **k):
            real = real_fn(path, *a, **k)
            uid, gid = owners.get(os.path.abspath(path), (0, 0))
            return _StatWithOwner(real, uid, gid)
        return fake

    def _lchown(self, path, uid, gid):
        self.lchown_calls.append((os.path.abspath(path), uid, gid))
        self.owners[os.path.abspath(path)] = (uid, gid)

    def __enter__(self):
        self.saved = (fo._is_privileged, fo.platform.system, os.stat, os.lstat, getattr(os, "lchown", None))
        fo._is_privileged = lambda: True
        fo.platform.system = lambda: "Linux"
        os.stat = self._wrap(self.saved[2])
        os.lstat = self._wrap(self.saved[3])
        os.lchown = self._lchown
        return self

    def __exit__(self, *a):
        fo._is_privileged, fo.platform.system, os.stat, os.lstat, lchown = self.saved
        if lchown is None:
            del os.lchown
        else:
            os.lchown = lchown


class _StatWithOwner:
    """Resultado real de stat con uid/gid simulados."""

    def __init__(self, real, uid, gid):
        self._real, self.st_uid, self.st_gid = real, uid, gid

    def __getattr__(self, name):
        return getattr(self._real, name)


USER = (1000, 1000)
tmp = tempfile.mkdtemp(prefix="alfa_owner_")
try:
    home = os.path.join(tmp, "home_usuario")
    os.mkdir(home)

    # PO-01: carpetas nuevas toman el dueño de su carpeta padre.
    target = os.path.join(home, "Pictures", "ALFA_ARCHIVOS")
    with LinuxOwnershipSim({home: USER}) as sim:
        fo.make_dirs_owned(target)
        check("PO-01: se crean las carpetas que faltaban (Pictures y ALFA_ARCHIVOS)", os.path.isdir(target))
        check("PO-01: cada carpeta nueva pasa al dueño de su carpeta padre (el usuario), no root",
              sim.owners.get(os.path.join(home, "Pictures")) == USER and sim.owners.get(target) == USER, sim.owners)

    # PO-02: ALFA_ARCHIVOS que ya existía a nombre de root se corrige.
    with LinuxOwnershipSim({home: USER, os.path.join(home, "Pictures"): USER, target: (0, 0)}) as sim:
        fo.make_dirs_owned(target)
        check("PO-02: ALFA_ARCHIVOS existente a nombre de root pasa al usuario", sim.owners[target] == USER, sim.owners[target])

    # PO-03: honeyfile creado por el agente -> dueño el usuario, contenido y hash reales.
    honeyfile = os.path.join(target, "Dulce_Trampa.pdf")
    with LinuxOwnershipSim({target: USER}) as sim:
        file_hash = hd._write_and_hash(honeyfile, "linea 1\nlinea 2")
        with open(honeyfile, "rb") as f:
            real = f.read()
        check("PO-03: el honeyfile se crea con el contenido de la plantilla",
              real == "linea 1\nlinea 2".replace("\n", os.linesep).encode("utf-8"), real)
        check("PO-03: el hash informado es el del archivo real", file_hash == hashlib.sha256(real).hexdigest())
        check("PO-03: el honeyfile queda a nombre del usuario", sim.owners.get(honeyfile) == USER, sim.owners.get(honeyfile))
        check("PO-03: el dueño se cambia con lchown (nunca sigue enlaces)", sim.lchown_calls == [(honeyfile, *USER)], sim.lchown_calls)

    # PO-04: sin privilegios no se intenta cambiar nada.
    saved = fo._is_privileged
    fo._is_privileged = lambda: False
    check("PO-04: sin privilegios -> no cambia el dueño", fo.adopt_parent_owner(honeyfile, newly_created=True) is False)
    fo._is_privileged = saved

    # PO-05: nunca se sobrescribe un archivo existente.
    try:
        hd._write_and_hash(honeyfile, "otro contenido")
        check("PO-05: crear sobre un archivo existente -> falla (no lo sobrescribe)", False)
    except OSError:
        with open(honeyfile, "rb") as f:
            check("PO-05: crear sobre un archivo existente -> falla y el original queda intacto",
                  f.read() == "linea 1\nlinea 2".replace("\n", os.linesep).encode("utf-8"))

    # PO-06: ALFA_ARCHIVOS reemplazada por un enlace a otra carpeta -> se rechaza.
    sistema = os.path.join(tmp, "carpeta_del_sistema")
    os.mkdir(sistema)
    link_dir = os.path.join(home, "Documents", "ALFA_ARCHIVOS")
    os.makedirs(os.path.dirname(link_dir))
    make_link(link_dir, sistema)
    try:
        fo.make_dirs_owned(link_dir)
        check("PO-06: ALFA_ARCHIVOS que es un enlace -> se rechaza", False)
    except OSError as error:
        check("PO-06: ALFA_ARCHIVOS que es un enlace/junction -> se rechaza", "enlace" in str(error), str(error))

    # PO-07: enlace plantado en la ruta de un honeyfile -> no se escribe a través de él.
    victim = os.path.join(sistema, "archivo_del_sistema.conf")
    with open(victim, "w") as f:
        f.write("original")
    planted = os.path.join(target, "No_Me_Toques.txt")
    make_file_link(planted, victim)
    try:
        hd._write_and_hash(planted, "contenido del señuelo")
        check("PO-07: enlace plantado en la ruta del honeyfile -> falla", False)
    except OSError:
        with open(victim) as f:
            check("PO-07: enlace plantado -> falla y el archivo del sistema queda intacto", f.read() == "original")

    # PO-08: reconciliación -> un honeyfile existente a nombre de root se corrige,
    # marcado antes como operación propia (evita una falsa alerta HR-03).
    events = []
    monitor = types.SimpleNamespace(mark_internal_operation=lambda p: events.append(("mark", os.path.abspath(p))))
    existing_path = honeyfile
    hd.get_honeyfile_policy = lambda cred: types.SimpleNamespace(status_code=200, json=lambda: {
        "pending": [], "existing": [{"assignment_id": 1, "file_path": "DESKTOP", "file_name": "Dulce_Trampa.pdf",
                                     "file_type": "PDF", "expected_hash": file_hash}]})
    hd.report_honeyfile_policy = lambda cred, results: events.append(("report", results))
    hd.resolve_logical_path = lambda raw: target
    with LinuxOwnershipSim({target: USER, existing_path: (0, 0)}) as sim:
        original_lchown = sim._lchown
        sim._lchown = lambda p, u, g: (events.append(("lchown", os.path.abspath(p))), original_lchown(p, u, g))
        os.lchown = sim._lchown
        watched = hd.apply_honeyfile_policy("cred", honeyfile_monitor=monitor)
        order = [e for e in events if e[0] in ("mark", "lchown")]
        check("PO-08: honeyfile existente a nombre de root pasa al usuario", sim.owners[existing_path] == USER)
        check("PO-08: se marca como operación propia ANTES de cambiar el dueño",
              order[:2] == [("mark", existing_path), ("lchown", existing_path)], order)
        check("PO-08: sigue vigilado y sin reporte (el hash coincide)", watched == [existing_path] and not any(e[0] == "report" for e in events))

    # PO-10: el agente escribe EXACTAMENTE los bytes del archivo real que manda el servidor.
    import base64
    real_pdf = b"%PDF-1.4\n% archivo de prueba\n%%EOF\n"
    pdf_path = os.path.join(target, "Informe_Avance_Proyecto_Q3_2026.pdf")
    pdf_hash = hd._write_and_hash(pdf_path, hd._item_content({"content_b64": base64.b64encode(real_pdf).decode(), "content": "texto"}))
    with open(pdf_path, "rb") as f:
        check("PO-10: content_b64 -> se escriben los bytes exactos (archivo real, no texto)", f.read() == real_pdf)
    check("PO-10: hash informado = hash de esos bytes", pdf_hash == hashlib.sha256(real_pdf).hexdigest())
    check("PO-10: sin content_b64 (servidor anterior) -> se usa el texto", hd._item_content({"content": "hola"}) == "hola")

    # PO-11: nombres con rutas -> rechazados (el agente privilegiado no escribe fuera de ALFA_ARCHIVOS).
    for bad in ("../../etc/cron.d/x", "..", "sub/archivo.pdf", "sub\\archivo.pdf", ""):
        try:
            hd._honeyfile_path(target, bad)
            check(f"PO-11: nombre {bad!r} -> rechazado", False)
        except OSError:
            check(f"PO-11: nombre {bad!r} -> rechazado", True)
    check("PO-11: nombre normal -> aceptado",
          hd._honeyfile_path(target, "Planilla_Sueldos_Septiembre_2026.xlsx") == os.path.join(target, "Planilla_Sueldos_Septiembre_2026.xlsx"))

    # PO-12: honeyfile ya creado que desapareció -> se pide la política completa y se recrea con el archivo real.
    calls = []
    real_xlsx = b"PK\x03\x04 xlsx de prueba"
    missing_item = {"assignment_id": 7, "file_path": "DESKTOP", "file_name": "Planilla_Viaticos_Septiembre_2026.xlsx",
                    "file_type": "XLSX", "content": "texto", "expected_hash": "x"}

    def fake_policy(cred, full=False):
        calls.append(full)
        item = dict(missing_item, content_b64=base64.b64encode(real_xlsx).decode() if full else None)
        return types.SimpleNamespace(status_code=200, json=lambda: {"pending": [], "existing": [item]})

    reports = []
    hd.get_honeyfile_policy = fake_policy
    hd.report_honeyfile_policy = lambda cred, results: reports.extend(results)
    hd.apply_honeyfile_policy("cred")
    recreated = os.path.join(target, missing_item["file_name"])
    check("PO-12: faltaba en disco -> se pidió la política completa (una sola vez más)", calls == [False, True], calls)
    with open(recreated, "rb") as f:
        check("PO-12: se recreó con los bytes del archivo real", f.read() == real_xlsx)
    check("PO-12: se informa CREATED con el hash nuevo",
          reports and reports[0]["status"] == "CREATED" and reports[0]["file_hash"] == hashlib.sha256(real_xlsx).hexdigest(), reports)

    # PO-13: si la política completa no llega, NO se escribe texto en lugar del archivo real.
    os.remove(recreated)
    reports.clear()
    hd.get_honeyfile_policy = lambda cred, full=False: (types.SimpleNamespace(status_code=200, json=lambda: {"pending": [], "existing": [dict(missing_item, content_b64=None)]}) if not full else None)
    hd.apply_honeyfile_policy("cred")
    check("PO-13: sin el archivo real -> no se crea nada y se informa FAILED (se reintenta)",
          not os.path.exists(recreated) and reports and reports[0]["status"] == "FAILED", reports)

    # PO-09 (solo Windows): lectura real del dueño y icacls /setowner.
    if platform.system() == "Windows":
        owner = fo._windows_owner(tmp)
        check("PO-09: Windows -> se lee el dueño real de la carpeta (Get-Acl)", bool(owner) and "\\" in owner, owner)
        probe = os.path.join(tmp, "prueba icacls.txt")
        open(probe, "w").close()
        result = subprocess.run(["icacls", probe, "/setowner", owner, "/L", "/Q"], capture_output=True, text=True)
        check("PO-09: Windows -> icacls /setowner acepta el dueño leído (mismo dueño, sin Administrador)",
              result.returncode == 0, result.stdout + result.stderr)
    else:
        print("(PO-09 omitida -- solo aplica en Windows)")
finally:
    # Los junctions se borran como carpetas vacías, sin tocar su destino.
    for root, dirs, _files in os.walk(tmp, topdown=False):
        for d in dirs:
            p = os.path.join(root, d)
            if fo.is_link_or_junction(p):
                os.rmdir(p) if platform.system() == "Windows" else os.unlink(p)
    shutil.rmtree(tmp, ignore_errors=True)

print()
total = len(RESULTS)
passed = sum(1 for _, ok in RESULTS if ok)
print(f"{passed}/{total} pruebas pasaron")
if passed != total:
    sys.exit(1)
