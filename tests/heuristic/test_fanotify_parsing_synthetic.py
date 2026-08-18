"""agent/adapters/linux_fanotify.py -- pruebas del parseo de eventos y
de la caché (path -> (pid, timestamp)) con un buffer SINTÉTICO (mismo
layout binario que entrega el kernel real, fabricado a mano) y del
comportamiento de start() cuando fanotify NO está disponible.

Por qué sintético y no con fanotify real: fanotify_init() exige el
privilegio CAP_SYS_ADMIN, que este entorno de desarrollo no tiene (ver
tests/heuristic/README.md, sección "Limitaciones de este entorno") --
confirmado explícitamente en 2026-08-16 (errno=EPERM, incluso dentro
de un user namespace con --map-root-user, porque fanotify es un
recurso del namespace de usuario INICIAL, no delegable). Esta prueba
no simula que fanotify funcione -- prueba la lógica de parseo (que sí
se puede probar sin privilegios, fabricando el mismo formato binario
documentado en <linux/fanotify.h>) y confirma que start() degrada
limpio sin privilegios, que es exactamente el comportamiento honesto
esperado en este entorno.

Ejecutar: python3 tests/heuristic/test_fanotify_parsing_synthetic.py
"""
import os
import struct
import sys
import time

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
sys.path.insert(0, os.path.abspath(AGENT_DIR))

from adapters.linux_fanotify import FanotifyWatcher, _METADATA_FORMAT, _METADATA_SIZE  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, (f"({detail})" if detail and not condition else ""))


check("struct fanotify_event_metadata mide 24 bytes (sin padding)", _METADATA_SIZE == 24, str(_METADATA_SIZE))

# 1) start() en un entorno sin privilegios -> debe degradar limpio.
watcher_unavailable = FanotifyWatcher()
started = watcher_unavailable.start("/tmp")
check("start() sin CAP_SYS_ADMIN devuelve False (no lanza excepción)", started is False)
check("available queda en False", watcher_unavailable.available is False)

# 2) Parseo de un evento sintético con el layout binario real del
#    kernel, apuntando a un fd real que abrimos nosotros mismos (para
#    poder resolver /proc/self/fd/<fd> a una ruta real sin necesitar
#    que el kernel nos haya entregado ese fd de verdad).
test_file = "/tmp/alfa_fanotify_synthetic_test.txt"
open(test_file, "w").close()
real_fd = os.open(test_file, os.O_RDONLY)

fake_pid = 987654
record = struct.pack(
    _METADATA_FORMAT,
    _METADATA_SIZE,  # event_len
    3,                # vers
    0,                # reserved
    _METADATA_SIZE,  # metadata_len
    0x00000002,       # mask (FAN_MODIFY)
    real_fd,
    fake_pid,
)

watcher = FanotifyWatcher()
watcher._handle_buffer(record)

result_pid = watcher.lookup(test_file)
check("lookup() devuelve el PID sintético tras parsear el evento", result_pid == fake_pid, str(result_pid))

# 3) Varios eventos concatenados en un solo buffer (el kernel puede
#    entregar más de un evento por lectura) -- confirma que el offset
#    avanza correctamente entre registros. Usa DOS fd nuevos (el 'fd'
#    de la Prueba 2 ya se cerró dentro de _handle_buffer -- fanotify
#    entrega un fd que hay que cerrar después de leerlo, así que no se
#    puede reusar 'record').
test_file_3a = "/tmp/alfa_fanotify_synthetic_test_3a.txt"
test_file_3b = "/tmp/alfa_fanotify_synthetic_test_3b.txt"
open(test_file_3a, "w").close()
open(test_file_3b, "w").close()
real_fd_3a = os.open(test_file_3a, os.O_RDONLY)
real_fd_3b = os.open(test_file_3b, os.O_RDONLY)

record_3a = struct.pack(_METADATA_FORMAT, _METADATA_SIZE, 3, 0, _METADATA_SIZE, 0x00000002, real_fd_3a, 222222)
record_3b = struct.pack(_METADATA_FORMAT, _METADATA_SIZE, 3, 0, _METADATA_SIZE, 0x00000002, real_fd_3b, 333333)
watcher2 = FanotifyWatcher()
watcher2._handle_buffer(record_3a + record_3b)
check("buffer con 2 eventos concatenados: primer PID resuelto", watcher2.lookup(test_file_3a) == 222222)
check("buffer con 2 eventos concatenados: segundo PID resuelto", watcher2.lookup(test_file_3b) == 333333)

# 4) TTL de la caché -- una entrada vieja no se devuelve.
with watcher._lock:
    key = list(watcher._recent.keys())[0]
    pid, _ = watcher._recent[key]
    watcher._recent[key] = (pid, time.time() - (watcher.CACHE_TTL_SECONDS + 1))
check("lookup() tras expirar el TTL de la caché devuelve None", watcher.lookup(test_file) is None)

os.remove(test_file)
os.remove(test_file_3a)
os.remove(test_file_3b)

print()
passed = sum(1 for _, c in RESULTS if c)
total = len(RESULTS)
print(f"{passed}/{total} pruebas OK (test_fanotify_parsing_synthetic.py)")
if passed != total:
    print("\nFALLARON:")
    for name, c in RESULTS:
        if not c:
            print(" -", name)
sys.exit(0 if passed == total else 1)
