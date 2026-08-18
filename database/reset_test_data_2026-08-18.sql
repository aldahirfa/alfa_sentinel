-- ============================================================
-- ALFA-Sentinel -- Reseteo de datos de prueba (2026-08-18)
--
-- Vacía TODAS las tablas de la base 'alfa_sentinel' EXCEPTO:
--   roles, users, user_roles
-- Esas tres NO aparecen en ningún TRUNCATE de este script, ni
-- siquiera de forma indirecta: no tienen ninguna clave foránea hacia
-- ninguna de las tablas listadas abajo (confirmado leyendo
-- database/schema.sql), así que TRUNCATE ... CASCADE no puede
-- alcanzarlas -- CASCADE solo se propaga hacia tablas que referencian
-- a la tabla truncada, nunca al revés.
--
-- DE DÓNDE SALE ESTA LISTA DE TABLAS (importante leer esto):
-- Este entorno no tiene una conexión de red configurada hacia tu
-- Postgres real ('alfa_sentinel' en ejecución) -- no pude correr
-- \dt / information_schema.tables directamente contra tu base para
-- armar este script. Lo que SÍ hice fue leer database/schema.sql,
-- que es la ÚNICA fuente de sentencias CREATE TABLE en todo el
-- repositorio (verificado: ningún archivo de migración crea tablas
-- nuevas por fuera de él) y que este proyecto mantiene sincronizada
-- con la base real en cada tarea (ver PENDIENTES.md). Ahí hay 24
-- tablas en total; 24 - 3 exentas = las 21 de abajo.
--
-- Antes de correr esto contra tu base real, confirmá vos mismo que
-- coincide con lo que existe hoy:
--
--   SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
--
-- Si tu base tiene alguna tabla que NO aparece en la lista de abajo
-- (por ejemplo, por una migración manual que no llegó a este repo),
-- esa tabla NO se va a vaciar con este script tal cual está.
--
-- AVISO -- catálogos/semilla, no solo datos de prueba:
-- 'severity_levels' (los 4 niveles BAJO/MEDIO/ALTO/CRÍTICO),
-- 'event_types', 'metric_types', 'heuristic_rules' (las 12 reglas
-- del motor heurístico) y 'honeyfile_templates' son catálogos base,
-- no datos generados por uso. Los incluí porque los pediste
-- explícitamente por nombre en la lista, pero con estas tablas vacías
-- el motor heurístico y el despliegue de honeyfiles van a dejar de
-- funcionar hasta volver a sembrarlos -- este repo ya tiene
-- database/schema.sql (sección de INSERTs semilla al final) y
-- database/reseed_catalogos_2026-08-16.sql para eso. Si tu intención
-- era vaciar solo los datos generados por uso (endpoints, agentes,
-- alertas, incidentes, aislamientos, etc.) y dejar estos 5 catálogos
-- intactos, decime y te preparo una segunda versión sin esas tablas.
-- ============================================================

BEGIN;

TRUNCATE TABLE
    endpoints,
    agents,
    agent_credentials,
    event_types,
    severity_levels,
    enrollment_tokens,
    honeyfiles,
    events,
    honeyfile_activations,
    metric_types,
    heuristic_rules,
    agent_rule,
    incidents,
    alerts,
    alert_rule,
    host_isolations,
    audit_logs,
    honeyfile_templates,
    agent_honeyfile_templates,
    reports,
    system_settings
RESTART IDENTITY CASCADE;

COMMIT;

-- ============================================================
-- Verificación -- correr después del TRUNCATE de arriba.
-- ============================================================

-- 1) Las 3 tablas exentas deben conservar exactamente las mismas
--    filas que tenían antes (comparar el número con lo que sabías de
--    antemano que tenían).
SELECT 'roles' AS tabla, COUNT(*) AS filas FROM roles
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'user_roles', COUNT(*) FROM user_roles
ORDER BY tabla;

-- 2) Las 21 restantes deben quedar todas en 0 filas.
SELECT 'endpoints' AS tabla, COUNT(*) AS filas FROM endpoints
UNION ALL SELECT 'agents', COUNT(*) FROM agents
UNION ALL SELECT 'agent_credentials', COUNT(*) FROM agent_credentials
UNION ALL SELECT 'event_types', COUNT(*) FROM event_types
UNION ALL SELECT 'severity_levels', COUNT(*) FROM severity_levels
UNION ALL SELECT 'enrollment_tokens', COUNT(*) FROM enrollment_tokens
UNION ALL SELECT 'honeyfiles', COUNT(*) FROM honeyfiles
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'honeyfile_activations', COUNT(*) FROM honeyfile_activations
UNION ALL SELECT 'metric_types', COUNT(*) FROM metric_types
UNION ALL SELECT 'heuristic_rules', COUNT(*) FROM heuristic_rules
UNION ALL SELECT 'agent_rule', COUNT(*) FROM agent_rule
UNION ALL SELECT 'incidents', COUNT(*) FROM incidents
UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL SELECT 'alert_rule', COUNT(*) FROM alert_rule
UNION ALL SELECT 'host_isolations', COUNT(*) FROM host_isolations
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
UNION ALL SELECT 'honeyfile_templates', COUNT(*) FROM honeyfile_templates
UNION ALL SELECT 'agent_honeyfile_templates', COUNT(*) FROM agent_honeyfile_templates
UNION ALL SELECT 'reports', COUNT(*) FROM reports
UNION ALL SELECT 'system_settings', COUNT(*) FROM system_settings
ORDER BY tabla;
