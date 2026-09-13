import unittest
from datetime import UTC, datetime

from faultbridge.domain.orchestrator import format_restoration_time


class RestorationTimeTests(unittest.TestCase):
    def test_formats_utc_as_spoken_west_africa_time(self) -> None:
        value = datetime(2026, 9, 13, 19, 30, tzinfo=UTC)

        self.assertEqual(
            format_restoration_time(value),
            "8:30 PM West Africa Time on 13 September 2026",
        )

    def test_treats_naive_provider_timestamp_as_utc(self) -> None:
        value = datetime(2026, 9, 13, 19, 30)  # noqa: DTZ001 - provider value

        self.assertEqual(
            format_restoration_time(value),
            "8:30 PM West Africa Time on 13 September 2026",
        )

    def test_handles_missing_estimate(self) -> None:
        self.assertEqual(format_restoration_time(None), "being assessed")


if __name__ == "__main__":
    unittest.main()
