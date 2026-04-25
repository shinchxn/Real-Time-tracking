"""
Rate Limiter Configuration — Content DNA Apex v7.0
Uses slowapi for Redis-backed rate limiting per organization.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

# Custom key generator based on API Key instead of IP if available
def get_org_key(request):
    return request.headers.get("X-API-Key", get_remote_address(request))

limiter = Limiter(
    key_func=get_org_key,
    storage_uri=os.getenv("REDIS_URL", "redis://redis:6379/0")
)

# /api/v1/assets/register  → 100 req/hour
# /api/v1/scan             → 500 req/hour
# /api/v1/sightings        → 1000 req/hour
