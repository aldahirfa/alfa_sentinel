-- ============================================================
-- ALFA-Sentinel — Corrección de nombres en heuristic_rules (2026-08-16)
--
-- POR QUÉ EXISTE ESTE ARCHIVO: al re-sembrar los catálogos a mano
-- después del TRUNCATE, 'heuristic_rules.name' se insertó en formato
-- "Título Con Espacios" (ej. 'Acceso Honeyfile'). El resto de
-- 'heuristic_rules.name' (a diferencia de 'severity_levels.name', que
-- SÍ es puro texto de presentación) funciona además como identificador
-- interno: el agente (agent/heuristic_engine.py) manda literalmente
-- 'acceso_honeyfile', 'modificacion_masiva_archivos', etc. en
-- matched_rules, y el servidor (server/main.py) los compara con
-- 'WHERE heuristic_rules.name = ...' en varios lugares (validación de
-- POST /agent/alerts, detección de honeyfile, STRONG_RULE_NAMES/
-- DEFERRED_RULE_NAMES/FIXED_SCORING_RULE_NAMES). Con el nombre en
-- "Título Con Espacios" ninguna de esas comparaciones matchea -- de
-- ahí el 422 "Ninguna de las reglas reportadas es una regla activa
-- conocida" al reportar la alerta del honeyfile.
--
-- QUÉ HACE: renombra las 12 filas de 'heuristic_rules' de vuelta al
-- identificador snake_case exacto que usan el agente y el servidor.
-- No toca 'description'/'weight'/'threshold'/'window_seconds'/
-- 'is_active'/'event_type_id'/'metric_type_id' -- todo eso queda
-- exactamente como lo cargaste. Tampoco toca 'metric_types.name'
-- (ese sí es puro texto de presentación, nunca se compara por código,
-- tu "Modificaciones Archivos" etc. está bien tal cual).
--
-- SEGURO DE CORRER MÁS DE UNA VEZ: cada UPDATE busca por el nombre
-- viejo; si ya se corrió antes, no encuentra filas y no hace nada.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f fix_nombres_heuristic_rules_2026-08-16.sql
-- ============================================================

BEGIN;

UPDATE heuristic_rules SET name = 'modificacion_masiva_archivos'      WHERE name = 'Modificacion Masiva Archivos';
UPDATE heuristic_rules SET name = 'renombrado_extension_anomala'      WHERE name = 'Renombrado Extension Anomala';
UPDATE heuristic_rules SET name = 'acceso_honeyfile'                  WHERE name = 'Acceso Honeyfile';
UPDATE heuristic_rules SET name = 'escritura_intensiva_archivos'      WHERE name = 'Escritura Intensiva Archivos';
UPDATE heuristic_rules SET name = 'proceso_sospechoso'                WHERE name = 'Proceso Sospechoso';
UPDATE heuristic_rules SET name = 'consumo_cpu_elevado'               WHERE name = 'Consumo CPU Elevado';
UPDATE heuristic_rules SET name = 'acceso_recursos_compartidos'       WHERE name = 'Acceso Recursos Compartidos';
UPDATE heuristic_rules SET name = 'creacion_masiva_temporales'        WHERE name = 'Creacion Masiva Temporales';
UPDATE heuristic_rules SET name = 'eliminacion_anomala_archivos'      WHERE name = 'Eliminacion Anomala Archivos';
UPDATE heuristic_rules SET name = 'actividad_archivos_usuario'        WHERE name = 'Actividad Archivos Usuario';
UPDATE heuristic_rules SET name = 'actividad_repetitiva_automatizada' WHERE name = 'Actividad Repetitiva Automatizada';
UPDATE heuristic_rules SET name = 'correlacion_multiples_indicadores' WHERE name = 'Correlacion Multiples Indicadores';

-- Verificación: deberían salir los 12 nombres en snake_case.
SELECT id, name, is_active FROM heuristic_rules ORDER BY id;

COMMIT;
