-- ============================================================
-- ALFA-Sentinel — Migración 2026-08-16
-- Activar HR-05 (Proceso Sospechoso), HR-06 (Consumo CPU Elevado) y
-- HR-11 (Actividad Repetitiva Automatizada)
--
-- POR QUÉ EXISTE ESTE ARCHIVO: estas tres reglas se sembraron con
-- is_active = FALSE porque el agente todavía no podía atribuir un
-- proceso a un evento de archivo ni muestrear CPU por proceso. Esa
-- capacidad ya existe (2026-08-16, ver PENDIENTES.md,
-- "Implementación final del motor heurístico y configuración por
-- endpoint" -- agent/adapters/ para atribución de proceso,
-- agent/cpu_monitor.py para CPU sostenida), así que corresponde
-- activarlas.
--
-- QUÉ HACE (y nada más que esto): tres UPDATE por nombre, cambiando
-- SOLO 'is_active' de FALSE a TRUE. No toca weight/threshold/
-- window_seconds/description/event_type_id/metric_type_id -- si ya
-- los ajustaste a mano, quedan intactos. No inserta ni borra filas.
--
-- IMPORTANTE -- orden de despliegue: correla DESPUÉS de actualizar
-- server/main.py y el agente a la versión que ya sabe evaluar estas
-- reglas. Si la activás acá antes de desplegar el código nuevo, el
-- servidor empieza a aceptar (si algún cliente viejo las reportara)
-- o simplemente las deja activas sin que el agente viejo las evalúe
-- nunca -- no rompe nada, pero no tiene efecto hasta que el agente
-- nuevo esté corriendo.
--
-- SEGURA DE CORRER MÁS DE UNA VEZ: los UPDATE solo tocan filas que
-- sigan en FALSE -- si ya se activaron, no hacen nada la segunda vez.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f migration_2026-08-16_activar_hr05_hr06_hr11.sql
-- ============================================================

BEGIN;

UPDATE heuristic_rules SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
    WHERE name = 'Proceso Sospechoso' AND is_active = FALSE;

UPDATE heuristic_rules SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
    WHERE name = 'Consumo CPU Elevado' AND is_active = FALSE;

UPDATE heuristic_rules SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
    WHERE name = 'Actividad Repetitiva Automatizada' AND is_active = FALSE;

-- Verificación: las tres deberían aparecer con is_active = t.
SELECT name, is_active, weight, threshold, window_seconds
FROM heuristic_rules
WHERE name IN ('Proceso Sospechoso', 'Consumo CPU Elevado', 'Actividad Repetitiva Automatizada')
ORDER BY name;

COMMIT;
