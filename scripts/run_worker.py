import asyncio

from faultbridge.config import Settings
from faultbridge.services.database import Database
from faultbridge.services.workers import ActionWorker, WebhookDispatcher


def dispatcher(url: str | None, token: str | None) -> WebhookDispatcher | None:
    if not url:
        return None
    if not token:
        raise RuntimeError("OPERATOR_WEBHOOK_TOKEN is required for action delivery")
    return WebhookDispatcher(url, token)


async def main() -> None:
    settings = Settings()
    token = (
        settings.operator_webhook_token.get_secret_value()
        if settings.operator_webhook_token
        else None
    )
    database = Database(settings.database_url)
    worker = ActionWorker(
        database,
        compensation=dispatcher(settings.compensation_webhook_url, token),
        callback=dispatcher(settings.callback_webhook_url, token),
    )
    try:
        handled = await worker.run_once()
        print(f"Processed {handled} queued command(s).")
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main())
