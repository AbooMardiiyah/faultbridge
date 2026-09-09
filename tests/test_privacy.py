import unittest

from faultbridge.services.privacy import pseudonymize_caller, redact_text


class PrivacyTests(unittest.TestCase):
    def test_redacts_phone_email_and_account(self) -> None:
        text = (
            "Call 08031234567, email ada@example.com, "
            "account number AB12345678"
        )
        safe = redact_text(text)
        self.assertNotIn("08031234567", safe)
        self.assertNotIn("ada@example.com", safe)
        self.assertNotIn("AB12345678", safe)
        self.assertIn("[PHONE_REDACTED]", safe)
        self.assertIn("[EMAIL_REDACTED]", safe)
        self.assertIn("[ACCOUNT_REDACTED]", safe)

    def test_pseudonym_is_stable_and_hides_caller(self) -> None:
        secret = "a-secret-with-enough-length"
        first = pseudonymize_caller("08031234567", secret)
        second = pseudonymize_caller("08031234567", secret)
        self.assertEqual(first, second)
        self.assertNotIn("08031234567", first)

    def test_rejects_weak_pseudonym_secret(self) -> None:
        with self.assertRaises(ValueError):
            pseudonymize_caller("08031234567", "short")


if __name__ == "__main__":
    unittest.main()

