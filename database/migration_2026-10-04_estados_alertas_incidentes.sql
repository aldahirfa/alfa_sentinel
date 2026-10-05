-- ============================================================
-- ALFA-Sentinel -- estados de alertas e incidentes (2026-10-04)
--
-- La alerta solo se tría: Pendiente (NEW), Escalada (ESCALATED) o
-- Descartada (FALSE_POSITIVE / LEGITIMATE_ACTIVITY). Investigar,
-- contener, clasificar y cerrar son del incidente. Este script ajusta
-- los datos que ya existen a ese esquema. No borra nada.
--
--   psql -U <usuario> -d alfa_sentinel -f migration_2026-10-04_estados_alertas_incidentes.sql
--
-- Seguro de correr más de una vez.
-- ============================================================

BEGIN;

-- Alertas que ya están en un incidente -> Escalada.
UPDATE alerts SET status = 'ESCALATED'
WHERE incident_id IS NOT NULL AND status <> 'ESCALATED';

-- Estados de alerta que ya no existen (sin incidente).
UPDATE alerts SET status = 'NEW', resolved_at = NULL
WHERE incident_id IS NULL AND status = 'ACKNOWLEDGED';

UPDATE alerts SET status = 'LEGITIMATE_ACTIVITY', resolved_at = COALESCE(resolved_at, CURRENT_TIMESTAMP)
WHERE incident_id IS NULL AND status = 'CLOSED';

-- "Posible amenaza" se pisaba con "No determinado".
UPDATE incidents SET classification = 'UNDETERMINED'
WHERE classification = 'POSSIBLE_THREAT';

-- Cerrar exige clasificación: los cerrados sin clasificar quedan
-- como "No determinado".
UPDATE incidents SET classification = 'UNDETERMINED'
WHERE status = 'CLOSED' AND classification IS NULL;

-- Incidentes cuyo equipo está aislado (aislamiento confirmado) ->
-- Contenido, como hace ahora el sistema automáticamente.
UPDATE incidents SET status = 'CONTAINED'
WHERE status IN ('OPEN', 'IN_PROGRESS')
  AND EXISTS (
      SELECT 1 FROM host_isolations hi
      WHERE hi.incident_id = incidents.id
        AND hi.status IN ('EXECUTED', 'RELEASE_REQUESTED')
        AND hi.released_at IS NULL
  );

COMMIT;

SELECT 'alertas' AS tabla, status, COUNT(*) FROM alerts GROUP BY status
UNION ALL
SELECT 'incidentes', status, COUNT(*) FROM incidents GROUP BY status
ORDER BY 1, 2;
