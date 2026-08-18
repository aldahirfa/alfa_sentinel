-- ============================================================
-- ALFA-Sentinel -- 3 plantillas de honeyfile (2026-08-18)
--
-- Crea 3 filas en 'honeyfile_templates' -- exactamente lo mismo que
-- quedaría si las cargaras a mano desde la consola (Honeyfiles ->
-- "Desplegar", POST /api/honeyfiles/deploy en server/main.py): mismas
-- columnas, mismas convenciones de formato (file_type/operating_system
-- en MAYÚSCULAS, file_path con la ruta LÓGICA, no una ruta física).
--
--   name              file_name            file_type  ruta lógica
--   Dulce Trampa      Dulce_Trampa.pdf     PDF        DESKTOP
--   Ojito             Ojito.docx           DOCX       DOCUMENTS
--   No Me Toques      No_Me_Toques.txt     TXT        DOWNLOADS
--
-- auto_deploy = TRUE en las 3 -- no hace falta indicar agent_ids a
-- mano: la próxima vez que CUALQUIER agente (existente o nuevo) pida
-- GET /agent/honeyfile-policy, el servidor las asigna solas si el
-- sistema operativo del endpoint coincide con 'ALL' (ver ese endpoint
-- en server/main.py) -- no hace falta reiniciar nada del lado del
-- servidor. El agente las escribe en su próximo ciclo de sincronización
-- (agent/honeyfile_sync.py) y recién ahí aparecen filas reales en
-- 'agent_honeyfile_templates' (PENDING -> CREATED) y en 'honeyfiles'
-- (la instancia física real, con su hash) -- ver la explicación de esas
-- 4 tablas más arriba en esta conversación.
--
-- 'content' usa el mismo texto genérico por defecto que ya usa
-- server/main.py cuando el Wizard se deja sin contenido personalizado
-- -- no se inventa nada distinto de lo que vería un analista real
-- creando esto desde la consola. Si querés un texto de señuelo distinto
-- por archivo, cambiá el valor de 'content' antes de correr esto.
--
-- 'created_by' queda en NULL a propósito -- este script no sabe cuál es
-- tu user_id real en 'users' (la tabla no se toca ni se asume nada
-- sobre ella). Si querés que la plantilla quede asociada a tu usuario,
-- reemplazá NULL por (SELECT id FROM users WHERE username = 'TU_USUARIO')
-- en las 3 filas de abajo.
--
-- SEGURO DE CORRER MÁS DE UNA VEZ: 'honeyfile_templates' no tiene una
-- restricción UNIQUE sobre 'file_name' (ver database/schema.sql), así
-- que cada INSERT de abajo va condicionado a un NOT EXISTS -- si ya
-- existe una plantilla con ese 'file_name', no se duplica.
--
-- No se ejecutó nada de esto contra tu base real -- es un archivo para
-- correr vos (psql -f, o pegado en pgAdmin), igual que los anteriores.
-- ============================================================

BEGIN;

INSERT INTO honeyfile_templates
    (name, file_name, file_type, file_path, operating_system, content, auto_deploy, is_active, created_by)
SELECT
    'Dulce Trampa', 'Dulce_Trampa.pdf', 'PDF', 'DESKTOP', 'ALL',
    'Documento confidencial. No modificar ni distribuir sin autorización.',
    TRUE, TRUE, NULL
WHERE NOT EXISTS (
    SELECT 1 FROM honeyfile_templates WHERE file_name = 'Dulce_Trampa.pdf'
);

INSERT INTO honeyfile_templates
    (name, file_name, file_type, file_path, operating_system, content, auto_deploy, is_active, created_by)
SELECT
    'Ojito', 'Ojito.docx', 'DOCX', 'DOCUMENTS', 'ALL',
    'Documento confidencial. No modificar ni distribuir sin autorización.',
    TRUE, TRUE, NULL
WHERE NOT EXISTS (
    SELECT 1 FROM honeyfile_templates WHERE file_name = 'Ojito.docx'
);

INSERT INTO honeyfile_templates
    (name, file_name, file_type, file_path, operating_system, content, auto_deploy, is_active, created_by)
SELECT
    'No Me Toques', 'No_Me_Toques.txt', 'TXT', 'DOWNLOADS', 'ALL',
    'Documento confidencial. No modificar ni distribuir sin autorización.',
    TRUE, TRUE, NULL
WHERE NOT EXISTS (
    SELECT 1 FROM honeyfile_templates WHERE file_name = 'No_Me_Toques.txt'
);

COMMIT;

-- ============================================================
-- Verificación -- deberías ver las 3 filas, todas is_active=t y
-- auto_deploy=t.
-- ============================================================
SELECT id, name, file_name, file_type, file_path, operating_system, auto_deploy, is_active
FROM honeyfile_templates
WHERE file_name IN ('Dulce_Trampa.pdf', 'Ojito.docx', 'No_Me_Toques.txt')
ORDER BY id;
