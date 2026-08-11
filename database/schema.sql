-- ============================================================
-- SISTEMA DE DETECCIÓN TEMPRANA DE RANSOMWARE
-- Esquema base de la base de datos (PostgreSQL)
-- Base de datos: ransomware_detection
--
-- Este archivo es el registro completo de las tablas tal como
-- ya existen en tu Postgres. Es la referencia para el Diccionario
-- de Datos de la tesis (Tarea 12) y para poder recrear la base
-- desde cero si alguna vez hace falta.
--
-- Si la base de datos "ransomware_detection" YA existe en tu
-- Postgres (que es el caso ahora mismo), NO vuelvas a correr este
-- archivo -- ya está aplicado. Lo que falta aplicar es
-- schema_updates.sql (ver ese archivo).
-- ============================================================

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

CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_id) REFERENCES roles(id),
    CONSTRAINT uq_user_roles
        UNIQUE (user_id, role_id)
);

CREATE TABLE enrollment_tokens (
    id BIGSERIAL PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_enrollment_tokens_created_by
        FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE agents (
    id BIGSERIAL PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    operating_system VARCHAR(50) NOT NULL,
    os_version VARCHAR(100),
    architecture VARCHAR(50),
    ip_address INET,
    agent_version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'OFFLINE',
    last_seen_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_credentials (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL UNIQUE,
    credential_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_agent_credentials_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE honeyfiles (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_type VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TIMESTAMP,
    CONSTRAINT fk_honeyfiles_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE honeyfile_activations (
    id BIGSERIAL PRIMARY KEY,
    honeyfile_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,
    operation VARCHAR(50) NOT NULL,
    process_id BIGINT,
    process_name VARCHAR(255),
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_honeyfile_activations_honeyfile
        FOREIGN KEY (honeyfile_id) REFERENCES honeyfiles(id),
    CONSTRAINT fk_honeyfile_activations_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    description TEXT,
    process_id BIGINT,
    process_name VARCHAR(255),
    metadata JSONB,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_events_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE heuristic_rules (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    indicator_type VARCHAR(100) NOT NULL,
    threshold INTEGER NOT NULL,
    window_seconds INTEGER,
    weight INTEGER NOT NULL,
    severity VARCHAR(20) NOT NULL,
    auto_isolate BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    rule_id BIGINT,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    risk_score INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'NEW',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alerts_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_alerts_rule
        FOREIGN KEY (rule_id) REFERENCES heuristic_rules(id)
);

CREATE TABLE incidents (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    classification VARCHAR(50),
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    closed_by BIGINT,
    CONSTRAINT fk_incidents_alert
        FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_incidents_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_incidents_closed_by
        FOREIGN KEY (closed_by) REFERENCES users(id)
);

CREATE TABLE host_isolations (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL,
    incident_id BIGINT,
    isolation_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED',
    reason TEXT,
    requested_by BIGINT,
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    released_at TIMESTAMP,
    result TEXT,
    CONSTRAINT fk_host_isolations_agent
        FOREIGN KEY (agent_id) REFERENCES agents(id),
    CONSTRAINT fk_host_isolations_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_host_isolations_requested_by
        FOREIGN KEY (requested_by) REFERENCES users(id)
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id BIGINT,
    description TEXT,
    ip_address INET,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id)
);
