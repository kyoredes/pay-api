import httpx

from src.infrastructure.webhooks.schemas import WebhookPayload


class WebhookClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

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

        response = await self._client.post(url, json=body)

        if 200 <= response.status_code < 300:
            return

        raise httpx.HTTPStatusError(
            f"server error {response.status_code}",
            request=response.request,
            response=response,
        )

    async def close(self) -> None:
        await self._client.aclose()
