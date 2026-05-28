from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.ports import OutboxRepository, PaymentRepository
from app.domain.entities import Payment
from app.domain.enums import Currency, PaymentStatus


@dataclass(slots=True)
class CreatePaymentCommand:
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict
    webhook_url: str
    idempotency_key: str


class PaymentService:
    def __init__(
        self,
        payments: PaymentRepository,
        outbox: OutboxRepository,
    ) -> None:
        self._payments = payments
        self._outbox = outbox

    async def create(self, command: CreatePaymentCommand) -> tuple[Payment, bool]:
        existing = await self._payments.get_by_idempotency_key(command.idempotency_key)
        if existing:
            return existing, False

        now = datetime.now(timezone.utc)
        payment = Payment(
            id=uuid4(),
            amount=command.amount,
            currency=command.currency,
            description=command.description,
            metadata=command.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=command.idempotency_key,
            webhook_url=command.webhook_url,
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
