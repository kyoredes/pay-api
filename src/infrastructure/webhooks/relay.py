import asyncio
import logging
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.infrastructure.database.repositories import SqlAlchemyWebhookOutboxRepository
from src.infrastructure.database.session import get_session_factory
from src.infrastructure.webhooks.client import WebhookClient
from src.infrastructure.webhooks.schemas import WebhookPayload

logger = logging.getLogger(__name__)


class WebhookRelay:
    def __init__(self, settings: Settings, webhook_client: WebhookClient) -> None:
        self._settings = settings
        self._webhooks = webhook_client
        self._running = False

    async def run(self) -> None:
        self._running = True
        factory = get_session_factory()
        while self._running:
            try:
                await self._tick(factory)
            except Exception:
                logger.exception("webhook relay tick failed")
            await asyncio.sleep(self._settings.outbox_poll_interval)

    async def _tick(self, factory) -> None:
        async with factory() as session:
            outbox = SqlAlchemyWebhookOutboxRepository(session)
            pending = await outbox.claim_pending(
                self._settings.outbox_batch_size,
                self._settings.outbox_claim_ttl,
            )
            await session.commit()

        for entry in pending:
            payload = WebhookPayload(**entry.payload)
            try:
                await self._webhooks.deliver(entry.url, payload)
            except Exception as exc:
                logger.exception(
                    "webhook delivery failed for payment %s",
                    payload.payment_id,
                )
                await self._record_retry(factory, entry, str(exc))
                continue

            async with factory() as session:
                outbox = SqlAlchemyWebhookOutboxRepository(session)
                await outbox.mark_delivered(entry.id)
                await session.commit()

    async def _record_retry(self, factory, entry, error: str) -> None:
        attempts = entry.attempts + 1
        async with factory() as session:
            outbox = SqlAlchemyWebhookOutboxRepository(session)
            if attempts >= self._settings.webhook_max_attempts:
                await outbox.mark_failed(entry.id, error)
            else:
                delay = self._settings.webhook_base_delay * (2 ** (attempts - 1))
                next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await outbox.schedule_retry(entry.id, attempts, next_attempt_at, error)
            await session.commit()

    def stop(self) -> None:
        self._running = False
