"""Dependency guard dùng chung cho các router sinh/ghi của Runtime 1.

`verify_runtime1_token` so header `X-Runtime1-Token` với `RUNTIME1_API_TOKEN`.
Tách khỏi `verify_webhook_token` (ingest) để xoay vòng token độc lập. Front-end
proxy server-side đính token này, browser không bao giờ thấy.
"""

from fastapi import Header, HTTPException, status

from app.core.settings import get_settings


def verify_runtime1_token(
    x_runtime1_token: str | None = Header(default=None, alias="X-Runtime1-Token"),
) -> None:
    token = get_settings().runtime1_api_token
    if not token or x_runtime1_token != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Runtime 1 token",
        )
