import asyncio

from faststream import FastStream

from src.config import get_settings
from src.infrastructure.database.session import close_db, init_db
from src.infrastructure.messaging.consumer import broker

app = FastStream(broker)


@app.on_startup
async def startup() -> None:
    init_db(get_settings().database_url)


@app.on_shutdown
async def shutdown() -> None:
    await close_db()


def main() -> None:
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
