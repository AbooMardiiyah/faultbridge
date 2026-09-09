from __future__ import annotations

import unittest

from faultbridge_eval.audio_conditions import transform


class AudioConditionTests(unittest.TestCase):
    def test_every_transform_is_deterministic_and_preserves_length(self) -> None:
        samples = [int(10_000 * ((index % 20) / 20 - 0.5)) for index in range(3200)]
        conditions = (
            "pstn-mulaw",
            "noise-10db",
            "packet-loss-3pct",
            "burst-loss-5pct",
            "mild-reverb",
        )
        for condition in conditions:
            with self.subTest(condition=condition):
                first = transform(samples, 16_000, condition, seed=7)
                second = transform(samples, 16_000, condition, seed=7)
                self.assertEqual(first, second)
                self.assertEqual(len(first), len(samples))
                self.assertNotEqual(first, samples)


if __name__ == "__main__":
    unittest.main()
