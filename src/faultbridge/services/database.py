from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from faultbridge.domain.models import AccountState, Fault, ToolEvent


class Database:
    """Small SQLite store for authoritative demo state and auditable actions."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._memory_connection: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._memory_connection = sqlite3.connect(self.path)
            self._memory_connection.row_factory = sqlite3.Row
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._memory_connection is not None:
            yield self._memory_connection
            self._memory_connection.commit()
            return
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS faults (
                    incident_id TEXT PRIMARY KEY,
                    cell_id TEXT NOT NULL,
                    area TEXT NOT NULL,
                    fault_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cause TEXT NOT NULL,
                    estimated_restoration TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fault_cell_status
                    ON faults(cell_id, status);

                CREATE TABLE IF NOT EXISTS accounts (
                    caller_ref TEXT PRIMARY KEY,
                    data_balance_mb INTEGER NOT NULL,
                    barred INTEGER NOT NULL,
                    compensation_eligible INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS action_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    inputs_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS complaint_signals (
                    signal_id TEXT PRIMARY KEY,
                    call_id TEXT NOT NULL UNIQUE,
                    caller_ref TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS candidate_incidents (
                    candidate_id TEXT PRIMARY KEY,
                    cell_id TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(cell_id, symptom)
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    call_id TEXT NOT NULL UNIQUE,
                    caller_ref TEXT NOT NULL,
                    cell_id TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS credits (
                    credit_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    caller_ref TEXT NOT NULL,
                    incident_id TEXT NOT NULL,
                    amount_mb INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS callbacks (
                    callback_id TEXT PRIMARY KEY,
                    caller_ref TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    incident_id TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(caller_ref, trigger, incident_id)
                );
                """
            )

    def seed_faults(self, faults: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO faults
                (incident_id, cell_id, area, fault_type, status, cause,
                 estimated_restoration)
                VALUES (:incident_id, :cell_id, :area, :fault_type, :status,
                        :cause, :estimated_restoration)
                """,
                faults,
            )

    def seed_accounts(self, accounts: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO accounts
                (caller_ref, data_balance_mb, barred, compensation_eligible)
                VALUES (:caller_ref, :data_balance_mb, :barred,
                        :compensation_eligible)
                """,
                accounts,
            )

    def find_active_fault(self, cell_id: str) -> Fault | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM faults WHERE cell_id = ? AND status = 'active' LIMIT 1",
                (cell_id,),
            ).fetchone()
        return Fault(**dict(row)) if row else None

    def get_account(self, caller_ref: str) -> AccountState:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM accounts WHERE caller_ref = ?", (caller_ref,)
            ).fetchone()
        if row is None:
            return AccountState(caller_ref, 1024, False, True)
        values = dict(row)
        values["barred"] = bool(values["barred"])
        values["compensation_eligible"] = bool(values["compensation_eligible"])
        return AccountState(**values)

    def record_event(self, call_id: str, event: ToolEvent) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO action_events
                (call_id, tool, inputs_json, output_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    event.tool,
                    json.dumps(event.inputs, sort_keys=True),
                    json.dumps(event.output, sort_keys=True),
                    event.created_at.isoformat(),
                ),
            )

    def create_credit(
        self,
        caller_ref: str,
        incident_id: str,
        amount_mb: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        credit_id = f"credit_{uuid4().hex[:10]}"
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT credit_id, amount_mb FROM credits WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return {
                    "credit_id": existing["credit_id"],
                    "amount_mb": existing["amount_mb"],
                    "created": False,
                }
            connection.execute(
                """
                INSERT INTO credits
                (credit_id, idempotency_key, caller_ref, incident_id, amount_mb, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    credit_id,
                    idempotency_key,
                    caller_ref,
                    incident_id,
                    amount_mb,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return {"credit_id": credit_id, "amount_mb": amount_mb, "created": True}

    def schedule_callback(
        self, caller_ref: str, trigger: str, incident_id: str | None
    ) -> dict[str, Any]:
        callback_id = f"callback_{uuid4().hex[:10]}"
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT callback_id FROM callbacks
                WHERE caller_ref = ? AND trigger = ? AND incident_id IS ?
                """,
                (caller_ref, trigger, incident_id),
            ).fetchone()
            if existing:
                return {"callback_id": existing["callback_id"], "created": False}
            connection.execute(
                """
                INSERT INTO callbacks
                (callback_id, caller_ref, trigger, incident_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    callback_id,
                    caller_ref,
                    trigger,
                    incident_id,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return {"callback_id": callback_id, "created": True}

    def create_ticket(
        self,
        call_id: str,
        caller_ref: str,
        cell_id: str,
        symptom: str,
        summary: str,
    ) -> str:
        ticket_id = f"ticket_{uuid4().hex[:10]}"
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT ticket_id FROM tickets WHERE call_id = ?", (call_id,)
            ).fetchone()
            if existing:
                return str(existing["ticket_id"])
            connection.execute(
                """
                INSERT INTO tickets
                (ticket_id, call_id, caller_ref, cell_id, symptom, summary,
                 status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    ticket_id,
                    call_id,
                    caller_ref,
                    cell_id,
                    symptom,
                    summary,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return ticket_id

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
                INSERT OR IGNORE INTO complaint_signals
                (signal_id, call_id, caller_ref, cell_id, symptom, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"signal_{uuid4().hex[:10]}",
                    call_id,
                    caller_ref,
                    cell_id,
                    symptom,
                    now.isoformat(),
                ),
            )
            cutoff = (now - timedelta(minutes=window_minutes)).isoformat()
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT caller_ref) AS count
                FROM complaint_signals
                WHERE cell_id = ? AND symptom = ? AND created_at >= ?
                """,
                (cell_id, symptom, cutoff),
            ).fetchone()
        return int(row["count"])

    def propose_candidate(self, cell_id: str, symptom: str, evidence_count: int) -> str:
        candidate_id = f"candidate_{uuid4().hex[:10]}"
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT candidate_id FROM candidate_incidents
                WHERE cell_id = ? AND symptom = ?
                """,
                (cell_id, symptom),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE candidate_incidents SET evidence_count = ?
                    WHERE candidate_id = ?
                    """,
                    (evidence_count, existing["candidate_id"]),
                )
                return str(existing["candidate_id"])
            connection.execute(
                """
                INSERT INTO candidate_incidents
                (candidate_id, cell_id, symptom, status, evidence_count, created_at)
                VALUES (?, ?, ?, 'unconfirmed', ?, ?)
                """,
                (
                    candidate_id,
                    cell_id,
                    symptom,
                    evidence_count,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return candidate_id

    def list_events(self, call_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM action_events WHERE call_id = ? ORDER BY event_id",
                (call_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_candidates(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM candidate_incidents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
