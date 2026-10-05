-- ============================================================
-- ALFA-Sentinel -- limpiar datos de pruebas (2026-10-04)
--
-- Borra TODO lo que generan las pruebas y deja la configuración:
--
--   SE BORRA:   endpoints, agentes y sus credenciales, códigos de
--               registro, eventos, alertas, incidentes, aislamientos,
--               honeyfiles creados en los equipos (y sus asignaciones),
--               configuraciones de reglas por equipo, reportes generados
--               y bitácora de auditoría.
--   SE CONSERVA: usuarios y roles, reglas heurísticas, niveles de
--               severidad, tipos de evento y métricas, plantillas de
--               honeyfiles (incluidas las 12 realistas) y la
--               configuración del sistema.
--
-- A diferencia de reset_test_data_2026-08-18.sql, NO borra los
-- catálogos: no hace falta volver a cargar reglas ni plantillas.
--
-- DESPUÉS: cada agente instalado deja de ser reconocido por el servidor.
-- Hay que volver a registrarlo con un código nuevo:
--   - Linux:   sudo bash instalar.sh  -> responder 'n' a "¿Conservar el registro actual?"
--   - Windows: instalar.bat           -> responder 'n' a la misma pregunta
--   (los honeyfiles que ya están en los equipos se vuelven a registrar solos)
--
-- NO SE PUEDE DESHACER.
--   psql -U <usuario> -d alfa_sentinel -f limpiar_datos_prueba_2026-10-04.sql
-- ============================================================

BEGIN;

TRUNCATE TABLE
    alert_rule,
    alerts,
    host_isolations,
    incidents,
    events,
    honeyfile_activations,
    honeyfiles,
    agent_honeyfile_templates,
    agent_rule,
    agent_credentials,
    agents,
    endpoints,
    enrollment_tokens,
    reports,
    audit_logs
RESTART IDENTITY;

COMMIT;

SELECT 'endpoints' AS tabla, COUNT(*) AS filas FROM endpoints
UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL SELECT 'incidents', COUNT(*) FROM incidents
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'honeyfiles', COUNT(*) FROM honeyfiles
UNION ALL SELECT '--- se conservan ---', NULL
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'heuristic_rules', COUNT(*) FROM heuristic_rules
UNION ALL SELECT 'honeyfile_templates', COUNT(*) FROM honeyfile_templates;
