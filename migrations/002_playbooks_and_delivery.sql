CREATE TABLE troubleshooting_playbooks (
    playbook_id UUID PRIMARY KEY,
    issue_type TEXT NOT NULL,
    title TEXT NOT NULL,
    steps_json JSONB NOT NULL,
    language_pair TEXT,
    operator TEXT,
    device_os TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'retired')),
    source_system TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE NULLS NOT DISTINCT (
        issue_type, language_pair, operator, device_os, version
    )
);

CREATE INDEX idx_playbook_lookup
    ON troubleshooting_playbooks (
        issue_type, status, language_pair, operator, device_os, version DESC
    );

ALTER TABLE compensation_commands
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN last_error TEXT,
    ADD COLUMN external_reference TEXT,
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE callback_commands
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN last_error TEXT,
    ADD COLUMN external_reference TEXT,
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
