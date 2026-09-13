import unittest

from faultbridge_eval.prepare_pii_cases import build_cases

from faultbridge.services.privacy import find_pii, pseudonymize_caller, redact_text


class PrivacyTests(unittest.TestCase):
    def test_redacts_phone_email_and_account(self) -> None:
        text = "Call 08031234567, email ada@example.com, account number AB12345678"
        safe = redact_text(text)
        self.assertNotIn("08031234567", safe)
        self.assertNotIn("ada@example.com", safe)
        self.assertNotIn("AB12345678", safe)
        self.assertIn("[PHONE_REDACTED]", safe)
        self.assertIn("[EMAIL_REDACTED]", safe)
        self.assertIn("[ACCOUNT_REDACTED]", safe)

    def test_redacts_spaced_numeric_identifier(self) -> None:
        safe = redact_text("My NIN is 1234 567 8901 and card is 5399-1234-5678-9012")
        self.assertNotIn("1234 567 8901", safe)
        self.assertNotIn("5399-1234-5678-9012", safe)
        self.assertIn("[NUMERIC_IDENTIFIER_REDACTED]", safe)

    def test_returns_typed_spans_for_benchmarking(self) -> None:
        text = "Send it to ada@example.com or 08031234567"

        matches = find_pii(text)

        self.assertEqual([match.pii_type for match in matches], ["email", "phone"])
        self.assertEqual(
            [text[match.start : match.end] for match in matches],
            ["ada@example.com", "08031234567"],
        )

    def test_preserves_account_label_and_redacts_only_identifier(self) -> None:
        text = "My SIM serial is ICC-12345678 and it has no service."

        matches = find_pii(text)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, "account")
        self.assertEqual(text[matches[0].start : matches[0].end], "ICC-12345678")
        self.assertIn("SIM serial is [ACCOUNT_REDACTED]", redact_text(text))

    def test_pseudonym_is_stable_and_hides_caller(self) -> None:
        secret = "a-secret-with-enough-length"
        first = pseudonymize_caller("08031234567", secret)
        second = pseudonymize_caller("08031234567", secret)
        self.assertEqual(first, second)
        self.assertNotIn("08031234567", first)

    def test_rejects_weak_pseudonym_secret(self) -> None:
        with self.assertRaises(ValueError):
            pseudonymize_caller("08031234567", "short")

    def test_frozen_privacy_panel_is_balanced_and_independently_labelled(self) -> None:
        cases = build_cases()

        self.assertEqual(len(cases), 100)
        self.assertEqual(
            {
                pair: sum(case["language_pair"] == pair for case in cases)
                for pair in {str(case["language_pair"]) for case in cases}
            },
            {
                "Hausa-English": 25,
                "Igbo-English": 25,
                "Pidgin-English": 25,
                "Yoruba-English": 25,
            },
        )
        for case in cases:
            text = str(case["text"])
            for span in case["expected_spans"]:
                self.assertTrue(text[int(span["start"]) : int(span["end"])])


if __name__ == "__main__":
    unittest.main()
