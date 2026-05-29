from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from src.application.schemas import WebhookOutboxEntry
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


class WebhookOutboxRepository(ABC):
    @abstractmethod
    async def enqueue(self, payment_id: UUID, url: str, payload: dict) -> None:
        ...

    @abstractmethod
    async def claim_pending(
        self,
        limit: int,
        claim_ttl_seconds: float,
    ) -> list[WebhookOutboxEntry]:
        ...

    @abstractmethod
    async def mark_delivered(self, outbox_id: UUID) -> None:
        ...

    @abstractmethod
    async def mark_failed(self, outbox_id: UUID, error: str) -> None:
        ...

    @abstractmethod
    async def schedule_retry(
        self,
        outbox_id: UUID,
        attempts: int,
        next_attempt_at: datetime,
        error: str,
    ) -> None:
        ...

    @abstractmethod
    async def release_claim(self, outbox_id: UUID) -> None:
        ...
