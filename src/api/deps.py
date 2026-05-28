from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.payment_service import PaymentService
from src.infrastructure.database.repositories import (
    SqlAlchemyOutboxRepository,
    SqlAlchemyPaymentRepository,
)
from src.infrastructure.database.session import get_session_factory

from pydantic import BaseModel, ConfigDict


class RequestContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
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