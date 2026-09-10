import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from faultbridge.api import app, database, settings


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.internal_headers = {
            "X-Internal-API-Key": (
                settings.faultbridge_internal_api_key.get_secret_value()
            )
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        with database.connect() as connection:
            connection.execute(
                """
                TRUNCATE network_incidents, accounts, call_sessions,
                         candidate_incidents, compensation_commands,
                         callback_commands, troubleshooting_playbooks
                RESTART IDENTITY CASCADE
                """
            )

    def test_internal_incident_ingestion_requires_authentication(self) -> None:
        response = self.client.put("/internal/network-incidents/INC-401", json={})
        self.assertEqual(response.status_code, 401)

    def test_frontends_are_served_without_exposing_operational_data(self) -> None:
        caller_page = self.client.get("/")
        self.assertEqual(caller_page.status_code, 200)
        self.assertIn("Voice Support · FaultBridge", caller_page.text)
        operations_page = self.client.get("/operations")
        self.assertEqual(operations_page.status_code, 200)
        self.assertIn("Network Operations · FaultBridge", operations_page.text)
        data = self.client.get("/internal/dashboard")
        self.assertEqual(data.status_code, 401)

    def test_ingested_incident_grounds_call_response(self) -> None:
        now = datetime.now(UTC)
        ingestion = self.client.put(
            "/internal/network-incidents/INC-LAG-9",
            headers=self.internal_headers,
            json={
                "operator": "Test Operator",
                "cell_id": "lag-009",
                "area": "Yaba, Lagos",
                "fault_type": "power failure",
                "status": "active",
                "cause": "site power loss",
                "estimated_restoration": (now + timedelta(hours=1)).isoformat(),
                "source_system": "noc-test",
                "source_reference": "alarm-lag-9",
                "verified_at": now.isoformat(),
            },
        )
        self.assertEqual(ingestion.status_code, 200)

        call = self.client.post(
            "/internal/text-calls",
            headers=self.internal_headers,
            json={
                "caller_id": "08031234567",
                "transcript": "My number is 08031234567 and network no dey work",
                "area": "Yaba, Lagos",
                "cell_id": "LAG-009",
                "language_pair": "Pidgin-English",
                "symptom": "no_service",
                "consent": True,
            },
        )
        self.assertEqual(call.status_code, 200)
        body = call.json()
        self.assertEqual(body["outcome"], "known_fault_handled")
        self.assertNotIn("08031234567", body["safe_transcript"])
        self.assertIn("power failure", body["response"])
        dashboard = self.client.get(
            "/internal/dashboard", headers=self.internal_headers
        ).json()
        self.assertEqual(
            dashboard["calls"][0]["safe_transcript"], body["safe_transcript"]
        )
        self.assertNotIn("08031234567", dashboard["calls"][0]["safe_transcript"])

    def test_caller_can_be_deleted_by_pseudonymous_reference(self) -> None:
        created = self.client.post(
            "/internal/text-calls",
            headers=self.internal_headers,
            json={
                "caller_id": "08035550199",
                "transcript": "My network no dey work",
                "area": "Yaba, Lagos",
                "cell_id": "LAG-199",
                "language_pair": "Pidgin-English",
                "symptom": "no_service",
                "consent": True,
            },
        )
        self.assertEqual(created.status_code, 200)
        deleted = self.client.request(
            "DELETE",
            "/internal/caller-data",
            headers=self.internal_headers,
            json={"caller_id": "08035550199"},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["deleted"]["calls"], 1)


if __name__ == "__main__":
    unittest.main()
