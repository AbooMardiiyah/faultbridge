from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from faultbridge.domain.models import CallSession, Outcome, Tier, ToolEvent
from faultbridge.services.privacy import pseudonymize_caller, redact_text
from faultbridge.tools.telco import TelcoTools

WEST_AFRICA_TIME = ZoneInfo("Africa/Lagos")


def format_restoration_time(value: datetime | None) -> str:
    """Return an incident ETA that is clear on screen and when spoken by TTS."""
    if value is None:
        return "being assessed"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local_value = value.astimezone(WEST_AFRICA_TIME)
    clock = local_value.strftime("%I:%M %p").lstrip("0")
    date = f"{local_value.day} {local_value.strftime('%B %Y')}"
    return f"{clock} West Africa Time on {date}"


class FaultBridgeOrchestrator:
    """Stateful policy that constrains model-selected actions to safe transitions."""

    def __init__(self, tools: TelcoTools, pseudonym_secret: str) -> None:
        self.tools = tools
        self.pseudonym_secret = pseudonym_secret

    def start_call(
        self,
        *,
        caller_id: str,
        transcript: str,
        area: str,
        cell_id: str,
        language_pair: str,
        symptom: str,
        consent: bool,
    ) -> CallSession:
        session = CallSession(
            caller_ref=pseudonymize_caller(caller_id, self.pseudonym_secret),
            area=area,
            cell_id=cell_id.strip().upper(),
            language_pair=language_pair,
            symptom=symptom.strip().lower(),
            safe_transcript=redact_text(transcript),
            consent=consent,
        )
        self.tools.database.save_session(session)
        if not consent:
            session.tier = Tier.COMPLETE
            session.outcome = Outcome.CONSENT_DECLINED
            session.response = "Recording and automated processing are off. I can transfer you to an agent."
            self.tools.database.save_session(session)
            return session

        fault, fault_event = self.tools.lookup_fault(session.call_id, session.cell_id)
        session.events.append(fault_event)
        if fault is not None:
            session.tier = Tier.KNOWN_FAULT
            account, account_event = self.tools.inspect_account(
                session.call_id, session.caller_ref
            )
            session.events.append(account_event)
            if account and account.compensation_eligible:
                session.events.append(
                    self.tools.apply_compensation(
                        session.call_id, session.caller_ref, fault.incident_id
                    )
                )
            session.events.append(
                self.tools.schedule_callback(
                    session.call_id, session.caller_ref, fault.incident_id
                )
            )
            session.tier = Tier.COMPLETE
            session.outcome = Outcome.KNOWN_FAULT_HANDLED
            restoration = format_restoration_time(fault.estimated_restoration)
            session.response = (
                f"I found an active {fault.fault_type} affecting {fault.area}. "
                f"The current restoration estimate is {restoration}. "
                "I have scheduled an update when service is restored."
            )
            self.tools.database.save_session(session)
            return session

        session.tier = Tier.DIAGNOSIS
        account, account_event = self.tools.inspect_account(
            session.call_id, session.caller_ref
        )
        session.events.append(account_event)
        playbook, playbook_event = self.tools.lookup_playbook(
            session.call_id,
            session.symptom,
            language_pair=session.language_pair,
        )
        session.events.append(playbook_event)
        first_step = (
            str(playbook["steps_json"][0])
            if playbook and playbook.get("steps_json")
            else None
        )
        if account is None:
            session.next_action = "run_device_diagnostic"
            session.response = (
                "I could not verify account state, so I will not make an account "
                "change. "
                + (first_step or "Check signal strength and toggle airplane mode")
                + ", then test again."
            )
        elif account.barred:
            session.next_action = "restore_account_access"
            session.response = "The line is barred. I can guide you through restoring access, then we will test again."
        elif account.data_balance_mb <= 0:
            session.next_action = "restore_data_balance"
            session.response = "There is no active data balance. Restore a bundle, then tell me whether data works."
        else:
            session.next_action = "toggle_airplane_mode"
            guidance = first_step or (
                "Turn airplane mode on for ten seconds, turn it off"
            )
            session.response = (
                f"Your account looks active. {guidance}, then test the service."
            )
        self.tools.database.save_session(session)
        return session

    def verify_resolution(self, session: CallSession, *, resolved: bool) -> CallSession:
        if session.outcome != Outcome.AWAITING_VERIFICATION:
            raise ValueError("this call is not awaiting verification")

        event = ToolEvent(
            tool="verify_resolution",
            inputs={"attempted_action": session.next_action},
            output={"resolved": resolved},
        )
        self.tools.database.record_event(session.call_id, event)
        session.events.append(event)
        if resolved:
            session.tier = Tier.COMPLETE
            session.outcome = Outcome.GUIDED_FIX_RESOLVED
            session.response = (
                "The service test passed, so I am closing this case as resolved."
            )
            self.tools.database.save_session(session)
            return session

        session.tier = Tier.ESCALATION
        safe_summary = (
            f"{session.language_pair} caller in {session.area}; "
            f"symptom={session.symptom}; attempted={session.next_action}; "
            "caller reports the service is still unavailable."
        )
        escalation, events = self.tools.escalate(
            session.call_id,
            session.caller_ref,
            session.cell_id,
            session.symptom,
            safe_summary,
        )
        session.events.extend(events)
        session.tier = Tier.COMPLETE
        session.outcome = Outcome.ESCALATED
        candidate_text = (
            f" Candidate incident {escalation.candidate_incident_id} was proposed for NOC review."
            if escalation.candidate_incident_id
            else " The complaint was added to the local fault signal."
        )
        session.response = f"I opened ticket {escalation.ticket_id}.{candidate_text}"
        self.tools.database.save_session(session)
        return session
