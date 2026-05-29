import logging
from uuid import UUID

from faststream.exceptions import RejectMessage
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from src.config import get_settings
from src.infrastructure.messaging.broker import create_broker
from src.infrastructure.messaging.dead_letter import DeadLetterArchiver
from src.infrastructure.messaging.exceptions import (
    PaymentNotFoundError,
    WebhookDeliveryError,
)
from src.infrastructure.messaging.processor import PaymentProcessor
from src.infrastructure.webhooks.client import WebhookClient

logger = logging.getLogger(__name__)

settings = get_settings()
broker = create_broker(settings)

webhook_client = WebhookClient()

main_exchange = RabbitExchange(
    settings.payments_exchange,
    type=ExchangeType.DIRECT,
    durable=True,
)

dlx_exchange = RabbitExchange(
    f"{settings.payments_exchange}.dlx",
    type=ExchangeType.DIRECT,
    durable=True,
)

payments_queue = RabbitQueue(
    settings.payments_queue,
    durable=True,
    routing_key=settings.payments_routing_key,
    arguments={
        "x-dead-letter-exchange": dlx_exchange.name,
        "x-dead-letter-routing-key": settings.payments_dlq,
    },
)

dlq = RabbitQueue(
    settings.payments_dlq,
    durable=True,
    routing_key=settings.payments_dlq,
)

processor = PaymentProcessor(webhook_client, settings)
dead_letter_archiver = DeadLetterArchiver()


@broker.subscriber(
    payments_queue,
    exchange=main_exchange,
    retry=settings.consumer_max_retries,
)
async def handle_payment_new(message: dict) -> None:
    try:
        payment_id = UUID(message["payment_id"])
    except (KeyError, ValueError) as exc:
        logger.error("invalid payment message, rejecting to DLQ: %r", message)
        raise RejectMessage() from exc

    try:
        await processor.process(payment_id)
    except PaymentNotFoundError as exc:
        logger.error("payment %s not found, rejecting to DLQ", exc.payment_id)
        raise RejectMessage() from exc
    except WebhookDeliveryError as exc:
        logger.error(
            "webhook delivery for payment %s failed after retries, rejecting to DLQ",
            exc.payment_id,
        )
        raise RejectMessage() from exc


@broker.subscriber(dlq, exchange=dlx_exchange, retry=True)
async def handle_dead_letter(message: dict) -> None:
    await dead_letter_archiver.archive(message)
