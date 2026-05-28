from faststream.rabbit import RabbitBroker, RabbitExchange, ExchangeType

from src.config import Settings


class PaymentEventPublisher:
    def __init__(self, broker: RabbitBroker, settings: Settings) -> None:
        self._broker = broker
        self._settings = settings
        self._exchange = RabbitExchange(
            settings.payments_exchange,
            type=ExchangeType.DIRECT,
            durable=True,
        )

    async def publish_new_payment(self, payload: dict) -> None:
        await self._broker.publish(
            payload,
            exchange=self._exchange,
            routing_key=self._settings.payments_routing_key,
        )
