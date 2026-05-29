from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.entities import Payment



class PaymentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        ...

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        ...

    @abstractmethod
    async def save(self, payment: Payment) -> Payment:
        ...

    @abstractmethod
    async def update_status(
        self,
        payment_id: UUID,
        status: str,
        processed_at: datetime | None,
    ) -> Payment | None:
        ...


class PaymentOutboxRepository(ABC):
    @abstractmethod
    async def enqueue(self, payment_id: UUID, payload: dict) -> None:
        ...

    @abstractmethod
    async def claim_pending(self, limit: int, claim_ttl_seconds: float) -> list[tuple[UUID, dict]]:
        ...

    @abstractmethod
    async def mark_processed(self, outbox_id: UUID) -> None:
        ...

    @abstractmethod
    async def release_claim(self, outbox_id: UUID) -> None:
        ...
