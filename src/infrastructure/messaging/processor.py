import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from src.config import Settings
from src.domain.entities import Payment
from src.domain.enums import PaymentStatus
from src.infrastructure.database.repositories import SqlAlchemyPaymentRepository
from src.infrastructure.database.session import get_session_factory
from src.infrastructure.messaging.exceptions import (
    PaymentNotFoundError,
    WebhookDeliveryError,
)
from src.infrastructure.webhooks.client import WebhookClient
from src.infrastructure.webhooks.schemas import WebhookPayload

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Single consumer handler: gets the message, emulates the gateway, updates
    the status and delivers the webhook itself with retries (3 attempts,
    exponential backoff). If delivery fails after all attempts, the message is
    sent to the DLQ by the consumer.
    """

    def __init__(self, webhook_client: WebhookClient, settings: Settings) -> None:
        self._webhooks = webhook_client
        self._settings = settings

    async def process(self, payment_id: UUID) -> None:
        factory = get_session_factory()

        async with factory() as session:
            repo = SqlAlchemyPaymentRepository(session)
            payment = await repo.get_by_id(payment_id)

        if payment is None:
            logger.error("payment %s not found", payment_id)
            raise PaymentNotFoundError(payment_id)

        if payment.status != PaymentStatus.PENDING:
            logger.info(
                "payment %s already in status %s, skipping duplicate message",
                payment_id,
                payment.status,
            )
            return

        await asyncio.sleep(random.uniform(2.0, 5.0))
        success = random.random() < 0.9
        status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED
        processed_at = datetime.now(timezone.utc)

        async with factory() as session:
            repo = SqlAlchemyPaymentRepository(session)
            payment = await repo.update_status(payment_id, status.value, processed_at)
            await session.commit()

        if not payment:
            logger.info(
                "payment %s already processed by another worker, skipping duplicate message",
                payment_id,
            )
            return

        await self._deliver_webhook(payment, processed_at)

    async def _deliver_webhook(self, payment: Payment, processed_at: datetime) -> None:
        payload = WebhookPayload(
            payment_id=str(payment.id),
            status=payment.status.value,
            amount=str(payment.amount),
            currency=payment.currency.value,
            description=payment.description,
            metadata=payment.metadata,
            processed_at=processed_at.isoformat(),
        )
        max_attempts = self._settings.webhook_max_attempts
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                await self._webhooks.deliver(payment.webhook_url, payload)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "webhook attempt %d/%d failed for payment %s: %s",
                    attempt,
                    max_attempts,
                    payment.id,
                    exc,
                )
                if attempt < max_attempts:
                    delay = self._settings.webhook_base_delay * 2 ** (attempt - 1)
                    await asyncio.sleep(delay)
                continue

            logger.info(
                "webhook delivered for payment %s on attempt %d", payment.id, attempt
            )
            return

        raise WebhookDeliveryError(payment.id, last_error)
