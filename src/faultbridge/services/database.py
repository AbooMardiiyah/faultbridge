from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from faultbridge.domain.models import (
    AccountState,
    CallSession,
    Fault,
    Outcome,
    Tier,
    ToolEvent,
)


def json_safe(value: Any) -> Any:
    """Normalize typed tool values before storing them in JSONB."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def apply_migrations(database_url: str, directory: Path) -> list[str]:
    """Apply each immutable SQL migration once, in filename order."""
    applied: list[str] = []
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        for path in sorted(directory.glob("*.sql")):
            if path.name in existing:
                continue
            connection.execute(path.read_text(), prepare=False)
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (path.name,),
            )
            applied.append(path.name)
    return applied


class Database:
    """PostgreSQL store for operational state, commands, and audit events."""

    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 10):
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=True,
        )

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        with self.pool.connection() as connection:
            yield connection

    def close(self) -> None:
        self.pool.close()

    def is_ready(self) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 AS ready").fetchone()["ready"] == 1

    def upsert_incident(self, incident: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO network_incidents
                (incident_id, operator, cell_id, area, fault_type, status, cause,
                 estimated_restoration, source_system, source_reference, verified_at)
                VALUES
                (%(incident_id)s, %(operator)s, %(cell_id)s, %(area)s,
                 %(fault_type)s, %(status)s, %(cause)s,
                 %(estimated_restoration)s, %(source_system)s,
                 %(source_reference)s, %(verified_at)s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    operator = EXCLUDED.operator,
                    cell_id = EXCLUDED.cell_id,
                    area = EXCLUDED.area,
                    fault_type = EXCLUDED.fault_type,
                    status = EXCLUDED.status,
                    cause = EXCLUDED.cause,
                    estimated_restoration = EXCLUDED.estimated_restoration,
                    source_system = EXCLUDED.source_system,
                    source_reference = EXCLUDED.source_reference,
                    verified_at = EXCLUDED.verified_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                incident,
            )

    def upsert_account(self, account: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO accounts
                (caller_ref, data_balance_mb, barred, compensation_eligible,
                 source_system, source_reference, verified_at)
                VALUES
                (%(caller_ref)s, %(data_balance_mb)s, %(barred)s,
                 %(compensation_eligible)s, %(source_system)s,
                 %(source_reference)s, %(verified_at)s)
                ON CONFLICT (caller_ref) DO UPDATE SET
                    data_balance_mb = EXCLUDED.data_balance_mb,
                    barred = EXCLUDED.barred,
                    compensation_eligible = EXCLUDED.compensation_eligible,
                    source_system = EXCLUDED.source_system,
                    source_reference = EXCLUDED.source_reference,
                    verified_at = EXCLUDED.verified_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                account,
            )

    def upsert_playbook(self, playbook: dict[str, Any]) -> str:
        playbook_id = playbook.get("playbook_id") or str(uuid4())
        payload = {**playbook, "playbook_id": playbook_id}
        with self.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO troubleshooting_playbooks
                (playbook_id, issue_type, title, steps_json, language_pair,
                 operator, device_os, status, source_system, source_reference,
                 verified_at, version)
                VALUES
                (%(playbook_id)s, %(issue_type)s, %(title)s, %(steps_json)s,
                 %(language_pair)s, %(operator)s, %(device_os)s, %(status)s,
                 %(source_system)s, %(source_reference)s, %(verified_at)s,
                 %(version)s)
                ON CONFLICT
                (issue_type, language_pair, operator, device_os, version)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    steps_json = EXCLUDED.steps_json,
                    status = EXCLUDED.status,
                    source_system = EXCLUDED.source_system,
                    source_reference = EXCLUDED.source_reference,
                    verified_at = EXCLUDED.verified_at,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING playbook_id
                """,
                {**payload, "steps_json": Jsonb(payload["steps"])},
            ).fetchone()
        return str(row["playbook_id"])

    def find_playbook(
        self,
        issue_type: str,
        *,
        language_pair: str | None = None,
        operator: str | None = None,
        device_os: str | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT playbook_id, issue_type, title, steps_json, language_pair,
                       operator, device_os, source_system, source_reference,
                       verified_at, version
                FROM troubleshooting_playbooks
                WHERE issue_type = %s AND status = 'approved'
                  AND (language_pair IS NULL OR language_pair = %s)
                  AND (operator IS NULL OR operator = %s)
                  AND (device_os IS NULL OR device_os = %s)
                ORDER BY
                    (language_pair IS NOT NULL)::int
                  + (operator IS NOT NULL)::int
                  + (device_os IS NOT NULL)::int DESC,
                    version DESC, verified_at DESC
                LIMIT 1
                """,
                (issue_type, language_pair, operator, device_os),
            ).fetchone()
        if row:
            row["playbook_id"] = str(row["playbook_id"])
        return row

    def find_active_fault(self, cell_id: str) -> Fault | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT incident_id, operator, cell_id, area, fault_type, status,
                       cause, estimated_restoration, source_system,
                       source_reference, verified_at
                FROM network_incidents
                WHERE cell_id = %s AND status = 'active'
                ORDER BY verified_at DESC
                LIMIT 1
                """,
                (cell_id,),
            ).fetchone()
        return Fault(**row) if row else None

    def get_account(self, caller_ref: str) -> AccountState | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT caller_ref, data_balance_mb, barred,
                       compensation_eligible, source_system, source_reference,
                       verified_at
                FROM accounts WHERE caller_ref = %s
                """,
                (caller_ref,),
            ).fetchone()
        return AccountState(**row) if row else None

    def save_session(self, session: CallSession) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO call_sessions
                (call_id, caller_ref, area, cell_id, language_pair, symptom,
                 safe_transcript, consent, tier, outcome, next_action, response)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (call_id) DO UPDATE SET
                    tier = EXCLUDED.tier,
                    outcome = EXCLUDED.outcome,
                    next_action = EXCLUDED.next_action,
                    response = EXCLUDED.response,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session.call_id,
                    session.caller_ref,
                    session.area,
                    session.cell_id,
                    session.language_pair,
                    session.symptom,
                    session.safe_transcript,
                    session.consent,
                    session.tier.value,
                    session.outcome.value,
                    session.next_action,
                    session.response,
                ),
            )

    def get_session(self, call_id: str) -> CallSession | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM call_sessions WHERE call_id = %s", (call_id,)
            ).fetchone()
        if row is None:
            return None
        return CallSession(
            call_id=str(row["call_id"]),
            caller_ref=row["caller_ref"],
            area=row["area"],
            cell_id=row["cell_id"],
            language_pair=row["language_pair"],
            symptom=row["symptom"],
            safe_transcript=row["safe_transcript"],
            consent=row["consent"],
            tier=Tier(row["tier"]),
            outcome=Outcome(row["outcome"]),
            next_action=row["next_action"],
            response=row["response"],
        )

    def record_event(self, call_id: str, event: ToolEvent) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO action_events
                (call_id, tool, inputs_json, output_json, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    call_id,
                    event.tool,
                    Jsonb(json_safe(event.inputs)),
                    Jsonb(json_safe(event.output)),
                    event.created_at,
                ),
            )

    def queue_compensation(
        self,
        caller_ref: str,
        incident_id: str,
        amount_mb: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        command_id = str(uuid4())
        with self.connect() as connection:
            created = connection.execute(
                """
                INSERT INTO compensation_commands
                (command_id, idempotency_key, caller_ref, incident_id,
                 amount_mb, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'queued', %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING command_id, amount_mb, status
                """,
                (
                    command_id,
                    idempotency_key,
                    caller_ref,
                    incident_id,
                    amount_mb,
                    datetime.now(UTC),
                ),
            ).fetchone()
            row = (
                created
                or connection.execute(
                    """
                SELECT command_id, amount_mb, status
                FROM compensation_commands WHERE idempotency_key = %s
                """,
                    (idempotency_key,),
                ).fetchone()
            )
        return {**row, "command_id": str(row["command_id"]), "created": bool(created)}

    def schedule_callback(
        self, caller_ref: str, trigger: str, incident_id: str | None
    ) -> dict[str, Any]:
        command_id = str(uuid4())
        with self.connect() as connection:
            created = connection.execute(
                """
                INSERT INTO callback_commands
                (command_id, caller_ref, trigger, incident_id, status, created_at)
                VALUES (%s, %s, %s, %s, 'queued', %s)
                ON CONFLICT (caller_ref, trigger, incident_id) DO NOTHING
                RETURNING command_id, status
                """,
                (
                    command_id,
                    caller_ref,
                    trigger,
                    incident_id,
                    datetime.now(UTC),
                ),
            ).fetchone()
            row = (
                created
                or connection.execute(
                    """
                SELECT command_id, status FROM callback_commands
                WHERE caller_ref = %s AND trigger = %s
                  AND incident_id IS NOT DISTINCT FROM %s
                """,
                    (caller_ref, trigger, incident_id),
                ).fetchone()
            )
        return {**row, "command_id": str(row["command_id"]), "created": bool(created)}

    def create_ticket(
        self,
        call_id: str,
        caller_ref: str,
        cell_id: str,
        symptom: str,
        summary: str,
    ) -> str:
        ticket_id = str(uuid4())
        with self.connect() as connection:
            created = connection.execute(
                """
                INSERT INTO tickets
                (ticket_id, call_id, caller_ref, cell_id, symptom, summary,
                 status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)
                ON CONFLICT (call_id) DO NOTHING
                RETURNING ticket_id
                """,
                (
                    ticket_id,
                    call_id,
                    caller_ref,
                    cell_id,
                    symptom,
                    summary,
                    datetime.now(UTC),
                ),
            ).fetchone()
            row = (
                created
                or connection.execute(
                    "SELECT ticket_id FROM tickets WHERE call_id = %s", (call_id,)
                ).fetchone()
            )
        return str(row["ticket_id"])

    def record_signal(
        self,
        call_id: str,
        caller_ref: str,
        cell_id: str,
        symptom: str,
        window_minutes: int,
    ) -> int:
        now = datetime.now(UTC)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO complaint_signals
                (signal_id, call_id, caller_ref, cell_id, symptom, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (call_id) DO NOTHING
                """,
                (str(uuid4()), call_id, caller_ref, cell_id, symptom, now),
            )
            cutoff = now - timedelta(minutes=window_minutes)
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT caller_ref) AS count
                FROM complaint_signals
                WHERE cell_id = %s AND symptom = %s AND created_at >= %s
                """,
                (cell_id, symptom, cutoff),
            ).fetchone()
        return int(row["count"])

    def propose_candidate(self, cell_id: str, symptom: str, evidence_count: int) -> str:
        with self.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO candidate_incidents
                (candidate_id, cell_id, symptom, status, evidence_count, created_at)
                VALUES (%s, %s, %s, 'unconfirmed', %s, %s)
                ON CONFLICT (cell_id, symptom) DO UPDATE SET
                    evidence_count = GREATEST(
                        candidate_incidents.evidence_count,
                        EXCLUDED.evidence_count
                    ),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING candidate_id
                """,
                (str(uuid4()), cell_id, symptom, evidence_count, datetime.now(UTC)),
            ).fetchone()
        return str(row["candidate_id"])

    def list_events(self, call_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, call_id, tool, inputs_json, output_json, created_at
                FROM action_events WHERE call_id = %s ORDER BY event_id
                """,
                (call_id,),
            ).fetchall()
        return [{**row, "call_id": str(row["call_id"])} for row in rows]

    def list_candidates(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM candidate_incidents ORDER BY created_at DESC"
            ).fetchall()
        return [{**row, "candidate_id": str(row["candidate_id"])} for row in rows]

    def claim_compensation(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                WITH next_command AS (
                    SELECT command_id FROM compensation_commands
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE compensation_commands AS command
                SET status = 'executing',
                    attempt_count = attempt_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                FROM next_command
                WHERE command.command_id = next_command.command_id
                RETURNING command.*
                """
            ).fetchone()
        if row:
            row["command_id"] = str(row["command_id"])
        return row

    def claim_callback(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                WITH next_command AS (
                    SELECT command_id FROM callback_commands
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE callback_commands AS command
                SET status = 'executing',
                    attempt_count = attempt_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                FROM next_command
                WHERE command.command_id = next_command.command_id
                RETURNING command.*
                """
            ).fetchone()
        if row:
            row["command_id"] = str(row["command_id"])
        return row

    def finish_command(
        self,
        table: str,
        command_id: str,
        *,
        status: str,
        external_reference: str | None = None,
        error: str | None = None,
    ) -> None:
        allowed_tables = {"compensation_commands", "callback_commands"}
        if table not in allowed_tables:
            raise ValueError("unsupported command table")
        if status not in {"queued", "completed", "failed"}:
            raise ValueError("unsupported command status")
        query = f"""
            UPDATE {table}
            SET status = %s, external_reference = %s, last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE command_id = %s
        """
        with self.connect() as connection:
            connection.execute(
                query, (status, external_reference, error, command_id), prepare=False
            )

    def dashboard_snapshot(self) -> dict[str, Any]:
        with self.connect() as connection:
            calls = connection.execute(
                """
                SELECT call_id, area, cell_id, language_pair, symptom, tier,
                       outcome, response, created_at, updated_at
                FROM call_sessions ORDER BY created_at DESC LIMIT 25
                """
            ).fetchall()
            tickets = connection.execute(
                "SELECT * FROM tickets ORDER BY created_at DESC LIMIT 25"
            ).fetchall()
            compensation = connection.execute(
                """
                SELECT command_id, incident_id, amount_mb, status, attempt_count,
                       external_reference, created_at, updated_at
                FROM compensation_commands ORDER BY created_at DESC LIMIT 25
                """
            ).fetchall()
            callbacks = connection.execute(
                """
                SELECT command_id, trigger, incident_id, status, attempt_count,
                       external_reference, created_at, updated_at
                FROM callback_commands ORDER BY created_at DESC LIMIT 25
                """
            ).fetchall()
        for collection in (calls, tickets, compensation, callbacks):
            for row in collection:
                for key, value in tuple(row.items()):
                    if hasattr(value, "hex") and key.endswith("_id"):
                        row[key] = str(value)
        return {
            "calls": calls,
            "tickets": tickets,
            "compensation_commands": compensation,
            "callback_commands": callbacks,
            "candidate_incidents": self.list_candidates(),
        }

    def delete_caller_data(self, caller_ref: str) -> dict[str, int]:
        """Delete caller-linked operational records while retaining aggregates."""
        with self.connect() as connection:
            calls = connection.execute(
                "DELETE FROM call_sessions WHERE caller_ref = %s RETURNING call_id",
                (caller_ref,),
            ).fetchall()
            accounts = connection.execute(
                "DELETE FROM accounts WHERE caller_ref = %s RETURNING caller_ref",
                (caller_ref,),
            ).fetchall()
            compensation = connection.execute(
                """
                DELETE FROM compensation_commands WHERE caller_ref = %s
                RETURNING command_id
                """,
                (caller_ref,),
            ).fetchall()
            callbacks = connection.execute(
                """
                DELETE FROM callback_commands WHERE caller_ref = %s
                RETURNING command_id
                """,
                (caller_ref,),
            ).fetchall()
        return {
            "calls": len(calls),
            "accounts": len(accounts),
            "compensation_commands": len(compensation),
            "callback_commands": len(callbacks),
        }

    def purge_expired_calls(self, retention_days: int) -> int:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with self.connect() as connection:
            rows = connection.execute(
                """
                DELETE FROM call_sessions WHERE created_at < %s RETURNING call_id
                """,
                (cutoff,),
            ).fetchall()
        return len(rows)
