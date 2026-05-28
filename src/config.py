from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pay:pay@localhost:5432/pay"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "dev-api-key-change-me"

    payments_queue: str = "payments.new"
    payments_dlq: str = "payments.new.dlq"
    payments_exchange: str = "payments"
    payments_routing_key: str = "payments.new"

    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 50
    outbox_claim_ttl: float = 30.0

    webhook_max_attempts: int = 3
    webhook_base_delay: float = 1.0

    consumer_max_retries: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
