-- ============================================================
-- ALFA-Sentinel -- Re-siembra de catálogos (2026-08-18)
--
-- Complemento de database/reset_test_data_2026-08-18.sql: ese script
-- vacía, entre otras, estas 4 tablas de catálogo/semilla porque las
-- pediste explícitamente por nombre:
--   event_types, severity_levels, metric_types, heuristic_rules
-- Sin estas filas el motor heurístico no puede funcionar (no hay con
-- qué comparar risk_score, no hay reglas que evaluar). Este script
-- las vuelve a sembrar con los MISMOS valores de una instalación
-- nueva -- copiados tal cual de database/schema.sql (sección de
-- INSERTs semilla, líneas ~725-880), NO del archivo viejo
-- database/reseed_catalogos_2026-08-16.sql, que quedó desactualizado
-- (todavía tiene nombres de regla en snake_case como
-- 'consumo_cpu_elevado' y HR-05/06/11 en is_active=FALSE -- eso era
-- así ANTES de la implementación final del motor heurístico del
-- 2026-08-16; hoy schema.sql tiene nombres "Título Con Espacios" y
-- las 12 reglas activas. Si reinsertaras con el archivo viejo, el
-- sistema quedaría funcionando con datos incorrectos/obsoletos).
--
-- También agrego 'system_settings' (agent_stale_seconds): no la
-- pediste por nombre en la lista de catálogos, pero SÍ está en el
-- TRUNCATE de reset_test_data_2026-08-18.sql, y sin ella el sistema
-- usa el default hardcodeado de server/main.py en vez del valor
-- configurable -- inofensivo, pero la incluyo para dejar la base
-- exactamente como una instalación nueva.
--
-- QUÉ NO INCLUYE ESTE SCRIPT Y POR QUÉ:
--
-- 1) 'roles' -- schema.sql sí trae un INSERT INTO roles (fila
--    'admin'), pero tu instrucción explícita en el pedido anterior fue
--    "NO modifiques ni elimines roles/users/user_roles" -- esas tres
--    tablas ni siquiera se vaciaron con el TRUNCATE, así que no hay
--    nada que reponer ahí. Si igual lo corrieras, no rompe nada
--    (llevaría ON CONFLICT DO NOTHING), pero lo omito por prolijidad
--    y para no tocar esas tablas ni de forma indirecta.
--
-- 2) 'honeyfile_templates' -- lo marqué como catálogo en el aviso del
--    script anterior, pero revisando su definición (database/
--    schema.sql, sección 20) resultó no serlo: cada plantilla tiene
--    'content' (texto real del señuelo), 'file_path' (ubicación
--    lógica) y 'created_by' (FK a users, quién la creó desde el
--    Wizard de Despliegue) -- son datos que un usuario real redactó,
--    no una constante fija del sistema. No hay ningún INSERT INTO
--    honeyfile_templates en todo el repositorio (ni en schema.sql ni
--    en ningún archivo de migración) -- nunca existió una "semilla"
--    para esta tabla, se llena solo desde la interfaz. Inventar
--    contenido de plantillas acá sería fabricar datos que no son
--    tuyos, así que no lo hago: después de correr el TRUNCATE vas a
--    necesitar recrear tus honeyfiles desde el Wizard de Despliegue
--    de la aplicación.
--
-- SEGURO DE CORRER MÁS DE UNA VEZ: cada INSERT lleva
-- ON CONFLICT (columna_única) DO NOTHING, así que si alguna fila ya
-- existe no se duplica ni falla.
--
-- Igual que con el script anterior: no lo ejecuté contra ninguna base
-- real, solo lo armé y lo validé en una base descartable de prueba.
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
-- nombres en español (BAJO/MEDIO/ALTO/CRÍTICO).
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
-- HEURISTIC RULES -- las 12 reglas de la especificación definitiva
-- (HR-01 a HR-12), nombres "Título Con Espacios" -- deben coincidir
-- exactamente con server/main.py (STRONG_RULE_NAMES/
-- DEFERRED_RULE_NAMES/FIXED_SCORING_RULE_NAMES) y agent/
-- heuristic_engine.py (RULE_NAMES), o dejan de matchear.
-- ------------------------------------------------------------
INSERT INTO heuristic_rules (name, description, event_type_id, metric_type_id, weight, threshold, window_seconds, is_active) VALUES
    (
        'Modificacion Masiva Archivos',
        'HR-01 -- Modificación masiva de archivos: 20 o más archivos únicos modificados dentro de una ventana de 10 segundos.',
        (SELECT id FROM event_types WHERE name = 'file_modified'),
        (SELECT id FROM metric_types WHERE name = 'MODIFICACIONES_ARCHIVOS'),
        25.00, 20.00, 10, TRUE
    ),
    (
        'Renombrado Extension Anomala',
        'HR-02 -- Renombrado/extensión anómala: 5 o más renombrados con patrón sospechoso (ej. cambio a extensión asociada a ransomware conocido) dentro de una ventana de 15 segundos.',
        (SELECT id FROM event_types WHERE name = 'file_renamed'),
        (SELECT id FROM metric_types WHERE name = 'RENOMBRADOS_ARCHIVOS'),
        20.00, 5.00, 15, TRUE
    ),
    (
        'Acceso Honeyfile',
        'HR-03 -- Acceso/activación de honeyfile: cualquier interacción detectada sobre un archivo señuelo lleva el risk_score inmediatamente a 100 (CRÍTICO), sin esperar otras reglas ni acumular progresivamente.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACCESO_HONEYFILE'),
        100.00, 1.00, NULL, TRUE
    ),
    (
        'Escritura Intensiva Archivos',
        'HR-04 -- Escritura intensiva: 50 o más operaciones de escritura/modificación dentro de una ventana de 10 segundos. Puede solaparse con HR-01; peso menor a propósito para no duplicar artificialmente el riesgo.',
        (SELECT id FROM event_types WHERE name = 'file_modified'),
        (SELECT id FROM metric_types WHERE name = 'ESCRITURAS_ARCHIVOS'),
        15.00, 50.00, 10, TRUE
    ),
    (
        'Proceso Sospechoso',
        'HR-05 -- Proceso sospechoso: el proceso responsable del evento de archivo (atribuido vía agent/adapters/) se ejecuta desde una ubicación atípica (carpeta temporal, carpeta de usuario, ruta no habitual) -- 1 o más coincidencias dentro de una ventana de 30 segundos.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'PROCESOS_SOSPECHOSOS'),
        10.00, 1.00, 30, TRUE
    ),
    (
        'Consumo CPU Elevado',
        'HR-06 -- Consumo elevado de CPU por proceso: uso de CPU sostenido (no una lectura instantánea) por encima del umbral durante toda la ventana, con UNA alerta por episodio sostenido (se rearma solo tras una recuperación real por debajo del umbral). Señal secundaria -- nunca lleva por sí sola a CRÍTICO ni dispara aislamiento. El umbral (80%) es sobre la base de psutil.Process.cpu_percent(): 100% representa UN núcleo lógico completo, no la máquina entera -- un proceso multi-hilo real puede superar el 100% usando varios núcleos.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'CPU_PROCESO'),
        5.00, 80.00, 10, TRUE
    ),
    (
        'Acceso Recursos Compartidos',
        'HR-07 -- Acceso masivo a recursos compartidos: 20 o más operaciones sobre archivos en rutas compartidas/remotas dentro de una ventana de 15 segundos.',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACCESO_RECURSOS_COMPARTIDOS'),
        15.00, 20.00, 15, TRUE
    ),
    (
        'Creacion Masiva Temporales',
        'HR-08 -- Creación masiva de archivos temporales: 30 o más archivos temporales creados dentro de una ventana de 15 segundos. Señal secundaria.',
        (SELECT id FROM event_types WHERE name = 'file_created'),
        (SELECT id FROM metric_types WHERE name = 'CREACION_ARCHIVOS_TEMPORALES'),
        5.00, 30.00, 15, TRUE
    ),
    (
        'Eliminacion Anomala Archivos',
        'HR-09 -- Eliminación anómala: 20 o más archivos eliminados dentro de una ventana de 15 segundos. Especialmente relevante combinada con modificación/renombrado.',
        (SELECT id FROM event_types WHERE name = 'file_deleted'),
        (SELECT id FROM metric_types WHERE name = 'ELIMINACIONES_ARCHIVOS'),
        15.00, 20.00, 15, TRUE
    ),
    (
        'Actividad Archivos Usuario',
        'HR-10 -- Actividad repetitiva sobre archivos de usuario: 30 o más operaciones dentro de una ventana de 20 segundos sobre rutas de usuario (Documents, Desktop, Downloads, Pictures, etc.).',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_ARCHIVOS_USUARIO'),
        10.00, 30.00, 20, TRUE
    ),
    (
        'Actividad Repetitiva Automatizada',
        'HR-11 -- Actividad repetitiva automatizada: el MISMO proceso (por process_id atribuido) realiza 40 o más operaciones de archivo dentro de una ventana de 15 segundos -- distinto de HR-01/04 (que cuentan actividad del endpoint completo, sin distinguir proceso).',
        NULL,
        (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_AUTOMATIZADA_ARCHIVOS'),
        10.00, 40.00, 15, TRUE
    ),
    (
        'Correlacion Multiples Indicadores',
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

COMMIT;

-- ============================================================
-- Verificación -- correr después del script de arriba.
-- Esperado: 4 / 4 / 12 / 12 / 1.
-- ============================================================
SELECT
    (SELECT COUNT(*) FROM event_types)     AS event_types_n,
    (SELECT COUNT(*) FROM severity_levels) AS severity_levels_n,
    (SELECT COUNT(*) FROM metric_types)    AS metric_types_n,
    (SELECT COUNT(*) FROM heuristic_rules) AS heuristic_rules_n,
    (SELECT COUNT(*) FROM system_settings) AS system_settings_n;

-- No modifica roles/users/user_roles -- no hay ningún INSERT/UPDATE/
-- DELETE sobre esas tres tablas en todo este archivo.
