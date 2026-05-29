from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from src.application.schemas import NewPayment
from src.application.repo import PaymentOutboxRepository, PaymentRepository
from src.domain.entities import Payment
from src.domain.enums import PaymentStatus


class IdempotencyMismatchError(Exception):
    pass


def ensure_idempotent_match(existing: Payment, new_payment: NewPayment) -> None:
    if (
        existing.amount == new_payment.amount
        and existing.currency == new_payment.currency
        and existing.description == new_payment.description
        and existing.metadata == new_payment.metadata
        and existing.webhook_url == new_payment.webhook_url
    ):
        return
    raise IdempotencyMismatchError(
        "Idempotency-Key reused with different request parameters"
    )


class PaymentService:
    def __init__(
        self,
        payments: PaymentRepository,
        outbox: PaymentOutboxRepository,
    ) -> None:
        self._payments = payments
        self._outbox = outbox

    async def create(self, new_payment: NewPayment) -> tuple[Payment, bool]:
        existing = await self._payments.get_by_idempotency_key(new_payment.idempotency_key)
        if existing:
            ensure_idempotent_match(existing, new_payment)
            return existing, False

        now = datetime.now(timezone.utc)
        payment = Payment(
            id=uuid4(),
            amount=new_payment.amount,
            currency=new_payment.currency,
            description=new_payment.description,
            metadata=new_payment.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=new_payment.idempotency_key,
            webhook_url=new_payment.webhook_url,
            created_at=now,
            processed_at=None,
        )
        saved = await self._payments.save(payment)
        await self._outbox.enqueue(
            saved.id,
            {
                "event": "payments.new",
                "payment_id": str(saved.id),
                "amount": str(saved.amount),
                "currency": saved.currency.value,
            },
        )
        return saved, True

    async def get(self, payment_id: UUID) -> Payment | None:
        return await self._payments.get_by_id(payment_id)
