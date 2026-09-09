CREATE TABLE network_incidents (
    incident_id TEXT PRIMARY KEY,
    operator TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    area TEXT NOT NULL,
    fault_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'resolved', 'cancelled')),
    cause TEXT,
    estimated_restoration TIMESTAMPTZ,
    source_system TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_incident_cell_status
    ON network_incidents (cell_id, status, updated_at DESC);

CREATE TABLE accounts (
    caller_ref TEXT PRIMARY KEY,
    data_balance_mb INTEGER NOT NULL CHECK (data_balance_mb >= 0),
    barred BOOLEAN NOT NULL,
    compensation_eligible BOOLEAN NOT NULL,
    source_system TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE call_sessions (
    call_id UUID PRIMARY KEY,
    caller_ref TEXT NOT NULL,
    area TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    language_pair TEXT NOT NULL,
    symptom TEXT NOT NULL,
    safe_transcript TEXT NOT NULL,
    consent BOOLEAN NOT NULL,
    tier TEXT NOT NULL,
    outcome TEXT NOT NULL,
    next_action TEXT,
    response TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE action_events (
    event_id BIGSERIAL PRIMARY KEY,
    call_id UUID NOT NULL REFERENCES call_sessions(call_id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    inputs_json JSONB NOT NULL,
    output_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_action_events_call ON action_events (call_id, event_id);

CREATE TABLE complaint_signals (
    signal_id UUID PRIMARY KEY,
    call_id UUID NOT NULL UNIQUE REFERENCES call_sessions(call_id) ON DELETE CASCADE,
    caller_ref TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    symptom TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_signal_cluster
    ON complaint_signals (cell_id, symptom, created_at DESC);

CREATE TABLE candidate_incidents (
    candidate_id UUID PRIMARY KEY,
    cell_id TEXT NOT NULL,
    symptom TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unconfirmed', 'confirmed', 'dismissed')),
    evidence_count INTEGER NOT NULL CHECK (evidence_count > 0),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cell_id, symptom)
);

CREATE TABLE tickets (
    ticket_id UUID PRIMARY KEY,
    call_id UUID NOT NULL UNIQUE REFERENCES call_sessions(call_id) ON DELETE CASCADE,
    caller_ref TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    symptom TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'resolved')),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE compensation_commands (
    command_id UUID PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    caller_ref TEXT NOT NULL,
    incident_id TEXT NOT NULL REFERENCES network_incidents(incident_id),
    amount_mb INTEGER NOT NULL CHECK (amount_mb > 0),
    status TEXT NOT NULL CHECK (status IN ('queued', 'executing', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE callback_commands (
    command_id UUID PRIMARY KEY,
    caller_ref TEXT NOT NULL,
    trigger TEXT NOT NULL,
    incident_id TEXT REFERENCES network_incidents(incident_id),
    status TEXT NOT NULL CHECK (status IN ('queued', 'executing', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE NULLS NOT DISTINCT (caller_ref, trigger, incident_id)
);
