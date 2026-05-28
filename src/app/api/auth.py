from fastapi import Header, HTTPException, status

from app.config import get_settings


async def verify_api_key(x_api_key: str = Header(alias="X-API-Key")) -> None:
    if x_api_key != get_settings().api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key",
        )
