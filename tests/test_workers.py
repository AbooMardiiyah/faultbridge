import os
import unittest
from datetime import UTC, datetime

from faultbridge.services.database import Database
from faultbridge.services.workers import ActionWorker


class RecordingDispatcher:
    def __init__(self) -> None:
        self.command_ids: list[str] = []

    async def deliver(self, command: dict) -> str:
        self.command_ids.append(command["command_id"])
        return f"operator-{command['command_id']}"


class ActionWorkerIntegrationTests(unittest.IsolatedAsyncioTestCase):
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
                         callback_commands, troubleshooting_playbooks
                RESTART IDENTITY CASCADE
                """
            )
        self.database.upsert_incident(
            {
                "incident_id": "INC-WORKER-1",
                "operator": "Test Operator",
                "cell_id": "LAG-001",
                "area": "Yaba",
                "fault_type": "power failure",
                "status": "active",
                "cause": "site power loss",
                "estimated_restoration": None,
                "source_system": "test-noc",
                "source_reference": "ALARM-1",
                "verified_at": datetime.now(UTC),
            }
        )

    async def test_worker_delivers_and_completes_both_command_types(self) -> None:
        self.database.queue_compensation(
            "caller-one", "INC-WORKER-1", 500, "caller-one:incident-one"
        )
        self.database.schedule_callback(
            "caller-one", "incident_resolved", "INC-WORKER-1"
        )
        compensation = RecordingDispatcher()
        callback = RecordingDispatcher()
        worker = ActionWorker(
            self.database, compensation=compensation, callback=callback
        )

        self.assertEqual(await worker.run_once(), 2)
        snapshot = self.database.dashboard_snapshot()
        self.assertEqual(snapshot["compensation_commands"][0]["status"], "completed")
        self.assertEqual(snapshot["callback_commands"][0]["status"], "completed")
        self.assertEqual(len(compensation.command_ids), 1)
        self.assertEqual(len(callback.command_ids), 1)


if __name__ == "__main__":
    unittest.main()
