from __future__ import annotations

from dataclasses import asdict
from typing import Any

from faultbridge.domain.models import EscalationResult, ToolEvent
from faultbridge.services.database import Database


class TelcoTools:
    def __init__(
        self,
        database: Database,
        *,
        signal_threshold: int = 3,
        signal_window_minutes: int = 30,
    ) -> None:
        self.database = database
        self.signal_threshold = signal_threshold
        self.signal_window_minutes = signal_window_minutes

    def _audit(
        self, call_id: str, tool: str, inputs: dict[str, Any], output: dict[str, Any]
    ) -> ToolEvent:
        event = ToolEvent(tool=tool, inputs=inputs, output=output)
        self.database.record_event(call_id, event)
        return event

    def lookup_fault(self, call_id: str, cell_id: str) -> tuple[Any, ToolEvent]:
        fault = self.database.find_active_fault(cell_id)
        output = {
            "matched": fault is not None,
            "fault": asdict(fault) if fault else None,
        }
        return fault, self._audit(call_id, "lookup_fault", {"cell_id": cell_id}, output)

    def inspect_account(self, call_id: str, caller_ref: str) -> tuple[Any, ToolEvent]:
        account = self.database.get_account(caller_ref)
        safe_output = (
            {
                "found": True,
                "data_balance_mb": account.data_balance_mb,
                "barred": account.barred,
                "compensation_eligible": account.compensation_eligible,
                "source_system": account.source_system,
                "verified_at": account.verified_at.isoformat(),
            }
            if account
            else {"found": False}
        )
        return account, self._audit(
            call_id, "inspect_account", {"caller_ref": caller_ref}, safe_output
        )

    def apply_compensation(
        self, call_id: str, caller_ref: str, incident_id: str, amount_mb: int = 500
    ) -> ToolEvent:
        output = self.database.queue_compensation(
            caller_ref,
            incident_id,
            amount_mb,
            idempotency_key=f"{caller_ref}:{incident_id}:data-credit",
        )
        return self._audit(
            call_id,
            "queue_compensation",
            {"caller_ref": caller_ref, "incident_id": incident_id},
            output,
        )

    def schedule_callback(
        self, call_id: str, caller_ref: str, incident_id: str | None
    ) -> ToolEvent:
        output = self.database.schedule_callback(
            caller_ref, "incident_resolved", incident_id
        )
        return self._audit(
            call_id,
            "schedule_callback",
            {"caller_ref": caller_ref, "incident_id": incident_id},
            output,
        )

    def escalate(
        self,
        call_id: str,
        caller_ref: str,
        cell_id: str,
        symptom: str,
        summary: str,
    ) -> tuple[EscalationResult, list[ToolEvent]]:
        events: list[ToolEvent] = []
        ticket_id = self.database.create_ticket(
            call_id, caller_ref, cell_id, symptom, summary
        )
        events.append(
            self._audit(
                call_id,
                "create_handoff",
                {"cell_id": cell_id, "symptom": symptom},
                {"ticket_id": ticket_id, "status": "open"},
            )
        )
        signal_count = self.database.record_signal(
            call_id,
            caller_ref,
            cell_id,
            symptom,
            self.signal_window_minutes,
        )
        events.append(
            self._audit(
                call_id,
                "record_complaint_signal",
                {"cell_id": cell_id, "symptom": symptom},
                {"distinct_callers": signal_count},
            )
        )
        candidate_id = None
        if signal_count >= self.signal_threshold:
            candidate_id = self.database.propose_candidate(
                cell_id, symptom, signal_count
            )
            events.append(
                self._audit(
                    call_id,
                    "propose_candidate_incident",
                    {"cell_id": cell_id, "symptom": symptom},
                    {
                        "candidate_incident_id": candidate_id,
                        "status": "unconfirmed",
                        "evidence_count": signal_count,
                    },
                )
            )
        result = EscalationResult(ticket_id, signal_count, candidate_id)
        return result, events
