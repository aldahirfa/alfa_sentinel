-- Mejoras aditivas sobre schema.sql. No borra ni modifica datos.
-- Correr UNA sola vez, contra la base de datos ransomware_detection
-- que ya tienes creada:
--   psql -U postgres -d ransomware_detection -f schema_updates.sql

-- 1. Índices en columnas de llave foránea (Postgres no las indexa solas).
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_agent_detected ON events(agent_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_agent_id ON alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_alerts_rule_id ON alerts(rule_id);
CREATE INDEX IF NOT EXISTS idx_honeyfile_activations_agent_id ON honeyfile_activations(agent_id);
CREATE INDEX IF NOT EXISTS idx_honeyfile_activations_honeyfile_id ON honeyfile_activations(honeyfile_id);
CREATE INDEX IF NOT EXISTS idx_incidents_agent_id ON incidents(agent_id);
CREATE INDEX IF NOT EXISTS idx_incidents_alert_id ON incidents(alert_id);
CREATE INDEX IF NOT EXISTS idx_host_isolations_agent_id ON host_isolations(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

-- 2. Restricciones de valores válidos (evita typos silenciosos).
-- Postgres no soporta "ADD CONSTRAINT IF NOT EXISTS" -- se envuelve
-- cada una en un bloque DO que atrapa el error "ya existe"
-- (duplicate_object) y sigue de largo, para que el archivo se pueda
-- volver a correr sin miedo (como ya nos pasó con esta sección).
DO $$ BEGIN
    ALTER TABLE agents
        ADD CONSTRAINT chk_agents_status
        CHECK (status IN ('ONLINE', 'OFFLINE'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE alerts
        ADD CONSTRAINT chk_alerts_severity
        CHECK (severity IN ('LOW', 'SUSPICIOUS', 'HIGH', 'CRITICAL'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE alerts
        ADD CONSTRAINT chk_alerts_status
        CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'ESCALATED', 'CLOSED', 'FALSE_POSITIVE'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE heuristic_rules
        ADD CONSTRAINT chk_heuristic_rules_severity
        CHECK (severity IN ('LOW', 'SUSPICIOUS', 'HIGH', 'CRITICAL'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE incidents
        ADD CONSTRAINT chk_incidents_status
        CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CONTAINED', 'CLOSED'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE host_isolations
        ADD CONSTRAINT chk_host_isolations_status
        CHECK (status IN ('REQUESTED', 'EXECUTED', 'FAILED', 'RELEASED'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE host_isolations
        ADD CONSTRAINT chk_host_isolations_type
        CHECK (isolation_type IN ('NETWORK', 'FULL'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 3. Detalle de qué disparó cada alerta.
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS details JSONB;

-- 4. Sembrar las 2 reglas que el motor heurístico del agente ya implementa.
INSERT INTO heuristic_rules (
    name, description, indicator_type, threshold,
    window_seconds, weight, severity, auto_isolate
)
SELECT
    'mass_file_activity',
    'Modificación/creación/eliminación de muchos archivos únicos en una ventana corta de tiempo',
    'mass_activity', 20, 10, 30, 'SUSPICIOUS', FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM heuristic_rules WHERE name = 'mass_file_activity'
);

INSERT INTO heuristic_rules (
    name, description, indicator_type, threshold,
    window_seconds, weight, severity, auto_isolate
)
SELECT
    'honeyfile_access',
    'Acceso, modificación o eliminación de un archivo señuelo',
    'honeyfile', 1, NULL, 60, 'HIGH', FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM heuristic_rules WHERE name = 'honeyfile_access'
);

-- 5. Relación muchos-a-muchos entre alertas y los eventos que las
-- dispararon. Una alerta nace de VARIOS eventos (todos los archivos
-- tocados en la ventana del analizador), así que un FK simple en
-- 'alerts' no alcanza -- hace falta una tabla puente. El agente arma
-- esta lista con los event_id que el servidor le devolvió al reportar
-- cada evento (ver agent/heuristic_engine.py y agent/file_monitor.py).
CREATE TABLE IF NOT EXISTS alert_events (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    event_id BIGINT NOT NULL,
    CONSTRAINT fk_alert_events_alert
        FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_alert_events_event
        FOREIGN KEY (event_id) REFERENCES events(id),
    CONSTRAINT uq_alert_events
        UNIQUE (alert_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_events_alert_id ON alert_events(alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_event_id ON alert_events(event_id);

-- 6. Notas de analista sobre una detección (texto libre, con autor y
-- fecha). No existía ningún lugar para dejar constancia de "qué se
-- investigó" -- esto es justo eso, nada más.
CREATE TABLE IF NOT EXISTS alert_notes (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_notes_alert
        FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_alert_notes_user
        FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_alert_notes_alert_id ON alert_notes(alert_id);

-- 7. Relación muchos-a-muchos entre incidentes y las detecciones que
-- agrupan. Antes, 'incidents.alert_id' (NOT NULL) obligaba a que un
-- incidente naciera de una sola alerta -- correcto para "quién lo
-- disparó", pero no alcanza para armar un caso con varias detecciones
-- relacionadas (lo que pidió el usuario). 'alert_id' se conserva como
-- la detección que originó el incidente; esta tabla es la lista
-- completa (incluida esa primera) de detecciones que el analista fue
-- vinculando al caso.
CREATE TABLE IF NOT EXISTS incident_alerts (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL,
    alert_id BIGINT NOT NULL,
    CONSTRAINT fk_incident_alerts_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_incident_alerts_alert
        FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT uq_incident_alerts
        UNIQUE (incident_id, alert_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_alerts_incident_id ON incident_alerts(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_alert_id ON incident_alerts(alert_id);

-- 8. Responsable asignado y marca de tiempo de última modificación.
-- Ninguna de las dos columnas existía -- sin 'assigned_to' no había
-- forma real de mostrar "Responsable" en el incidente, y sin
-- 'updated_at' no se puede mostrar "Última actualización" porque
-- 'opened_at' nunca cambia después del INSERT inicial. 'updated_at'
-- no tiene trigger automático -- cada endpoint que modifique el
-- incidente (estado, clasificación, asignación) lo actualiza a mano.
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS assigned_to BIGINT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

DO $$ BEGIN
    ALTER TABLE incidents
        ADD CONSTRAINT fk_incidents_assigned_to
        FOREIGN KEY (assigned_to) REFERENCES users(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE incidents
        ADD CONSTRAINT chk_incidents_classification
        CHECK (classification IS NULL OR classification IN (
            'CONFIRMED', 'POSSIBLE_THREAT', 'FALSE_POSITIVE',
            'LEGITIMATE_ACTIVITY', 'UNDETERMINED'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 9. Notas de analista sobre un incidente (mismo patrón que
-- alert_notes -- constancia de la investigación, texto libre).
CREATE TABLE IF NOT EXISTS incident_notes (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_incident_notes_incident
        FOREIGN KEY (incident_id) REFERENCES incidents(id),
    CONSTRAINT fk_incident_notes_user
        FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_incident_notes_incident_id ON incident_notes(incident_id);
