"""Rate Limiter — Content DNA Apex"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os


def get_org_key(request):
    return request.headers.get("X-API-Key", get_remote_address(request))


limiter = Limiter(
    key_func=get_org_key,
    storage_uri=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)

LIMIT_REGISTER  = "100/hour"
LIMIT_SCAN      = "500/hour"
LIMIT_SIGHTINGS = "1000/hour"
LIMIT_DMCA      = "100/hour"
LIMIT_AI        = "200/hour"
LIMIT_WATERMARK = "200/hour"

__all__ = [
    "limiter", "RateLimitExceeded", "_rate_limit_exceeded_handler",
    "LIMIT_REGISTER", "LIMIT_SCAN", "LIMIT_SIGHTINGS",
    "LIMIT_DMCA", "LIMIT_AI", "LIMIT_WATERMARK",
]
