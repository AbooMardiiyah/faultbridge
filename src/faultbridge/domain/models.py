from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Tier(StrEnum):
    KNOWN_FAULT = "known_fault"
    DIAGNOSIS = "diagnosis"
    ESCALATION = "escalation"
    COMPLETE = "complete"


class Outcome(StrEnum):
    AWAITING_VERIFICATION = "awaiting_verification"
    KNOWN_FAULT_HANDLED = "known_fault_handled"
    GUIDED_FIX_RESOLVED = "guided_fix_resolved"
    ESCALATED = "escalated"
    CONSENT_DECLINED = "consent_declined"


@dataclass(frozen=True, slots=True)
class Fault:
    incident_id: str
    cell_id: str
    area: str
    fault_type: str
    status: str
    cause: str
    estimated_restoration: str


@dataclass(frozen=True, slots=True)
class AccountState:
    caller_ref: str
    data_balance_mb: int
    barred: bool
    compensation_eligible: bool


@dataclass(slots=True)
class ToolEvent:
    tool: str
    inputs: dict[str, Any]
    output: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class CallSession:
    caller_ref: str
    area: str
    cell_id: str
    language_pair: str
    symptom: str
    safe_transcript: str
    consent: bool
    call_id: str = field(default_factory=lambda: str(uuid4()))
    tier: Tier = Tier.DIAGNOSIS
    outcome: Outcome = Outcome.AWAITING_VERIFICATION
    next_action: str | None = None
    response: str = ""
    events: list[ToolEvent] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EscalationResult:
    ticket_id: str
    signal_count: int
    candidate_incident_id: str | None

