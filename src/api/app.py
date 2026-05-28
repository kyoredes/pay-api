import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import payments
from src.config import get_settings
from src.infrastructure.database.session import close_db, init_db
from src.infrastructure.messaging.broker import create_broker
from src.infrastructure.messaging.publisher import PaymentEventPublisher
from src.infrastructure.outbox.relay import OutboxRelay


async def _connect_broker(broker, attempts: int = 10, delay: float = 2.0) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            await broker.connect()
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(delay)
    if last_error:
        raise last_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    init_db(settings.database_url)

    broker = create_broker(settings)
    await _connect_broker(broker)
    publisher = PaymentEventPublisher(broker, settings)
    relay = OutboxRelay(settings, publisher)
    task = asyncio.create_task(relay.run())
    app.state.broker = broker

    yield

    relay.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await broker.close()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="Pay API", lifespan=lifespan)
    app.include_router(payments.router)
    return app
