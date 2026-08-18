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
    description     TEXT,
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
    template_id          BIGINT,
    CONSTRAINT fk_honeyfiles_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(id)
);
-- 'template_id' agregado 2026-08-17 (ver PENDIENTES.md, "Honeyfiles:
-- despliegue automático, rutas, integridad, reconciliación y
-- ejecución en tiempo real") -- nullable a propósito (columna
-- agregada después de que la tabla ya tenía filas reales en
-- instalaciones existentes, mismo criterio que
-- heuristic_rules.metric_type_id más arriba). Sin este vínculo, no
-- había forma de recrear el contenido de un honeyfile borrado ni de
-- comparar su hash contra el de la plantilla que lo originó --
-- 'agent_honeyfile_templates' ya guardaba esa relación para el
-- PROCESO de asignación, pero la instancia real ('honeyfiles') no
-- quedaba conectada a su origen. La FK y el UNIQUE(agent_id,
-- template_id) se agregan más abajo (sección 20B), vía ALTER TABLE,
-- porque 'honeyfile_templates' todavía no existe en este punto del
-- script -- exactamente como pasó en la base real (se agregó con
-- ALTER TABLE, no se pudo declarar inline).

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
-- 12B. METRIC TYPES
--
-- Agregada junto con la reescritura del motor heurístico
-- (2026-08-16, ver PENDIENTES.md) para separar "qué ocurrió"
-- (event_types: file_created/modified/deleted/renamed) de "qué se
-- está midiendo" (metric_types: MODIFICACIONES_ARCHIVOS, CPU_PROCESO,
-- etc.) -- varias reglas heurísticas comparten el mismo event_type
-- pero miden cosas distintas (ej. HR-01 y HR-04 usan ambas
-- file_modified, pero HR-01 cuenta archivos únicos y HR-04 cuenta
-- operaciones totales). 'unit' vive acá y no se duplica en
-- heuristic_rules -- la UI la resuelve a través de esta tabla.
-- ============================================================
CREATE TABLE metric_types (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    unit            VARCHAR(30) NOT NULL
);

-- ============================================================
-- 13. HEURISTIC RULES
--
-- Orden de columnas: 'metric_type_id' y 'created_at' quedan al final
-- a propósito, coincidiendo con el orden físico real de la tabla en
-- la BD de producción (se agregaron ahí vía ALTER TABLE ADD COLUMN el
-- 2026-08-16, después de que la tabla ya existía con el resto de las
-- columnas -- ver PENDIENTES.md). No afecta ninguna consulta (todo el
-- código usa columnas por nombre, nunca por posición), pero mantiene
-- schema.sql como reflejo exacto de \d+ heuristic_rules real.
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
    metric_type_id  BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_heuristic_rules_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES event_types(id),
    CONSTRAINT fk_heuristic_rules_metric_type
        FOREIGN KEY (metric_type_id)
        REFERENCES metric_types(id),
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
-- No se siembra ninguna fila acá -- 'agent_rule' arranca vacía, cada
-- fila es un override puntual que un analista crea desde la consola
-- (Endpoints -> detalle de un endpoint -> "Configurar reglas de este
-- endpoint", ver frontend/src/components/AgentRulesModal.tsx) contra
-- PATCH /api/agents/{agent_id}/rules/{rule_id}. Un campo NULL en una
-- fila existente significa "heredar el valor global de heuristic_rules
-- para ese campo puntual" (override parcial); 'is_active' es la
-- excepción -- no admite NULL, así que la sola presencia de la fila ya
-- señala que ese endpoint tiene una personalización (ver
-- server/main.py::_effective_agent_rules_cte). El agente ya no aplica
-- threshold/window_seconds/weight fijos en su propio código: pide la
-- política EFECTIVA (global + override) vía GET /agent/rule-policy
-- (2026-08-16, ver PENDIENTES.md, "Implementación final del motor
-- heurístico y configuración por endpoint").

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
-- Real desde la corrección definitiva del motor heurístico
-- (2026-08-17, ver PENDIENTES.md, "Corrección definitiva del motor
-- heurístico, episodios, riesgo, severidad, alertas, incidentes y
-- aislamiento"): server/main.py::report_alert() inserta 'REQUESTED'
-- cuando corresponde aislar; agent/isolation_sync.py lo recoge
-- (GET /agent/isolation-status) y agent/isolation_executor.py lo
-- ejecuta de verdad (real solo si ALFA_SENTINEL_ENV=production y hay
-- privilegios reales; en development, el flujo completo se ejerce
-- igual pero la acción de red queda simulada), confirmando
-- 'EXECUTED'/'ISOLATION_FAILED' vía POST /agent/isolation-status/report.
-- 'status' sigue sin CHECK constraint (mismo criterio que el resto de
-- las columnas de estado en esta base) -- los valores válidos los fija
-- ISOLATION_STATUS_LABELS_ES en server/main.py: RECOMMENDED (legado),
-- REQUESTED, EXECUTED, ISOLATION_FAILED, RELEASED (liberar un
-- aislamiento ya aplicado queda fuera de alcance de esta tarea).

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
-- tipo, contenido, ubicación lógica, plataforma) separada de en qué
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
--
-- 'file_path' (2026-08-17, ver PENDIENTES.md, "Honeyfiles: despliegue
-- automático, rutas, integridad, reconciliación y ejecución en tiempo
-- real"): guarda una UBICACIÓN LÓGICA ('DOCUMENTS', 'DESKTOP',
-- 'DOWNLOADS', 'PICTURES', ver agent/paths.py), no una ruta
-- física de una máquina concreta -- el agente la resuelve a la carpeta
-- real según su propio sistema operativo y entorno (desarrollo vs
-- producción). Plantillas creadas antes de este cambio pueden seguir
-- teniendo una ruta con placeholders (%USERPROFILE%, $HOME, ~) -- el
-- resolver del agente sigue soportando ese formato como método
-- alternativo, no se rompe nada retroactivamente.

-- ============================================================
-- 20B. HONEYFILES -- FK a HONEYFILE_TEMPLATES (diferida)
--
-- No se pudo declarar inline en la sección 10 (CREATE TABLE
-- honeyfiles) porque esta tabla, 'honeyfile_templates', todavía no
-- existía en ese punto del script -- mismo motivo por el que en la
-- base real esto se agregó con ALTER TABLE, no al crear la tabla.
-- ============================================================
ALTER TABLE honeyfiles
    ADD CONSTRAINT fk_honeyfiles_template
        FOREIGN KEY (template_id)
        REFERENCES honeyfile_templates(id),
    ADD CONSTRAINT uq_honeyfiles_agent_template
        UNIQUE (agent_id, template_id);

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

-- Bandas de severidad -- rangos 0-24.99 / 25-49.99 / 50-74.99 / 75-100.
-- 'name' es BAJO/MEDIO/ALTO/CRÍTICO (renombrado 2026-08-16, corrección
-- arquitectónica: "si un dato existe en un catálogo de PostgreSQL, ese
-- dato es la fuente de verdad del sistema" -- ver PENDIENTES.md). Antes
-- 'name' guardaba NORMAL/SUSPICIOUS/HIGH/CRITICAL y una capa de
-- traducción aparte (RISK_LABELS_ES/ALERT_SEVERITY_LABELS_ES en
-- server/main.py, SEVERITY_LABEL en frontend/src/lib/severity.ts)
-- convertía eso a español para mostrarlo -- esa capa se eliminó
-- entera: ahora 'name' YA es el valor que ve el usuario, sin traducir,
-- de punta a punta (BD -> FastAPI -> React). Para una base ya
-- instalada con los valores viejos, ver
-- database/migration_2026-08-16_severity_levels_espanol.sql.
INSERT INTO severity_levels (name, min_score, max_score, description) VALUES
    ('BAJO',     0.00,  24.99,  'Actividad dentro de lo esperado -- sin indicios de comportamiento sospechoso.'),
    ('MEDIO',    25.00, 49.99,  'Actividad inusual que amerita revisión, sin señales claras de compromiso.'),
    ('ALTO',     50.00, 74.99,  'Comportamiento consistente con una amenaza activa -- requiere atención pronta.'),
    ('CRÍTICO',  75.00, 100.00, 'Evidencia fuerte de compromiso (p. ej. acceso a un honeyfile) -- requiere respuesta inmediata.');

-- ------------------------------------------------------------
-- METRIC TYPES -- qué mide cada regla (ver sección "12B" arriba).
-- Los 12 tipos de la especificación definitiva del motor heurístico.
-- ------------------------------------------------------------
INSERT INTO metric_types (name, description, unit) VALUES
    ('MODIFICACIONES_ARCHIVOS',        'Cantidad de archivos únicos modificados en la ventana', 'archivos'),
    ('RENOMBRADOS_ARCHIVOS',              'Cantidad de renombrados con patrón/extensión anómala', 'archivos'),
    ('ACCESO_HONEYFILE',          'Interacción detectada sobre un archivo señuelo', 'eventos'),
    ('ESCRITURAS_ARCHIVOS',               'Cantidad total de operaciones de escritura/modificación', 'operaciones'),
    ('PROCESOS_SOSPECHOSOS',      'Procesos con características sospechosas detectados', 'procesos'),
    ('CPU_PROCESO',               'Consumo de CPU sostenido por un proceso', '%'),
    ('ACCESO_RECURSOS_COMPARTIDOS',        'Operaciones sobre archivos en rutas/recursos compartidos', 'archivos'),
    ('CREACION_ARCHIVOS_TEMPORALES',        'Creación de archivos temporales', 'archivos'),
    ('ELIMINACIONES_ARCHIVOS',            'Cantidad de archivos eliminados en la ventana', 'archivos'),
    ('ACTIVIDAD_ARCHIVOS_USUARIO',        'Actividad repetitiva sobre archivos de carpetas de usuario', 'operaciones'),
    ('ACTIVIDAD_AUTOMATIZADA_ARCHIVOS',   'Operaciones repetitivas realizadas por un mismo proceso', 'operaciones'),
    ('CORRELACION_MULTIPLES_INDICADORES', 'Cantidad de reglas distintas activadas en el mismo episodio', 'reglas');

-- ------------------------------------------------------------
-- HEURISTIC RULES -- las 12 reglas de la especificación definitiva.
--
-- 'name' está en "Título Con Espacios" (2026-08-16, corrección: ver
-- PENDIENTES.md "Implementación final del motor heurístico..." --
-- se ajustó el código para coincidir con los nombres que ya existían
-- cargados a mano en la base real del usuario, en vez de forzar un
-- rename sobre esa base). Estos nombres son a la vez lo que se
-- muestra en la interfaz Y el identificador que compara el código
-- (server/main.py: STRONG_RULE_NAMES/DEFERRED_RULE_NAMES/
-- FIXED_SCORING_RULE_NAMES; agent/heuristic_engine.py: RULE_NAMES/
-- DEFAULT_RULES/matched.append(...)) -- si se cambia acá, hay que
-- cambiar ese código también, o pasan a no matchear nada.
--
-- HR-05 (Proceso Sospechoso), HR-06 (Consumo CPU Elevado) y HR-11
-- (Actividad Repetitiva Automatizada) se siembran con is_active=TRUE:
-- la implementación real de atribución de proceso (agent/adapters/),
-- muestreo de CPU por proceso (agent/cpu_monitor.py) y conteo de
-- actividad por proceso ya existen (2026-08-16, ver PENDIENTES.md).
-- weight/threshold/window son los que propone la especificación.
-- ------------------------------------------------------------

-- HR-01: event_type_id = file_modified (a diferencia de la versión
-- anterior, que no distinguía tipo de evento) porque la especificación
-- la define específicamente como "modificación masiva de archivos".
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
