from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from faultbridge.adapters.base import ComplaintAnalysis

SUPPORTED_LANGUAGE_PAIRS = {
    "Hausa-English",
    "Igbo-English",
    "Pidgin-English",
    "Yoruba-English",
}

SYSTEM_PROMPT = """You extract routing facts from Nigerian telco calls.
Return one JSON object only with symptom, language_pair, and consent.
symptom must be one of: no_service, data_unavailable, call_quality,
rapid_data_depletion, billing_dispute, recharge_failed, sim_issue, unknown.
language_pair must be Hausa-English, Igbo-English, Pidgin-English, or
Yoruba-English. consent is true only when the transcript explicitly grants
automated processing or the application has supplied a prior consent statement.
Do not invent account, network, location, or outage facts."""


class AgentModelError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleAgentModel:
    """Structured complaint analysis for OpenAI-compatible chat providers."""

    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 30.0
    transport: httpx.AsyncBaseTransport | None = None

    async def _json_completion(self, system: str, user: str) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("agent provider API key is required")
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        if response.is_error:
            raise AgentModelError(
                f"agent provider failed with HTTP {response.status_code}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise AgentModelError(
                "agent provider returned invalid structured data"
            ) from error
        if not isinstance(payload, dict):
            raise AgentModelError("agent provider response must be a JSON object")
        return payload

    async def analyze_complaint(
        self, transcript: str, *, default_language_pair: str
    ) -> ComplaintAnalysis:
        payload = await self._json_completion(
            SYSTEM_PROMPT,
            f"Default language pair: {default_language_pair}\nTranscript: {transcript}",
        )
        language_pair = str(payload.get("language_pair", default_language_pair))
        if language_pair not in SUPPORTED_LANGUAGE_PAIRS:
            language_pair = default_language_pair
        symptom = str(payload.get("symptom", "unknown")).strip().lower()
        allowed_symptoms = {
            "no_service",
            "data_unavailable",
            "call_quality",
            "rapid_data_depletion",
            "billing_dispute",
            "recharge_failed",
            "sim_issue",
            "unknown",
        }
        if symptom not in allowed_symptoms:
            symptom = "unknown"
        return ComplaintAnalysis(
            symptom=symptom,
            language_pair=language_pair,
            consent=payload.get("consent") is True,
        )

    async def confirms_resolution(self, transcript: str) -> bool:
        payload = await self._json_completion(
            'Return JSON only: {"resolved": true|false}. Set true only when '
            "the caller clearly confirms service now works.",
            transcript,
        )
        return payload.get("resolved") is True
