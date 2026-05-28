from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import OutboxRepository, PaymentRepository
from app.domain.entities import Payment
from app.domain.enums import Currency, PaymentStatus
from app.infrastructure.database.models import OutboxModel, PaymentModel


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
            .where(PaymentModel.id == payment_id)
            .values(status=status, processed_at=processed_at)
            .returning(PaymentModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await self._session.flush()
            return _to_entity(row)
        return None


class SqlAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, payment_id: UUID, payload: dict) -> None:
        row = OutboxModel(
            id=uuid4(),
            payment_id=payment_id,
            event_type=payload.get("event", "payments.new"),
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()

    async def fetch_pending(self, limit: int) -> list[tuple[UUID, dict]]:
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.processed_at.is_(None))
            .order_by(OutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [(row.id, row.payload) for row in rows]

    async def mark_processed(self, outbox_id: UUID) -> None:
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == outbox_id)
            .values(processed_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)
        await self._session.flush()
