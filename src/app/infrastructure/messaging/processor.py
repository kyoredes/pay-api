import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from app.domain.enums import PaymentStatus
from app.infrastructure.database.repositories import SqlAlchemyPaymentRepository
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.webhooks.client import WebhookClient, WebhookPayload

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, webhook_client: WebhookClient) -> None:
        self._webhooks = webhook_client

    async def process(self, payment_id: UUID) -> None:
        await asyncio.sleep(random.uniform(2.0, 5.0))
        success = random.random() < 0.9
        status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED
        processed_at = datetime.now(timezone.utc)

        factory = get_session_factory()
        async with factory() as session:
            repo = SqlAlchemyPaymentRepository(session)
            payment = await repo.update_status(
                payment_id,
                status.value,
                processed_at,
            )
            if not payment:
                raise ValueError(f"payment {payment_id} not found")
            await session.commit()

        try:
            await self._webhooks.deliver(
                payment.webhook_url,
                WebhookPayload(
                    payment_id=str(payment.id),
                    status=payment.status.value,
                    amount=str(payment.amount),
                    currency=payment.currency.value,
                    description=payment.description,
                    metadata=payment.metadata,
                    processed_at=processed_at.isoformat(),
                ),
            )
        except Exception:
            logger.exception("webhook failed for payment %s", payment_id)
