from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.payment_service import PaymentService
from app.infrastructure.database.repositories import (
    SqlAlchemyOutboxRepository,
    SqlAlchemyPaymentRepository,
)
from app.infrastructure.database.session import get_session_factory


@dataclass(slots=True)
class RequestContext:
    session: AsyncSession
    payments: PaymentService


async def get_request_context() -> AsyncGenerator[RequestContext, None]:
    factory = get_session_factory()
    async with factory() as session:
        payments_repo = SqlAlchemyPaymentRepository(session)
        outbox_repo = SqlAlchemyOutboxRepository(session)
        yield RequestContext(
            session=session,
            payments=PaymentService(payments_repo, outbox_repo),
        )
