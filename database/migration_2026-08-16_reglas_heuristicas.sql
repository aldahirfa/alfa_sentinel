-- ============================================================
-- ALFA-Sentinel — Migración 2026-08-16 (v2, reescrita)
-- Reglas heurísticas + metric_types: nombres en español + created_at
--
-- Esta es una reescritura de la versión anterior de este archivo. La
-- v1 asumía que tu base no tenía metric_types ni heuristic_rules.
-- metric_type_id -- ASUNCIÓN INCORRECTA, confirmada con tu propio
-- \d metric_types / \d heuristic_rules: esas dos cosas YA EXISTEN en
-- tu base. Lo único que de verdad falta es la columna
-- heuristic_rules.created_at (por eso fallaba "Reglas Heurísticas no
-- se pudo cargar" -- GET /api/rules pide esa columna).
--
-- QUÉ HACE ESTE ARCHIVO (y nada más que esto):
--   1. Agrega heuristic_rules.created_at (única columna que falta).
--   2. Renombra los 12 heuristic_rules.name de tu base (que hoy están
--      en inglés, con nombres distintos a los del repo original --
--      ej. 'mass_file_modification' en vez de 'mass_file_activity')
--      a los nuevos nombres en español. SOLO toca la columna 'name'
--      -- no toca weight/threshold/window_seconds/is_active/
--      description/event_type_id/metric_type_id, que son tuyos y no
--      se pisan.
--   3. Renombra los 12 metric_types.name (inglés -> español) y de
--      paso corrige el texto corrupto (mojibake) de
--      metric_types.description que viste en tu SELECT (ej.
--      "archivos se±uelo" -> "archivos señuelo").
--   4. Rellena heuristic_rules.metric_type_id SOLO donde esté en NULL
--      (nunca pisa un valor que ya tengas puesto).
--
-- NO TOCA: usuarios, endpoints, agentes, alertas, alert_rule,
-- audit_logs, ni ninguna otra tabla. NO borra ni reinserta filas de
-- heuristic_rules/metric_types -- todo es UPDATE sobre las filas que
-- ya existen, así que los ids (y por lo tanto alert_rule.rule_id, que
-- apunta a esos ids) no cambian.
--
-- SEGURA DE CORRER MÁS DE UNA VEZ: la segunda vez, los UPDATE de
-- nombre no encuentran filas con el nombre viejo (porque ya se
-- renombraron) y no hacen nada; ADD COLUMN IF NOT EXISTS tampoco
-- repite trabajo.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f migration_2026-08-16_reglas_heuristicas.sql
-- (o pegar todo el archivo en pgAdmin -> Query Tool -> Execute,
-- conectado a la base alfa_sentinel real)
--
-- Recomendado: hacé un respaldo antes (pg_dump) por costumbre, aunque
-- este script no borra nada.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Columna que falta de verdad en tu base.
-- ------------------------------------------------------------
ALTER TABLE heuristic_rules ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;


-- ------------------------------------------------------------
-- 2. Renombrar heuristic_rules.name: de los nombres que tu base tiene
-- HOY (confirmados con tu SELECT id, name, ... ORDER BY id) a los
-- nuevos nombres en español. Un UPDATE por regla, matcheando por el
-- nombre actual -- si el nombre ya fue cambiado (segunda corrida),
-- el WHERE no encuentra nada y no pasa nada.
-- ------------------------------------------------------------
UPDATE heuristic_rules SET name = 'modificacion_masiva_archivos'      WHERE name = 'mass_file_modification';
UPDATE heuristic_rules SET name = 'renombrado_extension_anomala'      WHERE name = 'anomalous_file_rename';
UPDATE heuristic_rules SET name = 'acceso_honeyfile'                  WHERE name = 'honeyfile_access';
UPDATE heuristic_rules SET name = 'escritura_intensiva_archivos'      WHERE name = 'intensive_file_writing';
UPDATE heuristic_rules SET name = 'proceso_sospechoso'                WHERE name = 'suspicious_process_execution';
UPDATE heuristic_rules SET name = 'consumo_cpu_elevado'               WHERE name = 'high_process_cpu';
UPDATE heuristic_rules SET name = 'acceso_recursos_compartidos'       WHERE name = 'mass_shared_path_access';
UPDATE heuristic_rules SET name = 'creacion_masiva_temporales'        WHERE name = 'mass_temp_file_creation';
UPDATE heuristic_rules SET name = 'eliminacion_anomala_archivos'      WHERE name = 'anomalous_file_deletion';
UPDATE heuristic_rules SET name = 'actividad_archivos_usuario'        WHERE name = 'repetitive_user_file_activity';
UPDATE heuristic_rules SET name = 'actividad_repetitiva_automatizada' WHERE name = 'automated_file_activity';
UPDATE heuristic_rules SET name = 'correlacion_multiples_indicadores' WHERE name = 'multi_indicator_correlation';


-- ------------------------------------------------------------
-- 3. Renombrar metric_types.name (inglés -> español) y corregir el
-- texto corrupto de 'description' (mojibake -- los caracteres con
-- tilde/ñ quedaron mal codificados en algún punto). El texto de acá
-- es el mismo que ya usa database/schema.sql para instalaciones
-- nuevas, así que tu base queda igual a una instalación limpia.
-- ------------------------------------------------------------
UPDATE metric_types SET
    name = 'MODIFICACIONES_ARCHIVOS',
    description = 'Cantidad de archivos únicos modificados en la ventana'
    WHERE name = 'FILE_MODIFICATIONS';

UPDATE metric_types SET
    name = 'RENOMBRADOS_ARCHIVOS',
    description = 'Cantidad de renombrados con patrón/extensión anómala'
    WHERE name = 'FILE_RENAMES';

UPDATE metric_types SET
    name = 'ACCESO_HONEYFILE',
    description = 'Interacción detectada sobre un archivo señuelo'
    WHERE name = 'HONEYFILE_ACCESS';

UPDATE metric_types SET
    name = 'ESCRITURAS_ARCHIVOS',
    description = 'Cantidad total de operaciones de escritura/modificación'
    WHERE name = 'FILE_WRITES';

UPDATE metric_types SET
    name = 'PROCESOS_SOSPECHOSOS',
    description = 'Procesos con características sospechosas detectados'
    WHERE name = 'SUSPICIOUS_PROCESSES';

UPDATE metric_types SET
    name = 'CPU_PROCESO',
    description = 'Consumo de CPU sostenido por un proceso'
    WHERE name = 'PROCESS_CPU';

UPDATE metric_types SET
    name = 'ACCESO_RECURSOS_COMPARTIDOS',
    description = 'Operaciones sobre archivos en rutas/recursos compartidos'
    WHERE name = 'SHARED_PATH_ACCESS';

UPDATE metric_types SET
    name = 'CREACION_ARCHIVOS_TEMPORALES',
    description = 'Creación de archivos temporales'
    WHERE name = 'TEMP_FILE_CREATION';

UPDATE metric_types SET
    name = 'ELIMINACIONES_ARCHIVOS',
    description = 'Cantidad de archivos eliminados en la ventana'
    WHERE name = 'FILE_DELETIONS';

UPDATE metric_types SET
    name = 'ACTIVIDAD_ARCHIVOS_USUARIO',
    description = 'Actividad repetitiva sobre archivos de carpetas de usuario'
    WHERE name = 'USER_FILE_ACTIVITY';

UPDATE metric_types SET
    name = 'ACTIVIDAD_AUTOMATIZADA_ARCHIVOS',
    description = 'Operaciones repetitivas realizadas por un mismo proceso'
    WHERE name = 'AUTOMATED_FILE_ACTIVITY';

UPDATE metric_types SET
    name = 'CORRELACION_MULTIPLES_INDICADORES',
    description = 'Cantidad de reglas distintas activadas en el mismo episodio'
    WHERE name = 'MULTI_INDICATOR_CORRELATION';


-- ------------------------------------------------------------
-- 4. Rellenar heuristic_rules.metric_type_id SOLO donde esté vacío
-- (NULL). Si ya lo tenías cargado, esto no lo toca. Empareja por la
-- correspondencia 1:1 HR-01..HR-12 <-> metric_types (la misma que usa
-- database/schema.sql), usando los nombres YA renombrados en los
-- pasos 2 y 3 de arriba.
-- ------------------------------------------------------------
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'MODIFICACIONES_ARCHIVOS')
    WHERE name = 'modificacion_masiva_archivos' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'RENOMBRADOS_ARCHIVOS')
    WHERE name = 'renombrado_extension_anomala' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ACCESO_HONEYFILE')
    WHERE name = 'acceso_honeyfile' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ESCRITURAS_ARCHIVOS')
    WHERE name = 'escritura_intensiva_archivos' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'PROCESOS_SOSPECHOSOS')
    WHERE name = 'proceso_sospechoso' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'CPU_PROCESO')
    WHERE name = 'consumo_cpu_elevado' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ACCESO_RECURSOS_COMPARTIDOS')
    WHERE name = 'acceso_recursos_compartidos' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'CREACION_ARCHIVOS_TEMPORALES')
    WHERE name = 'creacion_masiva_temporales' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ELIMINACIONES_ARCHIVOS')
    WHERE name = 'eliminacion_anomala_archivos' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_ARCHIVOS_USUARIO')
    WHERE name = 'actividad_archivos_usuario' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'ACTIVIDAD_AUTOMATIZADA_ARCHIVOS')
    WHERE name = 'actividad_repetitiva_automatizada' AND metric_type_id IS NULL;
UPDATE heuristic_rules SET metric_type_id = (SELECT id FROM metric_types WHERE name = 'CORRELACION_MULTIPLES_INDICADORES')
    WHERE name = 'correlacion_multiples_indicadores' AND metric_type_id IS NULL;

COMMIT;


-- ------------------------------------------------------------
-- Verificación (corré esto después, por separado, para confirmar):
--   SELECT id, name, metric_type_id, created_at FROM heuristic_rules ORDER BY id;
--   -- esperado: 12 filas, todas con name en español, metric_type_id
--   -- no nulo, created_at con una fecha (la de hoy si nunca existió).
--
--   SELECT id, name, description, unit FROM metric_types ORDER BY id;
--   -- esperado: 12 filas, name en español, description en español
--   -- legible (sin ± ¾ Ý ni caracteres raros).
--
--   SELECT r.name AS regla, m.name AS metrica
--   FROM heuristic_rules r LEFT JOIN metric_types m ON m.id = r.metric_type_id
--   ORDER BY r.id;
--   -- esperado: cada regla con su métrica correspondiente, ninguna fila
--   -- con metrica en NULL.
-- ------------------------------------------------------------
