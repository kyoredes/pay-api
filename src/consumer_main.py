import asyncio

from faststream import FastStream

from src.config import get_settings
from src.infrastructure.database.session import close_db, init_db
from src.infrastructure.messaging.consumer import broker, webhook_client

app = FastStream(broker)


@app.on_startup
async def startup() -> None:
    settings = get_settings()
    init_db(settings.database_url)
    await webhook_client.startup()


@app.on_shutdown
async def shutdown() -> None:
    await webhook_client.close()
    await close_db()


def main() -> None:
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
