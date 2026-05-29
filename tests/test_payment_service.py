import logging
import os
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest

from src.application.payment_service import (
    IdempotencyMismatchError,
    PaymentService,
)
from src.api.schemas import CreatePaymentResponse
from src.application.repo import PaymentOutboxRepository, PaymentRepository
from src.domain.entities import Payment
from src.domain.enums import Currency, PaymentStatus
from src.application.schemas import NewPayment

logger = logging.getLogger(__name__)


def api_response(payment: Payment, created: bool) -> tuple[int, str]:
    status_code = 202 if created else 200
    body = CreatePaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )
    return status_code, body.model_dump_json()


class FakePaymentRepository(PaymentRepository):
    def __init__(self) -> None:
        self.saved: list[Payment] = []

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        return next((p for p in self.saved if p.id == payment_id), None)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        return next((p for p in self.saved if p.idempotency_key == key), None)

    async def save(self, payment: Payment) -> Payment:
        self.saved.append(payment)
        return payment

    async def update_status(self, payment_id, status, processed_at):
        raise NotImplementedError


class FakeOutboxRepository(PaymentOutboxRepository):
    def __init__(self) -> None:
        self.enqueued: list[tuple[UUID, dict]] = []

    async def enqueue(self, payment_id: UUID, payload: dict) -> None:
        self.enqueued.append((payment_id, payload))

    async def claim_pending(self, limit, claim_ttl_seconds):
        raise NotImplementedError

    async def mark_processed(self, outbox_id):
        raise NotImplementedError

    async def release_claim(self, outbox_id):
        raise NotImplementedError


def make_new_payment(**overrides) -> NewPayment:
    data = {
        "amount": Decimal("100.00"),
        "currency": Currency.RUB,
        "description": "test",
        "metadata": {"order_id": "1"},
        "webhook_url": "https://example.com/hook",
        "idempotency_key": "key-1",
    }
    data.update(overrides)
    return NewPayment(**data)


@pytest.mark.asyncio
async def test_create_persists_payment_and_enqueues_outbox():
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    payment, created = await service.create(make_new_payment())

    status_code, body = api_response(payment, created)
    logger.info(
        "details: created=%s, saved=%d, enqueued=%d",
        created,
        len(payments.saved),
        len(outbox.enqueued),
    )

    assert created is True
    assert payment.status is PaymentStatus.PENDING
    assert len(payments.saved) == 1
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0][0] == payment.id

    logger.info("test_create_persists_payment_and_enqueues_outbox PASSED")


@pytest.mark.asyncio
async def test_create_is_idempotent_for_same_key_and_params():
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    first, first_created = await service.create(make_new_payment())
    second, second_created = await service.create(make_new_payment())

    first_status, first_body = api_response(first, first_created)
    second_status, second_body = api_response(second, second_created)

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert len(payments.saved) == 1
    assert len(outbox.enqueued) == 1

    logger.info("test_create_is_idempotent_for_same_key_and_params PASSED")


@pytest.mark.asyncio
async def test_create_rejects_same_key_with_different_params():
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    await service.create(make_new_payment())

    with pytest.raises(IdempotencyMismatchError) as exc_info:
        await service.create(make_new_payment(amount=Decimal("999.00")))

    logger.info('api returned: HTTP 409 {"detail": "%s"}', exc_info.value)
    logger.info("test_create_rejects_same_key_with_different_params PASSED")


# --- Integration tests: real HTTP request to a running API ---

API_BASE_URL = os.getenv("PAY_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key-change-me")


def _server_is_up(base_url: str) -> bool:
    try:
        resp = httpx.get(f"{base_url}/docs", timeout=2.0)
    except httpx.HTTPError:
        return False
    return resp.status_code < 500


@pytest.fixture(scope="module")
def api_base_url() -> str:
    if not _server_is_up(API_BASE_URL):
        logger.warning(
            "API server is not reachable at %s - integration tests skipped. "
            "Start the server: `docker compose up -d` or `uvicorn src.main:app`.",
            API_BASE_URL,
        )
        pytest.skip(f"API server is not running at {API_BASE_URL}")
    logger.info("API server is reachable at %s - running integration tests", API_BASE_URL)
    return API_BASE_URL


@pytest.mark.asyncio
async def test_api_create_payment_and_idempotent_replay(api_base_url: str):
    idempotency_key = f"itest-{uuid4()}"
    body = {
        "amount": "1500.00",
        "currency": "RUB",
        "description": "Subscription",
        "metadata": {"order_id": "1001"},
        "webhook_url": "https://example.com/hook",
    }
    headers = {"X-API-Key": API_KEY, "Idempotency-Key": idempotency_key}

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post("/api/v1/payments", json=body, headers=headers)
        logger.info("api returned: HTTP %d %s", resp.status_code, resp.text)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        assert UUID(data["payment_id"])
        payment_id = data["payment_id"]

        replay = await client.post("/api/v1/payments", json=body, headers=headers)
        logger.info("api returned (replay): HTTP %d %s", replay.status_code, replay.text)
        assert replay.status_code == 200
        assert replay.json()["payment_id"] == payment_id

    logger.info("test_api_create_payment_and_idempotent_replay PASSED")


@pytest.mark.asyncio
async def test_api_get_payment(api_base_url: str):
    body = {
        "amount": "250.50",
        "currency": "USD",
        "description": "test get",
        "metadata": {},
        "webhook_url": "https://example.com/hook",
    }
    headers = {"X-API-Key": API_KEY, "Idempotency-Key": f"itest-{uuid4()}"}

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        created = await client.post("/api/v1/payments", json=body, headers=headers)
        logger.info("api returned (create): HTTP %d %s", created.status_code, created.text)
        assert created.status_code == 202
        payment_id = created.json()["payment_id"]

        resp = await client.get(
            f"/api/v1/payments/{payment_id}", headers={"X-API-Key": API_KEY}
        )
        logger.info("api returned (GET): HTTP %d %s", resp.status_code, resp.text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["payment_id"] == payment_id
        assert data["amount"] == "250.50"
        assert data["currency"] == "USD"

    logger.info("test_api_get_payment PASSED")


@pytest.mark.asyncio
async def test_api_rejects_invalid_api_key(api_base_url: str):
    body = {
        "amount": "10.00",
        "currency": "RUB",
        "description": "",
        "metadata": {},
        "webhook_url": "https://example.com/hook",
    }
    headers = {"X-API-Key": "wrong-key", "Idempotency-Key": f"itest-{uuid4()}"}

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post("/api/v1/payments", json=body, headers=headers)
        logger.info("api returned (bad key): HTTP %d %s", resp.status_code, resp.text)
        assert resp.status_code == 401

    logger.info("test_api_rejects_invalid_api_key PASSED")
