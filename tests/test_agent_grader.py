from __future__ import annotations

import unittest
from collections import Counter

from faultbridge_eval.agent_grader import grade_agent_trace
from faultbridge_eval.prepare_agent_scenarios import build_scenarios


class AgentGraderTests(unittest.TestCase):
    def test_frozen_agent_panel_is_balanced_and_safety_gated(self) -> None:
        scenarios = build_scenarios()

        self.assertEqual(len(scenarios), 48)
        self.assertEqual(len({row["scenario_id"] for row in scenarios}), 48)
        self.assertEqual(
            Counter(row["input"]["language_pair"] for row in scenarios),
            {
                "Hausa-English": 12,
                "Igbo-English": 12,
                "Pidgin-English": 12,
                "Yoruba-English": 12,
            },
        )
        self.assertTrue(all(row["expected"].get("critical") for row in scenarios))
        self.assertTrue(all(len(row.get("hypotheses", {})) == 1 for row in scenarios))

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
