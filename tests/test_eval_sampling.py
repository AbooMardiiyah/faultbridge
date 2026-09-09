from __future__ import annotations

import unittest

from faultbridge_eval.prepare_afriswitch import Candidate, stratified_selection


class AfriSwitchSamplingTests(unittest.TestCase):
    def test_selection_is_deterministic_and_spans_strata(self) -> None:
        candidates = [
            Candidate(
                index=index,
                filename=f"source_{index}.wav",
                transcription="text",
                transcription_tagged="text",
                cmi=float(index),
                switch_points=index,
                duration=float(index + 1),
                stratum=("low" if index < 3 else "high", "1-2", "short"),
            )
            for index in range(6)
        ]

        first = stratified_selection(candidates, 4, seed=7, language="hausa")
        second = stratified_selection(candidates, 4, seed=7, language="hausa")

        self.assertEqual(first, second)
        self.assertEqual({candidate.stratum[0] for candidate in first}, {"low", "high"})


if __name__ == "__main__":
    unittest.main()
