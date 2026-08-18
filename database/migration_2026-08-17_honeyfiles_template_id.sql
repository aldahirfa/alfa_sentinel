-- ============================================================
-- ALFA-Sentinel — Migración 2026-08-17
-- Agregar 'honeyfiles.template_id' (vínculo real con la plantilla que
-- originó cada instancia)
--
-- POR QUÉ EXISTE ESTE ARCHIVO: 'agent_honeyfile_templates' ya guarda
-- la relación (agente, plantilla) para el PROCESO de asignación, pero
-- la instancia real ('honeyfiles') no quedaba conectada a su origen.
-- Sin ese vínculo, el agente no tiene forma de recrear el contenido
-- de un honeyfile borrado, ni el servidor de comparar su hash contra
-- el de la plantilla que lo generó -- ambos necesarios para la
-- reconciliación en caliente (ver PENDIENTES.md, "Honeyfiles:
-- despliegue automático, rutas, integridad, reconciliación y
-- ejecución en tiempo real").
--
-- QUÉ HACE (y nada más que esto):
--   1. Agrega la columna 'template_id' (nullable -- filas existentes
--      quedan con NULL, no se inventa un valor para honeyfiles ya
--      creados antes de este cambio; seguirán funcionando, solo sin
--      poder recrearse automáticamente si se borran).
--   2. Agrega la FK hacia 'honeyfile_templates(id)'.
--   3. Agrega UNIQUE(agent_id, template_id) -- permite que el
--      servidor haga UPSERT en vez de duplicar una fila cada vez que
--      se re-verifica un honeyfile ya existente.
-- No borra ni modifica ninguna fila existente. No toca ninguna otra
-- tabla.
--
-- SEGURA DE CORRER MÁS DE UNA VEZ: los ALTER TABLE con
-- "IF NOT EXISTS" no fallan si ya se aplicó antes.
--
-- CÓMO APLICARLA:
--   psql -U <tu_usuario> -d alfa_sentinel -f migration_2026-08-17_honeyfiles_template_id.sql
-- ============================================================

BEGIN;

ALTER TABLE honeyfiles
    ADD COLUMN IF NOT EXISTS template_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_honeyfiles_template'
    ) THEN
        ALTER TABLE honeyfiles
            ADD CONSTRAINT fk_honeyfiles_template
                FOREIGN KEY (template_id)
                REFERENCES honeyfile_templates(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_honeyfiles_agent_template'
    ) THEN
        ALTER TABLE honeyfiles
            ADD CONSTRAINT uq_honeyfiles_agent_template
                UNIQUE (agent_id, template_id);
    END IF;
END $$;

-- Verificación: la columna y las dos restricciones deberían existir.
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'honeyfiles' AND column_name = 'template_id';

SELECT conname FROM pg_constraint
WHERE conname IN ('fk_honeyfiles_template', 'uq_honeyfiles_agent_template');

COMMIT;
