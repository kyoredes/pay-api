from pydantic import BaseModel
from decimal import Decimal

from src.domain.enums import Currency

class NewPayment(BaseModel):
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict
    webhook_url: str
    idempotency_key: str