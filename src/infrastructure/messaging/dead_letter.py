import logging
from uuid import UUID

from src.infrastructure.database.repositories import SqlAlchemyDeadLetterRepository
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


class DeadLetterArchiver:
    """Drains the DLQ into the `dead_letters` table so permanently failed
    messages are retained for inspection / manual replay instead of being
    logged and discarded.
    """

    @staticmethod
    def _extract_payment_id(message: dict) -> UUID | None:
        raw = message.get("payment_id") if isinstance(message, dict) else None
        if not isinstance(raw, str):
            return None
        try:
            return UUID(raw)
        except ValueError:
            return None

    async def archive(self, message: dict) -> None:
        payment_id = self._extract_payment_id(message)
        factory = get_session_factory()
        async with factory() as session:
            repo = SqlAlchemyDeadLetterRepository(session)
            await repo.store(payment_id, message)
            await session.commit()
        logger.error(
            "dead letter persisted to dead_letters: payment_id=%s payload=%s",
            payment_id,
            message,
        )
