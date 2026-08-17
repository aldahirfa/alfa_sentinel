-- ============================================================
-- ALFA-Sentinel — Re-seed de catálogos (2026-08-16)
--
-- POR QUÉ EXISTE ESTE ARCHIVO: hiciste un
--
--   TRUNCATE TABLE agent_credentials, agent_honeyfile_templates,
--       agent_rule, agents, alert_rule, alerts, audit_logs, endpoints,
--       enrollment_tokens, event_types, events, heuristic_rules,
--       honeyfile_activations, honeyfile_templates, honeyfiles,
--       host_isolations, incidents, metric_types, reports,
--       severity_levels, system_settings
--   RESTART IDENTITY CASCADE;
--
-- Esa lista mezcla dos tipos de tablas muy distintos:
--   (a) datos OPERATIVOS (agentes, endpoints, alertas, incidentes,
--       eventos, honeyfiles, reportes, auditoría) -- esto sí es "tuyo",
--       se vacía y se vuelve a llenar solo, con uso real del sistema.
--   (b) catálogos DE REFERENCIA (event_types, severity_levels,
--       metric_types, heuristic_rules, system_settings) -- filas fijas
--       de las que depende casi cualquier consulta del sistema (de qué
--       severidad es un risk_score, qué reglas heurísticas existen,
--       qué tipos de evento son válidos). Estas NO se regeneran solas
--       con el uso normal -- por eso, apenas se vaciaron, dejó de
--       poder cargar cualquier página que las consulte.
--
-- Este archivo solo reinserta el grupo (b), exactamente con los mismos
-- valores semilla que trae una instalación nueva (ver
-- database/schema.sql, sección de datos iniciales). No toca 'roles',
-- 'users' ni 'user_roles' -- esas no estaban en tu TRUNCATE, tu sesión
-- sigue intacta. No reinserta nada del grupo (a): agentes/endpoints/
-- alertas/etc. se vuelven a poblar solos cuando el agente vuelva a
-- reportar y uses el sistema con normalidad.
--
-- SEGURO DE CORRER MÁS DE UNA VEZ: cada INSERT lleva
-- ON CONFLICT ... DO NOTHING sobre la columna única de cada tabla, así
-- que si alguna fila ya existe (por ejemplo si volvés a correr esto
-- por las dudas) no se duplica ni falla.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f reseed_catalogos_2026-08-16.sql
--   (o pegar el contenido en pgAdmin -> Query Tool -> Execute)
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- EVENT TYPES -- los 4 tipos que el agente reporta hoy (watchdog:
-- on_created/on_modified/on_deleted/on_moved).
-- ------------------------------------------------------------
INSERT INTO event_types (name, description, category) VALUES
    ('file_created',  'Archivo creado',              'file'),
    ('file_modified', 'Archivo modificado',          'file'),
    ('file_deleted',  'Archivo eliminado',           'file'),
    ('file_renamed',  'Archivo renombrado o movido', 'file')
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- SEVERITY LEVELS -- bandas 0-24.99 / 25-49.99 / 50-74.99 / 75-100,
-- nombres en español (BAJO/MEDIO/ALTO/CRÍTICO), la fuente de verdad
-- de la que depende toda la corrección arquitectónica del 2026-08-16.
-- ------------------------------------------------------------
INSERT INTO severity_levels (name, min_score, max_score, description) VALUES
    ('BAJO',     0.00,  24.99,  'Actividad dentro de lo esperado -- sin indicios de comportamiento sospechoso.'),
    ('MEDIO',    25.00, 49.99,  'Actividad inusual que amerita revisión, sin señales claras de compromiso.'),
    ('ALTO',     50.00, 74.99,  'Comportamiento consistente con una amenaza activa -- requiere atención pronta.'),
    ('CRÍTICO',  75.00, 100.00, 'Evidencia fuerte de compromiso (p. ej. acceso a un honeyfile) -- requiere respuesta inmediata.')
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- METRIC TYPES -- qué mide cada regla heurística (12 tipos).
-- ------------------------------------------------------------
INSERT INTO metric_types (name, description, unit) VALUES
    ('MODIFICACIONES_ARCHIVOS',           'Cantidad de archivos únicos modificados en la ventana', 'archivos'),
    ('RENOMBRADOS_ARCHIVOS',              'Cantidad de renombrados con patrón/extensión anómala', 'archivos'),
    ('ACCESO_HONEYFILE',                  'Interacción detectada sobre un archivo señuelo', 'eventos'),
    ('ESCRITURAS_ARCHIVOS',               'Cantidad total de operaciones de escritura/modificación', 'operaciones'),
    ('PROCESOS_SOSPECHOSOS',              'Procesos con características sospechosas detectados', 'procesos'),
    ('CPU_PROCESO',                       'Consumo de CPU sostenido por un proceso', '%'),
    ('ACCESO_RECURSOS_COMPARTIDOS',       'Operaciones sobre archivos en rutas/recursos compartidos', 'archivos'),
    ('CREACION_ARCHIVOS_TEMPORALES',      'Creación de archivos temporales', 'archivos'),
    ('ELIMINACIONES_ARCHIVOS',            'Cantidad de archivos eliminados en la ventana', 'archivos'),
    ('ACTIVIDAD_ARCHIVOS_USUARIO',        'Actividad repetitiva sobre archivos de carpetas de usuario', 'operaciones'),
    ('ACTIVIDAD_AUTOMATIZADA_ARCHIVOS',   'Operaciones repetitivas realizadas por un mismo proceso', 'operaciones'),
    ('CORRELACION_MULTIPLES_INDICADORES', 'Cantidad de reglas distintas activadas en el mismo episodio', 'reglas')
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- HEURISTIC RULES -- las 12 reglas definitivas (HR-01 a HR-12).
-- HR-05, HR-06 y HR-11 se siembran con is_active=FALSE (diferidas:
-- requieren datos que el agente no recopila hoy, ver descripción de
-- cada una).
-- ------------------------------------------------------------
INSERT INTO heuristic_rules (name, description, event_type_id, metric_type_id, weight, threshold, window_seconds, is_active) VALUES
    (
        'modificacion_masiva_archivos',
        'HR-01 -- Modificación masiva de archivos: 20 o más archivos únicos modificados dentro de una ventana de 10 segundos.',
        (SELECT id FROM event_types WHERE name = 'file_modified'),
        (SELECT id FROM metric_types WHERE name = 'MODIFICACIONES_ARCHIVOS'),
        25.00, 20.00, 10, TRUE
    ),
    (
        'renombrado_extension_anomala',
        'HR-02 -- Renombrado/extensión anómala: 5 o más renombrados con patrón sospechoso (ej. cambio a extensión asociada a ransomware conocido) dentro de una ventana de 15 segundos.',
        (SELECT id FROM event_types WHERE name = 'file_renamed'),
        (SELECT id FROM metric_types WHERE name = 'RENOMBRADOS_ARCHIVOS'),
        20.00, 5.00, 15, TRUE
    ),
    (
        'acceso_honeyfile',
        'HR-03 -- Acceso/activación de honeyfile: cualquier interacción detectada sobre un archivo señuelo lleva el risk_score inmediatamente a 100 (CRÍTICO), sin esperar otras reglas ni acumular progresivamente.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACCESO_HONEYFILE'),
        100.00, 1.00, NULL, TRUE
    ),
    (
        'escritura_intensiva_archivos',
        'HR-04 -- Escritura intensiva: 50 o más operaciones de escritura/modificación dentro de una ventana de 10 segundos. Puede solaparse con HR-01; peso menor a propósito para no duplicar artificialmente el riesgo.',
        (SELECT id FROM event_types WHERE name = 'file_modified'),
        (SELECT id FROM metric_types WHERE name = 'ESCRITURAS_ARCHIVOS'),
        15.00, 50.00, 10, TRUE
    ),
    (
        'proceso_sospechoso',
        'HR-05 -- Proceso sospechoso (DIFERIDA): requiere atribuir un proceso (process_id/process_name) a cada evento de archivo, dato que el agente no recopila hoy (watchdog solo entrega ruta y tipo de evento). No se simula: se activará cuando el agente reporte esa atribución.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'PROCESOS_SOSPECHOSOS'),
        10.00, 1.00, 30, FALSE
    ),
    (
        'consumo_cpu_elevado',
        'HR-06 -- Consumo elevado de CPU por proceso (DIFERIDA): requiere que el agente muestree y reporte consumo de CPU por proceso, algo que no hace hoy. No se simula: se activará cuando exista esa fuente de datos. Señal secundaria -- nunca debe llevar por sí sola a CRÍTICO.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'CPU_PROCESO'),
        5.00, 80.00, 10, FALSE
    ),
    (
        'acceso_recursos_compartidos',
        'HR-07 -- Acceso masivo a recursos compartidos: 20 o más operaciones sobre archivos en rutas compartidas/remotas dentro de una ventana de 15 segundos.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACCESO_RECURSOS_COMPARTIDOS'),
        15.00, 20.00, 15, TRUE
    ),
    (
        'creacion_masiva_temporales',
        'HR-08 -- Creación masiva de archivos temporales: 30 o más archivos temporales creados dentro de una ventana de 15 segundos. Señal secundaria.',
        (SELECT id FROM event_types WHERE name = 'file_created'),
        (SELECT id FROM metric_types WHERE name = 'CREACION_ARCHIVOS_TEMPORALES'),
        5.00, 30.00, 15, TRUE
    ),
    (
        'eliminacion_anomala_archivos',
        'HR-09 -- Eliminación anómala: 20 o más archivos eliminados dentro de una ventana de 15 segundos. Especialmente relevante combinada con modificación/renombrado.',
        (SELECT id FROM event_types WHERE name = 'file_deleted'),
        (SELECT id FROM metric_types WHERE name = 'ELIMINACIONES_ARCHIVOS'),
        15.00, 20.00, 15, TRUE
    ),
    (
        'actividad_archivos_usuario',
        'HR-10 -- Actividad repetitiva sobre archivos de usuario: 30 o más operaciones dentro de una ventana de 20 segundos sobre rutas de usuario (Documents, Desktop, Downloads, Pictures, etc.).',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_ARCHIVOS_USUARIO'),
        10.00, 30.00, 20, TRUE
    ),
    (
        'actividad_repetitiva_automatizada',
        'HR-11 -- Actividad repetitiva automatizada (DIFERIDA): requiere identificar que las operaciones repetitivas provienen del MISMO proceso, lo que exige atribución de proceso a evento de archivo -- el agente no la recopila hoy. No se simula.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_AUTOMATIZADA_ARCHIVOS'),
        10.00, 40.00, 15, FALSE
    ),
    (
        'correlacion_multiples_indicadores',
        'HR-12 -- Correlación de múltiples indicadores: bonificación de score (no una regla de conteo) cuando coinciden reglas distintas en el mismo episodio -- 2 reglas -> +5, 3 reglas -> +10, 4 o más -> +15. El peso acá (15.00) es el máximo posible, documental; el valor real aplicado (weight_applied en alert_rule) lo calcula el servidor según cuántas reglas distintas participaron.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'CORRELACION_MULTIPLES_INDICADORES'),
        15.00, 2.00, NULL, TRUE
    )
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- SYSTEM SETTINGS -- único parámetro global real hoy.
-- ------------------------------------------------------------
INSERT INTO system_settings (key, value, description) VALUES
    (
        'agent_stale_seconds',
        '120',
        'Segundos sin heartbeat tras los cuales un agente ONLINE pasa a "sin señal reciente" (advertencia) en vez de contar como en línea.'
    )
ON CONFLICT (key) DO NOTHING;

-- ------------------------------------------------------------
-- Verificación rápida: deberías ver 4 / 4 / 12 / 12 / 1.
-- ------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM event_types)     AS event_types_n,
    (SELECT COUNT(*) FROM severity_levels) AS severity_levels_n,
    (SELECT COUNT(*) FROM metric_types)    AS metric_types_n,
    (SELECT COUNT(*) FROM heuristic_rules) AS heuristic_rules_n,
    (SELECT COUNT(*) FROM system_settings) AS system_settings_n;

COMMIT;
