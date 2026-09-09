import json
import unittest

import httpx

from faultbridge.adapters.llm import OpenAICompatibleAgentModel


class LlmAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_validates_structured_complaint_analysis(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "symptom": "data_unavailable",
                                        "language_pair": "Pidgin-English",
                                        "consent": True,
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        model = OpenAICompatibleAgentModel(
            api_key="test-key",
            model="provider-model",
            base_url="https://provider.invalid/v1",
            transport=httpx.MockTransport(handler),
        )
        analysis = await model.analyze_complaint(
            "Data no dey work", default_language_pair="Pidgin-English"
        )
        self.assertEqual(analysis.symptom, "data_unavailable")
        self.assertEqual(analysis.language_pair, "Pidgin-English")
        self.assertTrue(analysis.consent)

    async def test_unknown_values_are_constrained(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"symptom":"invented","language_pair":"French"}'
                                )
                            }
                        }
                    ]
                },
            )

        model = OpenAICompatibleAgentModel(
            api_key="test-key",
            model="provider-model",
            base_url="https://provider.invalid/v1",
            transport=httpx.MockTransport(handler),
        )
        analysis = await model.analyze_complaint(
            "Unknown issue", default_language_pair="Hausa-English"
        )
        self.assertEqual(analysis.symptom, "unknown")
        self.assertEqual(analysis.language_pair, "Hausa-English")


if __name__ == "__main__":
    unittest.main()
