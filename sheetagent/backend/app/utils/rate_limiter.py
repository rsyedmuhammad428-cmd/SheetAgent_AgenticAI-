from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _make_limiter():
    try:
        return Limiter(
            key_func=get_remote_address,
            storage_uri=settings.redis_url,
            default_limits=[f"{settings.rate_limit_per_minute}/minute"],
        )
    except Exception as e:
        logger.warning(f"Redis rate limiter failed, using memory: {e}")
        return Limiter(
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_per_minute}/minute"],
        )


limiter = _make_limiter()


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Too many requests. Limit: {settings.rate_limit_per_minute}/minute.",
        },
    )
