from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.api.auth import verify_api_key
from src.api.deps import RequestContext, get_request_context
from src.api.schemas import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentDetailResponse,
)
from src.application.schemas import NewPayment
from src.infrastructure.database.repositories import SqlAlchemyPaymentRepository

router = APIRouter(prefix="/api/v1/payments", dependencies=[Depends(verify_api_key)])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=CreatePaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: RequestContext = Depends(get_request_context),
) -> CreatePaymentResponse:
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key is required",
        )

    new_payment = NewPayment(
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        metadata=body.metadata,
        webhook_url=str(body.webhook_url),
        idempotency_key=idempotency_key.strip(),
    )

    try:
        payment, _ = await ctx.payments.create(new_payment)
        await ctx.session.commit()
    except IntegrityError:
        await ctx.session.rollback()
        repo = SqlAlchemyPaymentRepository(ctx.session)
        existing = await repo.get_by_idempotency_key(new_payment.idempotency_key)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="idempotency conflict",
            ) from None
        payment = existing

    return CreatePaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentDetailResponse)
async def get_payment(
    payment_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> PaymentDetailResponse:
    payment = await ctx.payments.get(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return PaymentDetailResponse.from_entity(payment)
