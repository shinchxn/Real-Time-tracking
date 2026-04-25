"""
API Key Authentication — Content DNA Apex v6.0
SHA-256 hashed key lookup against PostgreSQL organizations table.
Returns HTTP 401 with WWW-Authenticate: ApiKey on failure.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from storage.db_client import get_org_by_api_key_hash

logger = logging.getLogger(__name__)

# ── API Key header scheme ─────────────────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key.",
    headers={"WWW-Authenticate": "ApiKey"},
)


def _hash_key(raw_key: str) -> str:
    """Compute SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_org(
    api_key: Annotated[Optional[str], Security(_api_key_header)] = None,
) -> dict:
    """
    FastAPI Security dependency.
    Inject into any protected route:
        org = Security(get_current_org)

    Returns:
        org dict: {org_id, org_name, plan, rate_limit_scan}

    Raises:
        HTTP 401 if key is missing, malformed, or not found in DB.
    """
    if not api_key:
        raise UNAUTHORIZED

    if len(api_key) < 16 or len(api_key) > 128:
        raise UNAUTHORIZED

    key_hash = _hash_key(api_key)

    try:
        org = await get_org_by_api_key_hash(key_hash)
    except Exception as e:
        logger.error("[Auth] DB lookup error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )

    if not org:
        logger.warning("[Auth] Invalid API key attempt (hash prefix: %s...)", key_hash[:8])
        raise UNAUTHORIZED

    return org


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key and its SHA-256 hash.

    Returns:
        (raw_key, key_hash) — store only the hash in the DB.
    """
    import secrets
    raw_key = f"cdna_{secrets.token_urlsafe(32)}"
    return raw_key, _hash_key(raw_key)
