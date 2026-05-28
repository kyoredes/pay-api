from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.domain.enums import Currency, PaymentStatus


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = ""
    metadata: dict = Field(default_factory=dict)
    webhook_url: HttpUrl


class CreatePaymentResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetailResponse(BaseModel):
    payment_id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_entity(cls, payment) -> "PaymentDetailResponse":
        return cls(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.metadata,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )
