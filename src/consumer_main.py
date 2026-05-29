import asyncio

from faststream import FastStream

from src.config import get_settings
from src.infrastructure.database.session import close_db, init_db
from src.infrastructure.messaging.consumer import broker
from src.infrastructure.webhooks.client import WebhookClient
from src.infrastructure.webhooks.relay import WebhookRelay

app = FastStream(broker)

_webhook_client: WebhookClient | None = None
_webhook_relay: WebhookRelay | None = None
_webhook_relay_task: asyncio.Task | None = None


@app.on_startup
async def startup() -> None:
    global _webhook_client, _webhook_relay, _webhook_relay_task

    settings = get_settings()
    init_db(settings.database_url)

    _webhook_client = WebhookClient()
    _webhook_relay = WebhookRelay(settings, _webhook_client)
    _webhook_relay_task = asyncio.create_task(_webhook_relay.run())


@app.on_shutdown
async def shutdown() -> None:
    global _webhook_client, _webhook_relay, _webhook_relay_task

    if _webhook_relay is not None:
        _webhook_relay.stop()

    if _webhook_relay_task is not None:
        _webhook_relay_task.cancel()
        try:
            await _webhook_relay_task
        except asyncio.CancelledError:
            pass

    if _webhook_client is not None:
        await _webhook_client.close()

    await close_db()


def main() -> None:
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
