# Pay API

Асинхронный сервис обработки платежей: REST API, outbox, RabbitMQ, webhook-уведомления.

## Стек

- FastAPI, Pydantic v2
- SQLAlchemy 2.0 (async), PostgreSQL, Alembic
- RabbitMQ, FastStream
- Docker Compose

## Запуск

```bash
docker compose up --build
```

Сервисы:

| Сервис   | URL                          |
|----------|------------------------------|
| API      | http://localhost:8000        |
| Swagger  | http://localhost:8000/docs   |
| RabbitMQ | http://localhost:15672       |

API-ключ по умолчанию: `dev-api-key-change-me` (заголовок `X-API-Key`).

## Примеры

Создание платежа:

```bash
curl -s -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Idempotency-Key: order-1001" \
  -d '{
    "amount": "1500.00",
    "currency": "RUB",
    "description": "Подписка",
    "metadata": {"order_id": "1001"},
    "webhook_url": "https://webhook.site/your-uuid"
  }'
```

Ответ `202`:

```json
{
  "payment_id": "...",
  "status": "pending",
  "created_at": "..."
}
```

Получение платежа:

```bash
curl -s http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: dev-api-key-change-me"
```

Повторный запрос с тем же `Idempotency-Key` вернёт тот же платёж без дубля в БД.

## Архитектура

```
src/app/
  domain/          сущности и enum
  application/     use-case и порты
  infrastructure/  БД, outbox relay, RabbitMQ, webhooks
  api/             HTTP-слой
```

Поток:

1. `POST /payments` — запись в `payments` и `outbox` в одной транзакции.
2. Outbox relay публикует событие в очередь `payments.new`.
3. Consumer эмулирует шлюз (2–5 с, ~90% успех), обновляет статус, шлёт webhook с retry.
4. После 3 неудачных обработок сообщение уходит в DLQ `payments.new.dlq`.

## Локальная разработка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

docker compose up postgres rabbitmq -d
alembic upgrade head
uvicorn src.main:app --reload
python -m src.consumer_main
```

Переменные окружения — см. `.env.example`.
