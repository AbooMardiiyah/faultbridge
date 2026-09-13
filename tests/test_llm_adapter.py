import json
import unittest

import httpx

from faultbridge.adapters.llm import OpenAICompatibleAgentModel
from faultbridge.adapters.registry import build_agent_model
from faultbridge.config import Settings


class LlmAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_validates_structured_complaint_analysis(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["max_tokens"], 128)
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

    def test_together_provider_uses_openai_compatible_adapter(self) -> None:
        model = build_agent_model(
            Settings(
                database_url="postgresql://test.invalid/faultbridge",
                faultbridge_pseudonym_secret="pseudonym-secret-at-least-32-chars",
                faultbridge_internal_api_key="internal-secret-at-least-32-chars",
                agent_provider="together",
                agent_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                together_api_key="together-test-key",
            )
        )

        self.assertIsInstance(model, OpenAICompatibleAgentModel)
        self.assertEqual(model.api_key, "together-test-key")
        self.assertEqual(model.base_url, "https://api.together.ai/v1")
        self.assertEqual(model.model, "meta-llama/Llama-3.3-70B-Instruct-Turbo")


if __name__ == "__main__":
    unittest.main()
