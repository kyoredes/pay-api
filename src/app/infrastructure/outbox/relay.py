import asyncio
import logging

from app.config import Settings
from app.infrastructure.database.repositories import SqlAlchemyOutboxRepository
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.messaging.publisher import PaymentEventPublisher

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(
        self,
        settings: Settings,
        publisher: PaymentEventPublisher,
    ) -> None:
        self._settings = settings
        self._publisher = publisher
        self._running = False

    async def run(self) -> None:
        self._running = True
        factory = get_session_factory()
        while self._running:
            try:
                async with factory() as session:
                    outbox = SqlAlchemyOutboxRepository(session)
                    pending = await outbox.fetch_pending(self._settings.outbox_batch_size)
                    for outbox_id, payload in pending:
                        await self._publisher.publish_new_payment(payload)
                        await outbox.mark_processed(outbox_id)
                    await session.commit()
            except Exception:
                logger.exception("outbox relay tick failed")
            await asyncio.sleep(self._settings.outbox_poll_interval)

    def stop(self) -> None:
        self._running = False
