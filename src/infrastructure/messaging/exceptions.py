from uuid import UUID


class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        super().__init__(f"payment {payment_id} not found")


class WebhookDeliveryError(Exception):
    def __init__(self, payment_id: UUID, error: Exception | None = None) -> None:
        self.payment_id = payment_id
        self.error = error
        super().__init__(f"webhook delivery failed for payment {payment_id}: {error}")