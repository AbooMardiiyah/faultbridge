import unittest

from faultbridge.domain.models import Outcome
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.tools.telco import TelcoTools


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database(":memory:")
        self.database.initialize()
        self.database.seed_faults(
            [
                {
                    "incident_id": "INC-1",
                    "cell_id": "KANO-014",
                    "area": "Tarauni, Kano",
                    "fault_type": "fibre cut",
                    "status": "active",
                    "cause": "road works",
                    "estimated_restoration": "18:30 WAT",
                }
            ]
        )
        self.agent = FaultBridgeOrchestrator(
            TelcoTools(self.database, signal_threshold=3),
            "test-secret-at-least-16-characters",
        )

    def start_unknown(self, index: int):
        return self.agent.start_call(
            caller_id=f"0804000000{index}",
            transcript="Data no work, call me on 08031234567",
            area="Bodija, Ibadan",
            cell_id="IBD-207",
            language_pair="Yoruba-English",
            symptom="data_unavailable",
            consent=True,
        )

    def test_known_fault_is_grounded_and_handled(self) -> None:
        session = self.agent.start_call(
            caller_id="08031234567",
            transcript="Network is down",
            area="Tarauni, Kano",
            cell_id="kano-014",
            language_pair="Hausa-English",
            symptom="no_service",
            consent=True,
        )
        self.assertEqual(session.outcome, Outcome.KNOWN_FAULT_HANDLED)
        self.assertEqual(
            [event.tool for event in session.events],
            [
                "lookup_fault",
                "inspect_account",
                "apply_compensation",
                "schedule_callback",
            ],
        )
        self.assertIn("18:30 WAT", session.response)

    def test_guided_fix_requires_verification(self) -> None:
        session = self.start_unknown(1)
        self.assertEqual(session.outcome, Outcome.AWAITING_VERIFICATION)
        self.agent.verify_resolution(session, resolved=True)
        self.assertEqual(session.outcome, Outcome.GUIDED_FIX_RESOLVED)

    def test_third_distinct_unresolved_call_proposes_candidate(self) -> None:
        sessions = []
        for index in range(3):
            session = self.start_unknown(index)
            sessions.append(self.agent.verify_resolution(session, resolved=False))

        self.assertIsNone(
            next(
                (
                    event.output.get("candidate_incident_id")
                    for event in sessions[1].events
                    if event.tool == "propose_candidate_incident"
                ),
                None,
            )
        )
        candidate_events = [
            event
            for event in sessions[2].events
            if event.tool == "propose_candidate_incident"
        ]
        self.assertEqual(len(candidate_events), 1)
        self.assertEqual(candidate_events[0].output["evidence_count"], 3)
        self.assertEqual(len(self.database.list_candidates()), 1)

    def test_repeated_caller_does_not_inflate_cluster(self) -> None:
        first = self.start_unknown(7)
        self.agent.verify_resolution(first, resolved=False)
        second = self.start_unknown(7)
        self.agent.verify_resolution(second, resolved=False)
        signals = [
            event
            for event in second.events
            if event.tool == "record_complaint_signal"
        ]
        self.assertEqual(signals[0].output["distinct_callers"], 1)
        self.assertEqual(self.database.list_candidates(), [])

    def test_consent_decline_avoids_tools(self) -> None:
        session = self.agent.start_call(
            caller_id="08031234567",
            transcript="Do not process this call",
            area="Kano",
            cell_id="KANO-014",
            language_pair="Hausa-English",
            symptom="no_service",
            consent=False,
        )
        self.assertEqual(session.outcome, Outcome.CONSENT_DECLINED)
        self.assertEqual(session.events, [])


if __name__ == "__main__":
    unittest.main()

