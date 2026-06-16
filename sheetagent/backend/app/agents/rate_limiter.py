"""
SheetAgent AI — rate_limiter.py

Automatic retry with backoff for Gemini RPM (requests-per-minute) errors.

FREE TIER LIMITS (gemini-1.5-flash / gemini-2.5-flash):
  - 5–15 RPM (requests per minute)
  - 1500 RPD (requests per day)

When an RPM error hits, we automatically wait `retry_delay` seconds
(from the error) and retry — the user never sees an error for a transient
rate limit. Only daily quota exhaustion is surfaced to the user.

Usage:
    from app.agents.rate_limiter import call_with_retry

    result = await call_with_retry(gemini_service.analyze_json, prompt)
"""
import asyncio
import logging
import re
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Max times to retry a single RPM-hit before giving up
MAX_RPM_RETRIES = 3


def _is_rpm_error(e: Exception) -> bool:
    """Return True if this is a per-minute rate limit (not daily quota)."""
    err = str(e)
    # quota_id contains PerMinute → RPM error
    if re.search(r'PerMinute|per_minute|per-minute|rpm', err, re.I):
        return True
    # Small retry_delay (≤ 120s) without PerDay → likely RPM
    has_per_day = bool(re.search(r'PerDay|per_day|per-day', err, re.I))
    if has_per_day:
        return False
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', err, re.DOTALL)
    if not m:
        m = re.search(r'retry in ([\d.]+)s', err)
    if m:
        secs = float(m.group(1))
        return secs <= 120
    return False


def _is_daily_error(e: Exception) -> bool:
    """Return True if this is a daily quota exhaustion."""
    from app.agents.quota_helper import is_quota_error
    if not is_quota_error(e):
        return False
    err = str(e)
    if re.search(r'PerDay|per_day|per-day', err, re.I):
        return True
    # Large retry_delay = daily
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', err, re.DOTALL)
    if m and int(m.group(1)) > 120:
        return True
    return False


def _get_retry_delay(e: Exception) -> float:
    """Extract retry_delay seconds from error. Default 30s if not found."""
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(e), re.DOTALL)
    if m:
        return float(m.group(1))
    m2 = re.search(r'retry in ([\d.]+)s', str(e))
    if m2:
        return float(m2.group(1))
    return 30.0


async def call_with_retry(
    fn: Callable[..., Coroutine],
    *args,
    **kwargs,
) -> Any:
    """
    Call an async Gemini function. If it hits an RPM error, wait the
    prescribed retry_delay and try again (up to MAX_RPM_RETRIES times).
    Daily quota errors are re-raised immediately for chat_agent to handle.
    """
    last_exc = None
    for attempt in range(1, MAX_RPM_RETRIES + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if _is_daily_error(e):
                # Daily quota — surface immediately, no retry
                raise

            if _is_rpm_error(e):
                wait = _get_retry_delay(e) + 2  # +2s buffer
                if attempt <= MAX_RPM_RETRIES:
                    logger.warning(
                        f"[RateLimiter] RPM hit (attempt {attempt}/{MAX_RPM_RETRIES}) "
                        f"— waiting {wait:.0f}s then retrying..."
                    )
                    await asyncio.sleep(wait)
                    last_exc = e
                    continue

            # Non-quota error — raise as-is
            raise

    # All retries exhausted — raise last RPM error
    raise last_exc
