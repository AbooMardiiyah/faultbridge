from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from faultbridge.services.database import Database


class DeliveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WebhookDispatcher:
    endpoint: str
    bearer_token: str
    timeout_seconds: float = 20.0

    async def deliver(self, command: dict[str, Any]) -> str:
        command_id = str(command["command_id"])
        payload = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in command.items()
            if key not in {"last_error", "external_reference"}
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Idempotency-Key": command_id,
                },
                json=payload,
            )
        if response.is_error:
            raise DeliveryError(f"operator connector returned {response.status_code}")
        body = response.json() if response.content else {}
        if not isinstance(body, dict):
            raise DeliveryError("operator connector returned an invalid response")
        return str(body.get("reference") or body.get("id") or command_id)


class ActionWorker:
    def __init__(
        self,
        database: Database,
        *,
        compensation: WebhookDispatcher | None,
        callback: WebhookDispatcher | None,
        max_attempts: int = 5,
    ) -> None:
        self.database = database
        self.compensation = compensation
        self.callback = callback
        self.max_attempts = max_attempts

    async def run_once(self) -> int:
        handled = 0
        handled += await self._process(
            "compensation_commands",
            self.database.claim_compensation,
            self.compensation,
        )
        handled += await self._process(
            "callback_commands",
            self.database.claim_callback,
            self.callback,
        )
        return handled

    async def _process(self, table: str, claim: Any, dispatcher: Any) -> int:
        if dispatcher is None:
            return 0
        command = claim()
        if command is None:
            return 0
        try:
            reference = await dispatcher.deliver(command)
        except (httpx.HTTPError, DeliveryError) as error:
            terminal = command["attempt_count"] >= self.max_attempts
            self.database.finish_command(
                table,
                command["command_id"],
                status="failed" if terminal else "queued",
                error=str(error)[:500],
            )
        else:
            self.database.finish_command(
                table,
                command["command_id"],
                status="completed",
                external_reference=reference,
            )
        return 1
