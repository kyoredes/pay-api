from uuid import UUID

from faststream import Context
from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue, ExchangeType

from app.config import get_settings
from app.infrastructure.messaging.broker import create_broker
from app.infrastructure.messaging.processor import PaymentProcessor
from app.infrastructure.webhooks.client import WebhookClient

settings = get_settings()
broker = create_broker(settings)

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

processor = PaymentProcessor(WebhookClient(settings))


@broker.subscriber(
    payments_queue,
    exchange=main_exchange,
    retry=settings.consumer_max_retries,
)
async def handle_payment_new(message: dict) -> None:
    payment_id = UUID(message["payment_id"])
    await processor.process(payment_id)


@broker.subscriber(dlq, exchange=dlx_exchange)
async def handle_dead_letter(message: dict, logger=Context()) -> None:
    logger.warning("dead letter: %s", message)
