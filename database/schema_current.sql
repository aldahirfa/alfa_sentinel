-- ============================================================
-- ALFA-Sentinel -- Estructura ACTUAL de la base de datos
-- (ransomware_detection, PostgreSQL)
--
-- Este archivo NO se corre contra la base -- es un snapshot de
-- lectura, para tener toda la estructura en un solo lugar y
-- poder reestructurar con la foto completa delante. La base real
-- se arma en dos pasos (schema.sql + schema_updates.sql); esto es
-- el resultado de aplicar los dos, tabla por tabla, con los
-- constraints ya incorporados en el CREATE TABLE en vez de
-- separados en ALTER TABLE.
--
-- Última actualización: 2026-08-11 (después de Detecciones/Incidentes).
-- ============================================================


-- ================= Usuarios y acceso =================

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);
-- No hay catálogo fijo de roles -- cualquier admin puede crear un
-- usuario con un "role" nuevo (POST /users) y la tabla 'roles' se
-- llena ad hoc. Hoy en la práctica solo existe 'admin' (sembrado por
-- bootstrap_admin.py). No hay tabla de permisos granulares todavía
-- (ej. 'endpoint.isolate') -- el único gateo real en el código es
-- require_role('admin').

CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(id),
    CONSTRAINT uq_user_roles UNIQUE (user_id, role_id)
);

CREATE TABLE enrollment_tokens (
    id BIGSERIAL PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_enrollment_tokens_created_by FOREIGN KEY (created_by) REFERENCES users(id)
);


-- ================= Endpoints y agentes =================

CREATE TABLE agents (
    id BIGSERIAL PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    operating_system VARCHAR(50) NOT NULL,
    os_version VARCHAR(100),
    architecture VARCHAR(50),
    ip_address INET,
    agent_version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'OFFLINE'
        CHECK (status IN ('ONLINE', 'OFFLINE')),
    last_seen_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- No hay MAC address, usuario logueado en el equipo, ni uptime --
-- el agente no los reporta hoy (ver endpoint_detail.html, notas
-- honestas en la pestaña Información).

CREATE TABLE agent_credentials (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL UNIQUE,
    credential_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_agent_credentials_agent FOREIGN KEY (agent_id) REFERENCES agents(id)
);


-- ================= Honeyfiles =================

CREATE TABLE honeyfiles (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_type VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TIMESTAMP,
    CONSTRAINT fk_honeyfiles_agent FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE honeyfile_activations (
    id BIGSERIAL PRIMARY KEY,
    honeyfile_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,
    operation VARCHAR(50) NOT NULL,
    process_id BIGINT,
    process_name VARCHAR(255),
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_honeyfile_activations_honeyfile FOREIGN KEY (honeyfile_id) REFERENCES honeyfiles(id),
    CONSTRAINT fk_honeyfile_activations_agent FOREIGN KEY (agent_id) REFERENCES agents(id)
);
-- Nunca se inserta acá todavía -- el disparo de un honeyfile hoy
-- termina en 'alerts' (regla honeyfile_access), no en esta tabla.
-- process_id/process_name se heredan del mismo problema que 'events':
-- watchdog no expone qué proceso tocó el archivo.


-- ================= Eventos de archivo =================

CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    description TEXT,
    process_id BIGINT,
    process_name VARCHAR(255),
    metadata JSONB,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_events_agent FOREIGN KEY (agent_id) REFERENCES agents(id)
);
-- event_type real: solo file_created / file_modified / file_deleted /
-- file_renamed (lo que expone watchdog). process_id/process_name
-- siempre NULL hoy (ver PENDIENTES.md -- requiere Sysmon/auditd).
-- metadata guarda {file_path, extension}.

CREATE INDEX idx_events_agent_id ON events(agent_id);
CREATE INDEX idx_events_agent_detected ON events(agent_id, detected_at DESC);


-- ================= Motor heurístico =================

CREATE TABLE heuristic_rules (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    indicator_type VARCHAR(100) NOT NULL,
    threshold INTEGER NOT NULL,
    window_seconds INTEGER,
    weight INTEGER NOT NULL,
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('LOW', 'SUSPICIOUS', 'HIGH', 'CRITICAL')),
    auto_isolate BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Solo 2 filas sembradas hoy (las únicas que el agente implementa):
--   'mass_file_activity'  -- SUSPICIOUS, auto_isolate = FALSE
--   'honeyfile_access'    -- HIGH,       auto_isolate = FALSE
-- 'auto_isolate' existe en el schema pero ningún código lo lee
-- todavía -- no hay motor de umbrales ni ejecución de aislamiento
-- (ver PENDIENTES.md, sección Respuesta).


-- ================= Detecciones (alertas) =================

CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    rule_id BIGINT,
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('LOW', 'SUSPICIOUS', 'HIGH', 'CRITICAL')),
    title VARCHAR(150) NOT NULL,
    description TEXT,
    risk_score INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'NEW'
        CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'ESCALATED', 'CLOSED', 'FALSE_POSITIVE')),
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alerts_agent FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_alerts_rule FOREIGN KEY (rule_id) REFERENCES heuristic_rules(id)
);
-- 'details' guarda {file_count, last_file} para mass_file_activity.
-- 'status' es el ciclo de vida gestionable desde /detecciones
-- (PATCH /alerts/{id}/status). LOW existe en el CHECK pero el motor
-- nunca lo produce en la práctica (solo SUSPICIOUS/HIGH/CRITICAL).

CREATE INDEX idx_alerts_agent_id ON alerts(agent_id);
CREATE INDEX idx_alerts_rule_id ON alerts(rule_id);

CREATE TABLE alert_events (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    event_id BIGINT NOT NULL,
    CONSTRAINT fk_alert_events_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_alert_events_event FOREIGN KEY (event_id) REFERENCES events(id),
    CONSTRAINT uq_alert_events UNIQUE (alert_id, event_id)
);
-- Muchos-a-muchos: una alerta nace de varios eventos (todos los
-- archivos tocados en la ventana del analizador heurístico). Solo se
-- llena para alertas/eventos generados DESPUÉS de este cambio
-- (no es retroactivo).

CREATE INDEX idx_alert_events_alert_id ON alert_events(alert_id);
CREATE INDEX idx_alert_events_event_id ON alert_events(event_id);

CREATE TABLE alert_notes (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_notes_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_alert_notes_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_alert_notes_alert_id ON alert_notes(alert_id);


-- ================= Incidentes =================

CREATE TABLE incidents (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CONTAINED', 'CLOSED')),
    classification VARCHAR(50)
        CHECK (classification IS NULL OR classification IN (
            'CONFIRMED', 'POSSIBLE_THREAT', 'FALSE_POSITIVE',
            'LEGITIMATE_ACTIVITY', 'UNDETERMINED'
        )),
    assigned_to BIGINT,
    assigned_at TIMESTAMP,
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    closed_by BIGINT,
    CONSTRAINT fk_incidents_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_incidents_agent FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_incidents_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id),
    CONSTRAINT fk_incidents_closed_by FOREIGN KEY (closed_by) REFERENCES users(id)
);
-- 'alert_id' = la detección que originó el incidente (histórico,
-- NOT NULL). La lista completa de detecciones que integran el caso
-- vive en 'incident_alerts' -- un incidente sigue atado a un único
-- 'agent_id' (no hay forma real de representar varios endpoints por
-- incidente hoy). 'updated_at' no tiene trigger -- cada endpoint que
-- modifica el incidente lo pisa a mano.

CREATE INDEX idx_incidents_agent_id ON incidents(agent_id);
CREATE INDEX idx_incidents_alert_id ON incidents(alert_id);

CREATE TABLE incident_alerts (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL,
    alert_id BIGINT NOT NULL,
    CONSTRAINT fk_incident_alerts_incident FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_incident_alerts_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT uq_incident_alerts UNIQUE (incident_id, alert_id)
);
-- Muchos-a-muchos: un incidente puede agrupar varias detecciones
-- relacionadas del mismo endpoint (POST /incidents/{id}/alerts).
-- 'severity' y 'detection_count' de un incidente NO son columnas --
-- se derivan de esta tabla en tiempo de consulta (ver INCIDENT_CTE
-- en server/main.py): severity = la más alta entre las vinculadas.

CREATE INDEX idx_incident_alerts_incident_id ON incident_alerts(incident_id);
CREATE INDEX idx_incident_alerts_alert_id ON incident_alerts(alert_id);

CREATE TABLE incident_notes (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_incident_notes_incident FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_incident_notes_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_incident_notes_incident_id ON incident_notes(incident_id);


-- ================= Respuesta (aislamiento) =================

CREATE TABLE host_isolations (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    incident_id BIGINT,
    isolation_type VARCHAR(20) NOT NULL
        CHECK (isolation_type IN ('NETWORK', 'FULL')),
    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED'
        CHECK (status IN ('REQUESTED', 'EXECUTED', 'FAILED', 'RELEASED')),
    reason TEXT,
    requested_by BIGINT,
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    released_at TIMESTAMP,
    result TEXT,
    CONSTRAINT fk_host_isolations_agent FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_host_isolations_incident FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_host_isolations_requested_by FOREIGN KEY (requested_by) REFERENCES users(id)
);
-- Existe en el schema desde el diseño original pero NINGÚN endpoint
-- del servidor escribe acá todavía, y el agente no tiene ninguna
-- capacidad de aislar una red (ni ejecutar nada remoto en general --
-- agent/main.py es un script de una sola pasada, sin bucle de
-- comandos). /respuesta sigue siendo un placeholder honesto por eso.

CREATE INDEX idx_host_isolations_agent_id ON host_isolations(agent_id);


-- ================= Auditoría =================

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id BIGINT,
    description TEXT,
    ip_address INET,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES users(id)
);
-- Tabla de auditoría general -- tampoco se escribe todavía desde
-- ningún endpoint (las notas de analista en alert_notes/incident_notes
-- cumplen ese rol para Detecciones/Incidentes, pero no hay un registro
-- transversal de "quién hizo qué" en toda la app).

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
