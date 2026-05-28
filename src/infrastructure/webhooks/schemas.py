from pydantic import BaseModel

class WebhookPayload(BaseModel):
    payment_id: str
    status: str
    amount: str
    currency: str
    description: str
    metadata: dict
    processed_at: str | None
