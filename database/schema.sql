-- ============================================================
-- ALFA-Sentinel
-- Esquema de base de datos (PostgreSQL)
-- Base de datos: alfa_sentinel
--
-- Reestructuración 2026-08-12: reemplaza la base anterior
-- "ransomware_detection" (el detalle de qué cambió y qué se dejó
-- afuera queda documentado en PENDIENTES.md).
-- Esta versión separa endpoint/agente, normaliza tipos de evento
-- y niveles de severidad en catálogos, y usa alerts.incident_id
-- como FK directa en vez de una tabla puente.
--
-- Decisión explícita del autor: se recrea la base desde cero (sin
-- migrar datos de la base anterior) y se adopta esta estructura
-- tal cual, sin reintroducir alert_events / alert_notes /
-- incident_notes / incident_alerts / incidents.assigned_to, que
-- existían en la base anterior. Ver PENDIENTES.md para el detalle
-- de qué funcionalidad quedó afuera y por qué.
--
-- Cómo aplicar (una sola vez, desde psql o pgAdmin):
--   1. CREATE DATABASE alfa_sentinel;
--   2. psql -U postgres -d alfa_sentinel -f schema.sql
--   3. cd server && python bootstrap_admin.py   (primer usuario admin)
-- ============================================================


-- ============================================================
-- 1. ENDPOINTS
-- ============================================================
CREATE TABLE endpoints (
    id              BIGSERIAL PRIMARY KEY,
    hostname        VARCHAR(255) NOT NULL,
    os              VARCHAR(100) NOT NULL,
    os_version      VARCHAR(100),
    ip_address      INET,
    status          VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. AGENTS
-- ============================================================
CREATE TABLE agents (
    id              BIGSERIAL PRIMARY KEY,
    endpoint_id     BIGINT NOT NULL,
    agent_version   VARCHAR(50) NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    last_seen_at    TIMESTAMPTZ,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agents_endpoint
        FOREIGN KEY (endpoint_id)
        REFERENCES endpoints(id)
);

-- ============================================================
-- 3. AGENT CREDENTIALS
-- ============================================================
CREATE TABLE agent_credentials (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    credential_hash TEXT NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_credentials_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
);

-- ============================================================
-- 4. USERS
-- ============================================================
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. ROLES
-- ============================================================
CREATE TABLE roles (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT
);

-- ============================================================
-- 6. USER ROLES
-- ============================================================
CREATE TABLE user_roles (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    role_id         BIGINT NOT NULL,
    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_id)
        REFERENCES roles(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_user_role
        UNIQUE (user_id, role_id)
);

-- ============================================================
-- 7. EVENT TYPES
-- ============================================================
CREATE TABLE event_types (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    category        VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 8. SEVERITY LEVELS
-- ============================================================
CREATE TABLE severity_levels (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    min_score       NUMERIC(6,2) NOT NULL,
    max_score       NUMERIC(6,2) NOT NULL,
    CONSTRAINT chk_severity_score_range
        CHECK (
            min_score >= 0
            AND max_score >= min_score
        )
);

-- ============================================================
-- 9. ENROLLMENT TOKENS
-- ============================================================
CREATE TABLE enrollment_tokens (
    id              BIGSERIAL PRIMARY KEY,
    token_hash      TEXT NOT NULL UNIQUE,
    created_by      BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,
    status          VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_enrollment_tokens_user
        FOREIGN KEY (created_by)
        REFERENCES users(id)
);

-- ============================================================
-- 10. HONEYFILES
-- ============================================================
CREATE TABLE honeyfiles (
    id                  BIGSERIAL PRIMARY KEY,
    agent_id            BIGINT NOT NULL,
    file_path           TEXT NOT NULL,
    file_name           VARCHAR(255) NOT NULL,
    file_type           VARCHAR(100),
    file_hash           VARCHAR(128),
    status              VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at      TIMESTAMPTZ,
    CONSTRAINT fk_honeyfiles_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
);

-- ============================================================
-- 11. EVENTS
-- ============================================================
CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    event_type_id   BIGINT NOT NULL,
    process_id      BIGINT,
    process_name    VARCHAR(255),
    file_path       TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_events_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id),
    CONSTRAINT fk_events_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES event_types(id)
);

-- ============================================================
-- 12. HONEYFILE ACTIVATIONS
-- ============================================================
CREATE TABLE honeyfile_activations (
    id              BIGSERIAL PRIMARY KEY,
    honeyfile_id    BIGINT NOT NULL,
    agent_id        BIGINT NOT NULL,
    operation       VARCHAR(50) NOT NULL,
    process_name    VARCHAR(255),
    process_id      BIGINT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_honeyfile_activations_honeyfile
        FOREIGN KEY (honeyfile_id)
        REFERENCES honeyfiles(id),
    CONSTRAINT fk_honeyfile_activations_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
);

-- ============================================================
-- 13. HEURISTIC RULES
-- ============================================================
CREATE TABLE heuristic_rules (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL UNIQUE,
    description     TEXT,
    event_type_id   BIGINT,
    weight          NUMERIC(6,2) NOT NULL,
    threshold       NUMERIC(6,2) NOT NULL,
    window_seconds  INTEGER,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_heuristic_rules_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES event_types(id),
    CONSTRAINT chk_heuristic_rule_weight
        CHECK (weight >= 0),
    CONSTRAINT chk_heuristic_rule_threshold
        CHECK (threshold >= 0),
    CONSTRAINT chk_heuristic_rule_window
        CHECK (
            window_seconds IS NULL
            OR window_seconds > 0
        )
);

-- ============================================================
-- 14. AGENT RULE
-- ============================================================
CREATE TABLE agent_rule (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    rule_id         BIGINT NOT NULL,
    threshold       NUMERIC(6,2),
    window_seconds  INTEGER,
    weight          NUMERIC(6,2),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_agent_rule_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_rule_rule
        FOREIGN KEY (rule_id)
        REFERENCES heuristic_rules(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_agent_rule
        UNIQUE (agent_id, rule_id),
    CONSTRAINT chk_agent_rule_threshold
        CHECK (
            threshold IS NULL
            OR threshold >= 0
        ),
    CONSTRAINT chk_agent_rule_weight
        CHECK (
            weight IS NULL
            OR weight >= 0
        ),
    CONSTRAINT chk_agent_rule_window
        CHECK (
            window_seconds IS NULL
            OR window_seconds > 0
        )
);
-- No se siembra ninguna fila acá: hoy el agente aplica threshold/
-- window_seconds/weight fijos en su propio código (agent/file_monitor.py,
-- start_file_monitor()), no los pide al servidor. Esta tabla queda
-- preparada para cuando el agente los consulte por agente -- hasta
-- entonces no tiene datos reales y no debe mostrarse en la UI como si
-- ya aplicara.

-- ============================================================
-- 15. INCIDENTS
-- ============================================================
CREATE TABLE incidents (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    classification  VARCHAR(100),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at       TIMESTAMPTZ,
    assigned_to     BIGINT,
    assigned_at     TIMESTAMPTZ,
    CONSTRAINT fk_incidents_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id),
    CONSTRAINT fk_incidents_assigned_to
        FOREIGN KEY (assigned_to)
        REFERENCES users(id)
);
-- 'assigned_to'/'assigned_at' vueltos a agregar 2026-08-12: se habían
-- sacado al adoptar la estructura alfa_sentinel tal cual (ver
-- PENDIENTES.md, "Reestructuración de la base de datos"), pero se
-- pidió reintroducir la función de "Responsable" de verdad, no como
-- placeholder. 'updated_at' NO se reintroduce -- sigue sin haber
-- historial de cambios de estado (ver PENDIENTES.md, "Historial de
-- cambios de estado de un incidente"), esto es solo el analista
-- asignado.

-- ============================================================
-- 16. ALERTS
-- ============================================================
CREATE TABLE alerts (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    incident_id     BIGINT,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    severity_id     BIGINT NOT NULL,
    risk_score      NUMERIC(6,2) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'NEW',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMPTZ,
    CONSTRAINT fk_alerts_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id),
    CONSTRAINT fk_alerts_incident
        FOREIGN KEY (incident_id)
        REFERENCES incidents(id),
    CONSTRAINT fk_alerts_severity
        FOREIGN KEY (severity_id)
        REFERENCES severity_levels(id),
    CONSTRAINT chk_alert_risk_score
        CHECK (risk_score >= 0)
);

-- ============================================================
-- 17. ALERT RULE
-- ============================================================
CREATE TABLE alert_rule (
    id              BIGSERIAL PRIMARY KEY,
    alert_id        BIGINT NOT NULL,
    rule_id         BIGINT NOT NULL,
    weight_applied  NUMERIC(6,2) NOT NULL,
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_rule_alert
        FOREIGN KEY (alert_id)
        REFERENCES alerts(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_alert_rule_rule
        FOREIGN KEY (rule_id)
        REFERENCES heuristic_rules(id),
    CONSTRAINT chk_alert_rule_weight
        CHECK (weight_applied >= 0)
);

-- ============================================================
-- 18. HOST ISOLATIONS
-- ============================================================
CREATE TABLE host_isolations (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    incident_id     BIGINT NOT NULL,
    isolation_type  VARCHAR(50) NOT NULL,
    status          VARCHAR(50) NOT NULL,
    reason          TEXT,
    requested_by    BIGINT,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at     TIMESTAMPTZ,
    released_at     TIMESTAMPTZ,
    result          TEXT,
    CONSTRAINT fk_host_isolations_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id),
    CONSTRAINT fk_host_isolations_incident
        FOREIGN KEY (incident_id)
        REFERENCES incidents(id),
    CONSTRAINT fk_host_isolations_user
        FOREIGN KEY (requested_by)
        REFERENCES users(id)
);
-- Igual que en la base anterior: ningún endpoint del servidor escribe
-- acá todavía y el agente no tiene capacidad de aislar una red ni
-- ejecutar nada remoto (agent/main.py es de una sola pasada, sin
-- bucle de comandos). /respuesta sigue siendo un placeholder honesto.

-- ============================================================
-- 19. AUDIT LOGS
-- ============================================================
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT,
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100),
    entity_id       BIGINT,
    description     TEXT,
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
);
-- Tampoco se escribe todavía desde ningún endpoint.

-- ============================================================
-- 20. HONEYFILE TEMPLATES
--
-- "Qué debería existir": la definición de una trampa (nombre real,
-- tipo, contenido, ruta de destino, plataforma) separada de en qué
-- agente concreto se aplica. auto_deploy = TRUE significa "cualquier
-- endpoint cuyo SO coincida la recibe sola, sin que nadie la asigne
-- a mano" -- el agente la descubre la próxima vez que corre (ver
-- GET /agent/honeyfile-policy en server/main.py), no en el momento
-- en que se crea la plantilla.
-- ============================================================
CREATE TABLE honeyfile_templates (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(150) NOT NULL,
    file_name           VARCHAR(255) NOT NULL,
    file_type           VARCHAR(20) NOT NULL,
    file_path           TEXT NOT NULL,
    operating_system    VARCHAR(20) NOT NULL DEFAULT 'ALL',
    content             TEXT NOT NULL,
    auto_deploy         BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          BIGINT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_honeyfile_templates_user
        FOREIGN KEY (created_by)
        REFERENCES users(id),
    CONSTRAINT chk_honeyfile_templates_os
        CHECK (operating_system IN ('WINDOWS', 'LINUX', 'ALL'))
);
-- El contenido es texto plano guardado con la extensión elegida (no
-- un .xlsx/.docx/.pdf válido de verdad): generar binarios reales de
-- Office requeriría sumar librerías nuevas al agente (openpyxl,
-- python-docx, etc.), y para el alcance de esta tesis no aporta nada
-- que el watchdog o la detección de honeyfile necesiten -- ambos
-- reaccionan a que el archivo exista y se lo toque, no a que se abra
-- correctamente en Word/Excel. Ver PENDIENTES.md.

-- ============================================================
-- 21. AGENT HONEYFILE TEMPLATES
--
-- "En qué agente debería existir": une una plantilla con un agente
-- concreto y trackea si ese agente ya la creó de verdad. Sirve tanto
-- para asignaciones manuales (Wizard de Despliegue -> se insertan acá
-- directo) como para las automáticas (auto_deploy=TRUE -> el propio
-- servidor inserta la fila la primera vez que ese agente pide su
-- política, en vez de tener que sembrar de antemano una fila por
-- cada agente que todavía no existe).
-- ============================================================
CREATE TABLE agent_honeyfile_templates (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        BIGINT NOT NULL,
    template_id     BIGINT NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_aht_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_aht_template
        FOREIGN KEY (template_id)
        REFERENCES honeyfile_templates(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_agent_honeyfile_template
        UNIQUE (agent_id, template_id),
    CONSTRAINT chk_aht_status
        CHECK (status IN ('PENDING', 'CREATED', 'FAILED'))
);
-- status: PENDING (todavía no se lo pedimos al agente o se lo
-- pedimos y no contestó), CREATED (el agente confirmó que el archivo
-- existe -- en ese momento se crea la fila real en 'honeyfiles'),
-- FAILED (el agente lo intentó y no pudo, ej. la carpeta destino no
-- existe -- se reintenta en la próxima política, no queda colgado).

-- ============================================================
-- 22. REPORTS
--
-- Bitácora de trazabilidad de informes generados -- no el archivo
-- pesado en sí (eso vive en disco, en server/generated_reports/),
-- solo los metadatos de auditoría: quién lo generó, cuándo, con qué
-- rango/filtro y en qué formato. 'file_path' guarda la ruta del
-- archivo ya generado para que "Descargar" sirva exactamente la
-- misma copia auditada, no una regenerada con datos más nuevos.
-- ============================================================
CREATE TABLE reports (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    report_type     VARCHAR(50) NOT NULL,
    format          VARCHAR(10) NOT NULL,
    period_label    VARCHAR(50) NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    endpoint_id     BIGINT,
    generated_by    BIGINT,
    file_path       VARCHAR(500) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reports_endpoint
        FOREIGN KEY (endpoint_id)
        REFERENCES endpoints(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_reports_user
        FOREIGN KEY (generated_by)
        REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT chk_reports_type
        CHECK (report_type IN ('SECURITY', 'ENDPOINTS', 'INCIDENTS')),
    CONSTRAINT chk_reports_format
        CHECK (format IN ('PDF', 'XLSX'))
);
-- 'endpoint_id' NULL = informe sobre todos los endpoints (no filtrado).
-- 'generated_by' NULL en el schema queda permitido para no romper el
-- registro si algún día se borra el usuario que lo generó (ON DELETE
-- SET NULL), pero en la práctica /reportes/generar siempre lo llena
-- con el usuario de la sesión -- no existe generación automática/por
-- sistema todavía (ver PENDIENTES.md).

-- ============================================================
-- 23. SYSTEM SETTINGS
--
-- Parámetros globales editables desde /configuracion, key-value en
-- vez de columnas sueltas para no tener que migrar el schema cada vez
-- que se agregue uno nuevo. A propósito arranca con un solo valor
-- real (agent_stale_seconds): es el único parámetro de "Configuración
-- > Agentes" que el servidor realmente vuelve a leer después de
-- guardarlo (reemplaza a la constante Python AGENT_STALE_SECONDS).
-- "Intervalo de Heartbeat" y "Sincronización de Reglas" NO tienen
-- fila acá -- no existe ningún mecanismo, ni en el agente ni en el
-- servidor, que los consuma (el agente manda heartbeat una sola vez
-- al arrancar, no en un loop; no hay sincronización de reglas en
-- absoluto). Se muestran en la UI como referencia/no aplicable, no
-- como settings editables, para no fabricar un control que no hace
-- nada. Ver PENDIENTES.md.
-- ============================================================
CREATE TABLE system_settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           VARCHAR(255) NOT NULL,
    description     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by      BIGINT,
    CONSTRAINT fk_system_settings_user
        FOREIGN KEY (updated_by)
        REFERENCES users(id)
        ON DELETE SET NULL
);

-- ============================================================
-- ÍNDICES
-- ============================================================
CREATE INDEX idx_agents_endpoint
    ON agents(endpoint_id);
CREATE INDEX idx_agents_last_seen
    ON agents(last_seen_at);
CREATE INDEX idx_events_agent
    ON events(agent_id);
CREATE INDEX idx_events_type
    ON events(event_type_id);
CREATE INDEX idx_events_detected_at
    ON events(detected_at);
CREATE INDEX idx_honeyfiles_agent
    ON honeyfiles(agent_id);
CREATE INDEX idx_honeyfile_activations_agent
    ON honeyfile_activations(agent_id);
CREATE INDEX idx_honeyfile_activations_honeyfile
    ON honeyfile_activations(honeyfile_id);
CREATE INDEX idx_honeyfile_activations_detected_at
    ON honeyfile_activations(detected_at);
CREATE INDEX idx_alerts_agent
    ON alerts(agent_id);
CREATE INDEX idx_alerts_incident
    ON alerts(incident_id);
CREATE INDEX idx_alerts_status
    ON alerts(status);
CREATE INDEX idx_alerts_created_at
    ON alerts(created_at);
CREATE INDEX idx_incidents_agent
    ON incidents(agent_id);
CREATE INDEX idx_incidents_status
    ON incidents(status);
CREATE INDEX idx_alert_rule_alert
    ON alert_rule(alert_id);
CREATE INDEX idx_alert_rule_rule
    ON alert_rule(rule_id);
CREATE INDEX idx_agent_rule_agent
    ON agent_rule(agent_id);
CREATE INDEX idx_agent_rule_rule
    ON agent_rule(rule_id);
CREATE INDEX idx_audit_logs_user
    ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at
    ON audit_logs(created_at);
CREATE INDEX idx_honeyfile_templates_auto_deploy
    ON honeyfile_templates(auto_deploy)
    WHERE is_active = TRUE;
CREATE INDEX idx_aht_agent
    ON agent_honeyfile_templates(agent_id);
CREATE INDEX idx_aht_template
    ON agent_honeyfile_templates(template_id);
CREATE INDEX idx_aht_status
    ON agent_honeyfile_templates(status);
CREATE INDEX idx_reports_created_at
    ON reports(created_at DESC);
CREATE INDEX idx_reports_type
    ON reports(report_type);
CREATE INDEX idx_reports_generated_by
    ON reports(generated_by);


-- ============================================================
-- DATOS SEMILLA
--
-- Solo catálogos que el sistema necesita para funcionar desde el
-- primer arranque. Nada de usuarios/agentes/endpoints -- esos se
-- crean con bootstrap_admin.py y con el enrolamiento real.
-- ============================================================

-- Rol admin: mismo nombre que bootstrap_admin.py espera encontrar
-- o crear (server/bootstrap_admin.py, ensure_admin_role()).
INSERT INTO roles (name, description) VALUES
    ('admin', 'Acceso total al sistema');

-- Los 4 tipos de evento que el agente realmente reporta hoy (vienen
-- de watchdog: on_created/on_modified/on_deleted/on_moved -- ver
-- agent/file_monitor.py). No existe "lectura de archivo": watchdog
-- no la expone, así que no se siembra ese tipo.
INSERT INTO event_types (name, description, category) VALUES
    ('file_created',  'Archivo creado',              'file'),
    ('file_modified', 'Archivo modificado',          'file'),
    ('file_deleted',  'Archivo eliminado',           'file'),
    ('file_renamed',  'Archivo renombrado o movido', 'file');

-- Bandas de severidad ancladas a los umbrales reales de
-- agent/heuristic_engine.py (FileActivityAnalyzer.get_risk_level()):
-- score < 30 -> NORMAL, 30-59 -> SUSPICIOUS, 60-79 -> HIGH, 80+ -> CRITICAL.
-- El motor nunca envía una alerta con score < 30 (is_suspicious()
-- filtra eso), así que NORMAL no se ve nunca en 'alerts' en la
-- práctica -- se siembra igual porque el CHECK de heuristic_rules
-- y el resto del sistema pueden necesitar referenciarla.
INSERT INTO severity_levels (name, min_score, max_score) VALUES
    ('NORMAL',     0.00,  29.99),
    ('SUSPICIOUS', 30.00, 59.99),
    ('HIGH',       60.00, 79.99),
    ('CRITICAL',   80.00, 100.00);

-- Primer par de reglas del motor heurístico (2 más se agregan más
-- abajo). weight/threshold/window_seconds son los valores por defecto
-- reales de FileActivityAnalyzer.__init__() (agent/heuristic_engine.py):
-- mass_activity_score=30/threshold=20 archivos/window=10s;
-- honeyfile_score=60/window=60s. honeyfile_access no tiene un
-- "threshold" real (se dispara con un solo toque al señuelo) -- se
-- guarda como 1 para respetar el NOT NULL de la columna sin inventar
-- un umbral que el agente no aplica. event_type_id queda NULL en
-- ambas: ninguna de las dos reglas depende de un único tipo de
-- evento (mass_file_activity mira cualquier combinación dentro de la
-- ventana; honeyfile_access mira cualquier operación sobre el señuelo).
INSERT INTO heuristic_rules (name, description, event_type_id, weight, threshold, window_seconds) VALUES
    ('mass_file_activity', 'Modificación masiva de archivos en una ventana corta', NULL, 30.00, 20.00, 10),
    ('honeyfile_access',   'Actividad detectada sobre un archivo señuelo (honeyfile)', NULL, 60.00, 1.00, 60);

-- Dos reglas agregadas 2026-08-12 (agent/heuristic_engine.py,
-- FileActivityAnalyzer): ambas se apoyan solo en lo que watchdog
-- puede ver (tipo de evento + ruta/extensión), no en proceso ni
-- contenido del archivo -- ver PENDIENTES.md sobre esa limitación.
-- event_type_id sí queda seteado acá (a diferencia de las dos de
-- arriba) porque estas dos reglas evalúan un único tipo de evento
-- cada una: renombrados para la primera, borrados para la segunda.
INSERT INTO heuristic_rules (name, description, event_type_id, weight, threshold, window_seconds) VALUES
    (
        'ransomware_extension_rename',
        'Archivo renombrado a una extensión asociada a ransomware conocido (.locked, .encrypted, etc.)',
        (SELECT id FROM event_types WHERE name = 'file_renamed'),
        70.00, 1.00, 30
    ),
    (
        'mass_deletion',
        'Ráfaga de borrados de archivos en una ventana corta',
        (SELECT id FROM event_types WHERE name = 'file_deleted'),
        40.00, 15.00, 10
    );

-- Único parámetro global real hoy (ver sección 23, SYSTEM SETTINGS).
-- 120s es el mismo valor que tenía la constante Python
-- AGENT_STALE_SECONDS que reemplaza.
INSERT INTO system_settings (key, value, description) VALUES
    (
        'agent_stale_seconds',
        '120',
        'Segundos sin heartbeat tras los cuales un agente ONLINE pasa a "sin señal reciente" (advertencia) en vez de contar como en línea.'
    );
