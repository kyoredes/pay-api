from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Payment


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
        processed_at,
    ) -> Payment | None:
        ...


class OutboxRepository(ABC):
    @abstractmethod
    async def enqueue(self, payment_id: UUID, payload: dict) -> None:
        ...

    @abstractmethod
    async def fetch_pending(self, limit: int) -> list[tuple[UUID, dict]]:
        ...

    @abstractmethod
    async def mark_processed(self, outbox_id: UUID) -> None:
        ...
