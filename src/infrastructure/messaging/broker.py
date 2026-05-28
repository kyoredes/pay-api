from faststream.rabbit import RabbitBroker

from src.config import Settings


def create_broker(settings: Settings) -> RabbitBroker:
    return RabbitBroker(settings.rabbitmq_url)
