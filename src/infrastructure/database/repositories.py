from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.repo import PaymentOutboxRepository, PaymentRepository, WebhookOutboxEntry, WebhookOutboxRepository
from src.domain.entities import Payment
from src.domain.enums import Currency, PaymentStatus
from src.infrastructure.database.models import PaymentOutboxModel, PaymentModel, WebhookOutboxModel


def _to_entity(row: PaymentModel) -> Payment:
    return Payment(
        id=row.id,
        amount=row.amount,
        currency=Currency(row.currency),
        description=row.description,
        metadata=row.metadata_ or {},
        status=PaymentStatus(row.status),
        idempotency_key=row.idempotency_key,
        webhook_url=row.webhook_url,
        created_at=row.created_at,
        processed_at=row.processed_at,
    )


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        row = await self._session.get(PaymentModel, payment_id)
        return _to_entity(row) if row else None

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        stmt = select(PaymentModel).where(PaymentModel.idempotency_key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def save(self, payment: Payment) -> Payment:
        model = PaymentModel(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency.value,
            description=payment.description,
            metadata_=payment.metadata,
            status=payment.status.value,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return payment

    async def update_status(
        self,
        payment_id: UUID,
        status: str,
        processed_at: datetime | None,
    ) -> Payment | None:
        stmt = (
            update(PaymentModel)
            .where(
                PaymentModel.id == payment_id,
                PaymentModel.status == PaymentStatus.PENDING.value,
            )
            .values(status=status, processed_at=processed_at)
            .returning(PaymentModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await self._session.flush()
            return _to_entity(row)
        return None


class SqlAlchemyPaymentOutboxRepository(PaymentOutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, payment_id: UUID, payload: dict) -> None:
        row = PaymentOutboxModel(
            id=uuid4(),
            payment_id=payment_id,
            event_type=payload.get("event", "payments.new"),
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()

    async def claim_pending(self, limit: int, claim_ttl_seconds: float) -> list[tuple[UUID, dict]]:
        now = datetime.now(timezone.utc)
        claim_expired_before = now - timedelta(seconds=claim_ttl_seconds)
        stmt = (
            select(PaymentOutboxModel)
            .where(
                PaymentOutboxModel.processed_at.is_(None),
                (PaymentOutboxModel.claimed_at.is_(None)) | (PaymentOutboxModel.claimed_at < claim_expired_before),
            )
            .order_by(PaymentOutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        for row in rows:
            row.claimed_at = now
        await self._session.flush()
        return [(row.id, row.payload) for row in rows]

    async def mark_processed(self, outbox_id: UUID) -> None:
        stmt = (
            update(PaymentOutboxModel)
            .where(PaymentOutboxModel.id == outbox_id)
            .values(
                processed_at=datetime.now(timezone.utc),
                claimed_at=None,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def release_claim(self, outbox_id: UUID) -> None:
        stmt = (
            update(PaymentOutboxModel)
            .where(PaymentOutboxModel.id == outbox_id)
            .values(claimed_at=None)
        )
        await self._session.execute(stmt)
        await self._session.flush()


class SqlAlchemyWebhookOutboxRepository(WebhookOutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, payment_id: UUID, url: str, payload: dict) -> None:
        row = WebhookOutboxModel(
            id=uuid4(),
            payment_id=payment_id,
            url=url,
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()

    async def claim_pending(self, limit: int, claim_ttl_seconds: float) -> list[WebhookOutboxEntry]:
        now = datetime.now(timezone.utc)
        claim_expired_before = now - timedelta(seconds=claim_ttl_seconds)
        stmt = (
            select(WebhookOutboxModel)
            .where(
                WebhookOutboxModel.delivered_at.is_(None),
                WebhookOutboxModel.failed_at.is_(None),
                (WebhookOutboxModel.next_attempt_at.is_(None))
                | (WebhookOutboxModel.next_attempt_at <= now),
                (WebhookOutboxModel.claimed_at.is_(None))
                | (WebhookOutboxModel.claimed_at < claim_expired_before),
            )
            .order_by(WebhookOutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        for row in rows:
            row.claimed_at = now
        await self._session.flush()
        return [
            WebhookOutboxEntry(
                id=row.id,
                url=row.url,
                payload=row.payload,
                attempts=row.attempts,
            )
            for row in rows
        ]

    async def mark_delivered(self, outbox_id: UUID) -> None:
        stmt = (
            update(WebhookOutboxModel)
            .where(WebhookOutboxModel.id == outbox_id)
            .values(
                delivered_at=datetime.now(timezone.utc),
                claimed_at=None,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_failed(self, outbox_id: UUID, error: str) -> None:
        stmt = (
            update(WebhookOutboxModel)
            .where(WebhookOutboxModel.id == outbox_id)
            .values(
                failed_at=datetime.now(timezone.utc),
                last_error=error,
                claimed_at=None,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def schedule_retry(
        self,
        outbox_id: UUID,
        attempts: int,
        next_attempt_at: datetime,
        error: str,
    ) -> None:
        stmt = (
            update(WebhookOutboxModel)
            .where(WebhookOutboxModel.id == outbox_id)
            .values(
                attempts=attempts,
                next_attempt_at=next_attempt_at,
                last_error=error,
                claimed_at=None,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def release_claim(self, outbox_id: UUID) -> None:
        stmt = (
            update(WebhookOutboxModel)
            .where(WebhookOutboxModel.id == outbox_id)
            .values(claimed_at=None)
        )
        await self._session.execute(stmt)
        await self._session.flush()
