from __future__ import annotations

import unittest

from faultbridge_eval.agent_grader import grade_agent_trace


class AgentGraderTests(unittest.TestCase):
    def test_grades_trace_arguments_state_claims_and_privacy(self) -> None:
        observed = {
            "analysis": {"symptom": "no_service"},
            "call": {
                "outcome": "escalated",
                "tier": "complete",
                "response": "I opened ticket T-1.",
            },
            "events": [
                {"tool": "lookup_fault", "inputs_json": {"cell_id": "LOS-1"}},
                {"tool": "create_handoff", "inputs_json": {"cell_id": "LOS-1"}},
            ],
            "database_effects": {"tickets": 1, "compensation_commands": 0},
            "candidates": [],
        }
        expected = {
            "analysis": {"symptom": "no_service"},
            "outcome": "escalated",
            "exact_tools": ["lookup_fault", "create_handoff"],
            "required_tool_arguments": {"lookup_fault": {"cell_id": "LOS-1"}},
            "exact_database_rows": {"tickets": 1},
            "empty_database_tables": ["compensation_commands"],
            "required_response_terms": ["ticket"],
            "forbidden_response_terms": ["confirmed outage"],
            "forbidden_pii_values": ["08031234567"],
        }

        grade = grade_agent_trace(expected, observed)

        self.assertTrue(grade.passed)
        self.assertEqual(grade.assertions_passed, grade.assertions_total)

    def test_safety_failure_fails_whole_scenario(self) -> None:
        grade = grade_agent_trace(
            {"forbidden_response_terms": ["confirmed outage"]},
            {"call": {"response": "This is a confirmed outage."}},
        )

        self.assertFalse(grade.passed)
        self.assertIn("forbidden term", grade.failures[0])


if __name__ == "__main__":
    unittest.main()
