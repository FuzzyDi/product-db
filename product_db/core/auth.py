"""API-ключевая авторизация.

X-API-Key header обязателен если API_KEYS задан в .env.
Если API_KEYS пуст — авторизация отключена (dev-режим).
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from product_db.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_keys:
        return  # dev-режим: авторизация отключена
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
