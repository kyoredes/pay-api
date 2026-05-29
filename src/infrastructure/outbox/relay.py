import asyncio
import logging

from src.config import Settings
from src.infrastructure.database.repositories import SqlAlchemyPaymentOutboxRepository
from src.infrastructure.database.session import get_session_factory
from src.infrastructure.messaging.publisher import PaymentEventPublisher

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
                await self._tick(factory)
            except Exception:
                logger.exception("outbox relay tick failed")
            await asyncio.sleep(self._settings.outbox_poll_interval)

    async def _tick(self, factory) -> None:
        async with factory() as session:
            outbox = SqlAlchemyPaymentOutboxRepository(session)
            pending = await outbox.claim_pending(
                self._settings.outbox_batch_size,
                self._settings.outbox_claim_ttl,
            )
            await session.commit()

        for outbox_id, payload in pending:
            try:
                await self._publisher.publish_new_payment(payload)
            except Exception:
                logger.exception("failed to publish outbox payload %s", payload.get("payment_id"))
                async with factory() as session:
                    outbox = SqlAlchemyPaymentOutboxRepository(session)
                    await outbox.release_claim(outbox_id)
                    await session.commit()
                continue

            async with factory() as session:
                outbox = SqlAlchemyPaymentOutboxRepository(session)
                await outbox.mark_processed(outbox_id)
                await session.commit()

    def stop(self) -> None:
        self._running = False
