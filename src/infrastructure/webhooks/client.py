import asyncio

import httpx
from src.infrastructure.webhooks.schemas import WebhookPayload
from src.config import Settings




class WebhookClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def deliver(self, url: str, payload: WebhookPayload) -> None:
        body = {
            "payment_id": payload.payment_id,
            "status": payload.status,
            "amount": payload.amount,
            "currency": payload.currency,
            "description": payload.description,
            "metadata": payload.metadata,
            "processed_at": payload.processed_at,
        }
        delay = self._settings.webhook_base_delay
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, self._settings.webhook_max_attempts + 1):
                try:
                    response = await client.post(url, json=body)
                    if 200 <= response.status_code < 300:
                        return
                    if 400 <= response.status_code < 500:
                        raise httpx.HTTPStatusError(
                            f"client error {response.status_code}, won't retry",
                            request=response.request,
                            response=response,
                        )
                    last_error = httpx.HTTPStatusError(
                        f"server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                except httpx.HTTPStatusError:
                    raise
                except httpx.HTTPError as exc:
                    last_error = exc

                if attempt < self._settings.webhook_max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2

        if last_error:
            raise last_error
