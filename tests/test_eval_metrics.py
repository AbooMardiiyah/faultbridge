from __future__ import annotations

import unittest

from faultbridge_eval.metrics import (
    ErrorCounts,
    bootstrap_interval,
    character_errors,
    entity_scores,
    language_role_counts,
    normalize_text,
    switch_context_recall,
    word_errors,
)


class EvaluationMetricTests(unittest.TestCase):
    def test_word_errors_preserve_operation_counts(self) -> None:
        counts = word_errors("hello world", "hello brave earth", normalized=False)

        self.assertEqual(counts, ErrorCounts(1, 0, 1, 2))
        self.assertEqual(counts.error_rate, 1.0)

    def test_frozen_normalization_handles_case_unicode_and_punctuation(self) -> None:
        self.assertEqual(normalize_text("  ÈKÓ, Network!  "), "èkó network")
        self.assertEqual(
            word_errors("ÈKÓ, Network!", "èkó network", normalized=True).error_rate,
            0.0,
        )
        self.assertEqual(
            character_errors("AB", "AC", normalized=False),
            ErrorCounts(1, 0, 0, 2),
        )

    def test_language_role_counts_include_insertions(self) -> None:
        counts = language_role_counts(
            "bawo [[EN]]network down[[/EN]] yau",
            "bawo network slow yau extra",
        )

        self.assertEqual(counts.embedded_english_units, 2)
        self.assertEqual(counts.embedded_english_errors, 1)
        self.assertEqual(counts.matrix_units, 2)
        self.assertEqual(counts.matrix_errors, 1)

    def test_switch_context_requires_adjacent_correct_tokens(self) -> None:
        tagged = "bawo [[EN]]network down[[/EN]] yau"
        self.assertEqual(switch_context_recall(tagged, "bawo network down yau"), 1.0)
        self.assertLess(
            switch_context_recall(tagged, "bawo very network down yau"), 1.0
        )

    def test_entity_matching_uses_token_boundaries(self) -> None:
        self.assertEqual(
            entity_scores(["cell 12"], "problem at cell 123")["recall"], 0.0
        )
        self.assertEqual(
            entity_scores(["cell 12"], "problem at cell 12")["recall"], 1.0
        )

    def test_bootstrap_is_seeded(self) -> None:
        statistic = lambda values: sum(values) / len(values)
        first = bootstrap_interval([1.0, 2.0, 3.0], statistic, iterations=100)
        second = bootstrap_interval([1.0, 2.0, 3.0], statistic, iterations=100)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
