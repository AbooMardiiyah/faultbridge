from __future__ import annotations

import unittest

from faultbridge_eval.routing_recommender import recommend


class RoutingRecommenderTests(unittest.TestCase):
    def asr_report(self) -> dict:
        return {
            "groups": [
                {
                    "provider": "sahara",
                    "language_pair": "Hausa-English",
                    "condition": "clean-16khz",
                    "normalized_wer": 0.3,
                    "failure_rate": 0.0,
                    "post_audio_p95_seconds": 1.0,
                },
                {
                    "provider": "alternative",
                    "language_pair": "Hausa-English",
                    "condition": "clean-16khz",
                    "normalized_wer": 0.2,
                    "failure_rate": 0.0,
                    "post_audio_p95_seconds": 1.0,
                },
            ],
            "paired_comparisons": [
                {
                    "provider_a": "alternative",
                    "provider_b": "sahara",
                    "language_pair": "Hausa-English",
                    "condition": "clean-16khz",
                    "lower_wer_winner": "alternative",
                }
            ],
        }

    def test_routes_only_when_paired_evidence_and_safety_pass(self) -> None:
        agent = {
            "variants": [
                {"variant": name, "critical_runs": 3, "critical_failure_rate": 0.0}
                for name in ("sahara", "alternative")
            ]
        }

        policies = recommend(
            self.asr_report(),
            agent,
            default_provider="sahara",
            max_failure_rate=0.01,
            max_p95_seconds=2.0,
        )

        self.assertEqual(policies[0]["primary_provider"], "alternative")

    def test_safety_failure_keeps_conservative_default(self) -> None:
        agent = {
            "variants": [
                {"variant": "sahara", "critical_runs": 3, "critical_failure_rate": 0.0},
                {
                    "variant": "alternative",
                    "critical_runs": 3,
                    "critical_failure_rate": 1 / 3,
                },
            ]
        }

        policies = recommend(
            self.asr_report(),
            agent,
            default_provider="sahara",
            max_failure_rate=0.01,
            max_p95_seconds=2.0,
        )

        self.assertEqual(policies[0]["primary_provider"], "sahara")
        self.assertIn(
            "critical safety gate failed", policies[0]["rejections"]["alternative"]
        )

    def test_maps_report_provider_names_to_named_asr_agent_variants(self) -> None:
        asr = self.asr_report()
        asr["groups"][0]["provider"] = "sahara-file-sync"
        asr["groups"][1]["provider"] = "sbpn-base"
        asr["paired_comparisons"][0]["provider_a"] = "sbpn-base"
        asr["paired_comparisons"][0]["provider_b"] = "sahara-file-sync"
        asr["paired_comparisons"][0]["lower_wer_winner"] = "sbpn-base"
        agent = {
            "variants": [
                {
                    "variant": "asr_sahara",
                    "critical_runs": 3,
                    "critical_failure_rate": 0.0,
                },
                {
                    "variant": "asr_sbpn",
                    "critical_runs": 3,
                    "critical_failure_rate": 0.0,
                },
            ]
        }

        policies = recommend(
            asr,
            agent,
            default_provider="sahara-file-sync",
            max_failure_rate=0.01,
            max_p95_seconds=2.0,
        )

        self.assertEqual(policies[0]["primary_provider"], "sbpn-base")

    def test_missing_comparable_latency_keeps_default(self) -> None:
        report = self.asr_report()
        report["groups"][1]["post_audio_p95_seconds"] = None
        agent = {
            "variants": [
                {"variant": name, "critical_runs": 3, "critical_failure_rate": 0.0}
                for name in ("sahara", "alternative")
            ]
        }

        policies = recommend(
            report,
            agent,
            default_provider="sahara",
            max_failure_rate=0.01,
            max_p95_seconds=2.0,
        )

        self.assertEqual(policies[0]["primary_provider"], "sahara")
        self.assertIsNone(policies[0]["fallback_provider"])
        self.assertIn(
            "no comparable p95 post-audio latency",
            policies[0]["rejections"]["alternative"],
        )


if __name__ == "__main__":
    unittest.main()
