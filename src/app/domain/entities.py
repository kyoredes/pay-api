from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums import Currency, PaymentStatus


@dataclass(slots=True)
class Payment:
    id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
