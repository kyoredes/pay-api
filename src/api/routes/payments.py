from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from src.api.auth import verify_api_key
from src.api.deps import RequestContext, get_request_context
from src.api.schemas import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentDetailResponse,
)
from src.application.payment_service import IdempotencyMismatchError, ensure_idempotent_match
from src.application.schemas import NewPayment
from src.infrastructure.database.repositories import SqlAlchemyPaymentRepository

router = APIRouter(prefix="/api/v1/payments", dependencies=[Depends(verify_api_key)])


@router.post(
    "",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_200_OK: {
            "description": "Existing payment returned for idempotent replay",
            "model": CreatePaymentResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Idempotency-Key reused with different request parameters",
        },
    },
)
async def create_payment(
    body: CreatePaymentRequest,
    response: Response,
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

    created = True
    try:
        payment, created = await ctx.payments.create(new_payment)
        await ctx.session.commit()
    except IdempotencyMismatchError as exc:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        await ctx.session.rollback()
        repo = SqlAlchemyPaymentRepository(ctx.session)
        existing = await repo.get_by_idempotency_key(new_payment.idempotency_key)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="idempotency conflict",
            ) from None
        try:
            ensure_idempotent_match(existing, new_payment)
        except IdempotencyMismatchError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        payment = existing
        created = False

    response.status_code = (
        status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
    )
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
