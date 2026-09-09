from __future__ import annotations

from faultbridge.domain.models import CallSession, Outcome, Tier, ToolEvent
from faultbridge.services.privacy import pseudonymize_caller, redact_text
from faultbridge.tools.telco import TelcoTools


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
        if not consent:
            session.tier = Tier.COMPLETE
            session.outcome = Outcome.CONSENT_DECLINED
            session.response = "Recording and automated processing are off. I can transfer you to an agent."
            return session

        fault, fault_event = self.tools.lookup_fault(session.call_id, session.cell_id)
        session.events.append(fault_event)
        if fault is not None:
            session.tier = Tier.KNOWN_FAULT
            account, account_event = self.tools.inspect_account(
                session.call_id, session.caller_ref
            )
            session.events.append(account_event)
            if account.compensation_eligible:
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
            session.response = (
                f"I found an active {fault.fault_type} affecting {fault.area}. "
                f"The current restoration estimate is {fault.estimated_restoration}. "
                "I have scheduled an update when service is restored."
            )
            return session

        session.tier = Tier.DIAGNOSIS
        account, account_event = self.tools.inspect_account(
            session.call_id, session.caller_ref
        )
        session.events.append(account_event)
        if account.barred:
            session.next_action = "restore_account_access"
            session.response = "The line is barred. I can guide you through restoring access, then we will test again."
        elif account.data_balance_mb <= 0:
            session.next_action = "restore_data_balance"
            session.response = "There is no active data balance. Restore a bundle, then tell me whether data works."
        else:
            session.next_action = "toggle_airplane_mode"
            session.response = "Your account looks active. Turn airplane mode on for ten seconds, turn it off, then test the service."
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
            session.response = "The service test passed, so I am closing this case as resolved."
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
        return session

