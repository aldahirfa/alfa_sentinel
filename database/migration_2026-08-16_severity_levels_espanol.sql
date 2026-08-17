-- ============================================================
-- ALFA-Sentinel — Migración 2026-08-16
-- severity_levels.name -> español (BAJO/MEDIO/ALTO/CRÍTICO)
--
-- CONTEXTO: corrección arquitectónica pedida explícitamente ("si un
-- dato existe en un catálogo de PostgreSQL, ese dato es la fuente de
-- verdad del sistema"). Hasta ahora 'severity_levels.name' guardaba
-- NORMAL/SUSPICIOUS/HIGH/CRITICAL y una capa de traducción aparte en
-- Python/TypeScript (RISK_LABELS_ES, ALERT_SEVERITY_LABELS_ES en
-- server/main.py; SEVERITY_LABEL en frontend/src/lib/severity.ts)
-- convertía eso a español para mostrarlo en pantalla. Esa capa de
-- traducción se eliminó del código -- ahora 'severity_levels.name' ES
-- directamente lo que ve el usuario, de punta a punta (Postgres ->
-- FastAPI -> React), sin traducir nada en el medio.
--
-- QUÉ HACE ESTE ARCHIVO (y nada más que esto):
--   1. Renombra los 4 severity_levels.name: NORMAL->BAJO,
--      SUSPICIOUS->MEDIO, HIGH->ALTO, CRITICAL->CRÍTICO.
--   2. Rellena severity_levels.description SOLO donde esté vacía
--      (NULL o string vacío) -- si ya le pusiste una descripción
--      propia, no se pisa.
--   3. NO toca min_score/max_score (los rangos 0-24.99/25-49.99/
--      50-74.99/75-100 quedan exactamente igual).
--
-- NO TOCA: 'alerts.severity_id' ni ninguna otra tabla -- son FKs por
-- id, no por nombre, así que ninguna alerta/incidente/reporte
-- histórico se ve afectado por este rename. NO borra ni reinserta
-- filas -- todo es UPDATE sobre las 4 filas que ya existen, los ids
-- no cambian.
--
-- SEGURA DE CORRER MÁS DE UNA VEZ: la segunda vez, los UPDATE de
-- nombre no encuentran filas con el nombre viejo (porque ya se
-- renombraron) y no hacen nada.
--
-- IMPORTANTE -- orden de despliegue: corré esta migración ANTES de
-- desplegar la versión nueva de server/main.py (o durante una breve
-- ventana sin tráfico). El código nuevo ya espera BAJO/MEDIO/ALTO/
-- CRÍTICO en las consultas -- si el código nuevo corre contra la base
-- vieja (todavía en inglés) antes de aplicar esto, los filtros por
-- severidad y los conteos "críticos" van a devolver 0 (no van a
-- encontrar coincidencias), aunque nada se rompe ni se corrompe.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f migration_2026-08-16_severity_levels_espanol.sql
-- (o pegar todo el archivo en pgAdmin -> Query Tool -> Execute,
-- conectado a la base alfa_sentinel real)
--
-- Recomendado: hacé un respaldo antes (pg_dump) por costumbre, aunque
-- este script no borra nada.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Rename de los 4 nombres reales.
-- ------------------------------------------------------------
UPDATE severity_levels SET name = 'BAJO'    WHERE name = 'NORMAL';
UPDATE severity_levels SET name = 'MEDIO'   WHERE name = 'SUSPICIOUS';
UPDATE severity_levels SET name = 'ALTO'    WHERE name = 'HIGH';
UPDATE severity_levels SET name = 'CRÍTICO' WHERE name = 'CRITICAL';

-- ------------------------------------------------------------
-- 2. Descripciones -- solo si están vacías (NULL o '').
-- ------------------------------------------------------------
UPDATE severity_levels SET description = 'Actividad dentro de lo esperado -- sin indicios de comportamiento sospechoso.'
    WHERE name = 'BAJO' AND (description IS NULL OR description = '');
UPDATE severity_levels SET description = 'Actividad inusual que amerita revisión, sin señales claras de compromiso.'
    WHERE name = 'MEDIO' AND (description IS NULL OR description = '');
UPDATE severity_levels SET description = 'Comportamiento consistente con una amenaza activa -- requiere atención pronta.'
    WHERE name = 'ALTO' AND (description IS NULL OR description = '');
UPDATE severity_levels SET description = 'Evidencia fuerte de compromiso (p. ej. acceso a un honeyfile) -- requiere respuesta inmediata.'
    WHERE name = 'CRÍTICO' AND (description IS NULL OR description = '');

-- ------------------------------------------------------------
-- 3. Verificación -- debe mostrar las 4 filas en español, en orden
-- de min_score, con sus descripciones.
-- ------------------------------------------------------------
SELECT id, name, min_score, max_score, description FROM severity_levels ORDER BY min_score;

COMMIT;
