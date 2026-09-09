import unittest

from faultbridge.adapters.sahara import language_code, pcm16_chunks


class SaharaAdapterTests(unittest.TestCase):
    def test_maps_all_submission_language_pairs(self) -> None:
        self.assertEqual(language_code("Hausa-English"), "ha")
        self.assertEqual(language_code("Igbo-English"), "ig")
        self.assertEqual(language_code("Pidgin-English"), "pcm")
        self.assertEqual(language_code("Yoruba-English"), "yo")

    def test_chunks_preserve_audio(self) -> None:
        audio = bytes(range(256)) * 150
        chunks = pcm16_chunks(audio)
        self.assertEqual(b"".join(chunks), audio)
        self.assertTrue(all(1024 <= len(chunk) <= 32 * 1024 for chunk in chunks))

    def test_short_audio_is_padded_to_api_minimum(self) -> None:
        audio = b"\x01\x02" * 100
        chunks = pcm16_chunks(audio)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 1024)
        self.assertTrue(chunks[0].startswith(audio))

    def test_rejects_partial_pcm_sample(self) -> None:
        with self.assertRaises(ValueError):
            pcm16_chunks(b"\x00")

    def test_rejects_unknown_language_pair(self) -> None:
        with self.assertRaises(ValueError):
            language_code("French-English")


if __name__ == "__main__":
    unittest.main()
