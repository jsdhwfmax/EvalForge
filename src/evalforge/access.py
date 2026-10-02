"""Shared-key access for a trusted maintainer deployment."""

from hmac import compare_digest
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from evalforge.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def _access_key(settings: Settings) -> str:
    return settings.access_key.get_secret_value() if settings.access_key is not None else ""


def validate_access_configuration(settings: Settings) -> None:
    """Refuse to start a production API without its access boundary."""
    if settings.environment.lower() in {"production", "prod"} and not _access_key(settings).strip():
        raise ValueError("EVALFORGE_ACCESS_KEY must be configured in production")


def access_key_matches(candidate: str, settings: Settings) -> bool:
    """Compare submitted credentials without exposing or retaining their value."""
    expected = _access_key(settings)
    return bool(expected.strip()) and compare_digest(
        candidate.encode("utf-8"), expected.encode("utf-8")
    )


def require_access(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> None:
    settings = get_settings()
    try:
        validate_access_configuration(settings)
    except ValueError as exc:
        # Also fail closed when an ASGI caller does not execute startup hooks.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API access is not configured",
        ) from exc

    expected = _access_key(settings)
    if not expected.strip():
        return
    if credentials is None or not access_key_matches(credentials.credentials, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid access key is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
