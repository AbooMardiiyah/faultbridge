import os
import unittest
from datetime import UTC, datetime, timedelta

from faultbridge.domain.models import Outcome
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.services.privacy import pseudonymize_caller
from faultbridge.tools.telco import TelcoTools

SECRET = "test-secret-at-least-32-characters-long"


class OrchestratorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is required for integration tests")
        cls.database = Database(database_url)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.database.close()

    def setUp(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                TRUNCATE network_incidents, accounts, call_sessions,
                         candidate_incidents, compensation_commands,
                         callback_commands
                RESTART IDENTITY CASCADE
                """
            )
        self.database.upsert_incident(
            {
                "incident_id": "INC-1",
                "operator": "Test Operator",
                "cell_id": "KANO-014",
                "area": "Tarauni, Kano",
                "fault_type": "fibre cut",
                "status": "active",
                "cause": "road works",
                "estimated_restoration": datetime.now(UTC) + timedelta(hours=2),
                "source_system": "noc-integration-test",
                "source_reference": "alarm-123",
                "verified_at": datetime.now(UTC),
            }
        )
        caller_ref = pseudonymize_caller("08031234567", SECRET)
        self.database.upsert_account(
            {
                "caller_ref": caller_ref,
                "data_balance_mb": 1024,
                "barred": False,
                "compensation_eligible": True,
                "source_system": "crm-integration-test",
                "source_reference": "subscriber-123",
                "verified_at": datetime.now(UTC),
            }
        )
        self.agent = FaultBridgeOrchestrator(
            TelcoTools(self.database, signal_threshold=3), SECRET
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

    def test_known_fault_is_grounded_and_queues_actions(self) -> None:
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
                "queue_compensation",
                "schedule_callback",
            ],
        )
        self.assertEqual(
            session.events[0].output["fault"]["source_system"],
            "noc-integration-test",
        )
        self.assertEqual(session.events[2].output["status"], "queued")

    def test_missing_account_remains_unknown(self) -> None:
        session = self.start_unknown(1)
        account_event = next(
            event for event in session.events if event.tool == "inspect_account"
        )
        self.assertEqual(account_event.output, {"found": False})
        self.assertEqual(session.next_action, "run_device_diagnostic")

    def test_guided_fix_requires_verification_and_persists_state(self) -> None:
        session = self.start_unknown(1)
        self.assertEqual(session.outcome, Outcome.AWAITING_VERIFICATION)
        self.agent.verify_resolution(session, resolved=True)
        self.assertEqual(session.outcome, Outcome.GUIDED_FIX_RESOLVED)
        restored = self.database.get_session(session.call_id)
        self.assertEqual(restored.outcome, Outcome.GUIDED_FIX_RESOLVED)

    def test_third_distinct_unresolved_call_proposes_candidate(self) -> None:
        sessions = []
        for index in range(3):
            session = self.start_unknown(index)
            sessions.append(self.agent.verify_resolution(session, resolved=False))

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
            event for event in second.events if event.tool == "record_complaint_signal"
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
        self.assertIsNotNone(self.database.get_session(session.call_id))


if __name__ == "__main__":
    unittest.main()
