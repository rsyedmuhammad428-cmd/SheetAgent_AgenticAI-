"""
SheetAgent AI — quota_helper.py (v3)

FIXED in this version:

  The Gemini gRPC error always includes a small retry_delay (e.g. 7 seconds)
  as a gRPC backoff hint — this is NOT the actual daily quota reset time.
  The REAL signal is quota_id: "GenerateRequestsPerDayPerProject..." which tells
  us it is a daily limit, not a per-minute rate limit.

  Error classification:
    DAILY  — quota_id contains 'PerDay'    → show midnight Pacific reset time
    MINUTE — quota_id contains 'PerMinute' → show "wait ~1 minute" message
    OTHER  — retry_delay > 120s            → use parsed retry_delay as reset time
             retry_delay ≤ 120s            → fall back to midnight Pacific

  Time format: 12-hour (e.g. 6:46 PM), shown in both UTC and PKT (Karachi).
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def is_quota_error(e: Exception) -> bool:
    """Return True if the exception is a Gemini rate-limit / quota error."""
    msg = str(e).lower()
    return any(k in msg for k in [
        "quota", "rate limit", "429", "resource exhausted",
        "limit exceeded", "too many requests", "resource_exhausted",
    ])


def get_quota_reset_message(e: Optional[Exception] = None) -> str:
    """
    Returns a professional message with:
      - Whether this is a daily or per-minute limit
      - Exact reset time in 12-hour format (e.g. 6:46 PM)
      - Time remaining
      - What the user can do
    """
    err_type, retry_secs = _classify_error(e)

    # ── Per-minute rate limit ──────────────────────────────────────────────
    if err_type == "per_minute":
        wait = max(retry_secs or 60, 15)
        if wait >= 60:
            wait_str = f"{wait} seconds"
        else:
            wait_str = f"{wait} seconds"
        return (
            "## ⏱ Rate Limit — Please Wait a Moment\n\n"
            f"You've sent too many requests in a short time. "
            f"Please wait about **{wait_str}** and try again.\n\n"
            "*This is a per-minute rate limit, not your daily quota — "
            "it resets automatically and you can retry shortly.*"
        )

    # ── Daily quota ────────────────────────────────────────────────────────
    reset_time_str, time_remaining = _calculate_daily_reset(e, err_type, retry_secs)

    return (
        "## ⏳ Daily AI Quota Reached\n\n"
        "Your Gemini API free-tier daily quota has been fully used for today. "
        "No new requests can be processed until the quota resets.\n\n"
        f"**🔄 Quota resets at:** **{reset_time_str}**\n"
        f"**⏱ Time remaining:** approximately **{time_remaining}**\n\n"
        "---\n\n"
        "**What you can do right now:**\n"
        "- ⏰ Come back after the reset time above — your request will work automatically\n"
        "- 💳 Upgrade to a paid Gemini API plan for unlimited daily usage: "
        "[Google AI Studio → Get API Key](https://aistudio.google.com/app/apikey)\n"
        "- 🔑 If you have a spare API key, update `GEMINI_API_KEY` in your `.env` "
        "file and restart the server with `docker-compose restart backend`\n\n"
        "*Your message has been saved — simply re-send it after the quota resets "
        "and SheetAgent will process it immediately.*"
    )


def _classify_error(e: Optional[Exception]) -> tuple[str, Optional[int]]:
    """
    Returns (error_type, retry_seconds).
    error_type: 'daily' | 'per_minute' | 'unknown'
    retry_seconds: parsed from error, or None
    """
    if e is None:
        return "daily", None

    err_str = str(e)

    # Extract quota_id (most reliable signal)
    quota_id = ""
    m = re.search(r'quota_id:\s*["\']?([A-Za-z0-9\-_]+)', err_str)
    if m:
        quota_id = m.group(1)

    # Extract retry_delay seconds
    retry_secs = None
    m2 = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', err_str, re.DOTALL)
    if m2:
        retry_secs = int(m2.group(1))
    # Also handle "Please retry in N.Ns" format
    if retry_secs is None:
        m3 = re.search(r'retry in ([\d.]+)s', err_str)
        if m3:
            retry_secs = int(float(m3.group(1)))
    # Also handle "Retry-After: N"
    if retry_secs is None:
        m4 = re.search(r'[Rr]etry[_\-][Aa]fter[:\s]+(\d+)', err_str)
        if m4:
            retry_secs = int(m4.group(1))

    logger.info(f"[QuotaHelper] quota_id={quota_id!r} retry_secs={retry_secs}")

    # Classify by quota_id first (most reliable)
    if re.search(r'PerDay|per_day|daily', quota_id, re.I):
        return "daily", retry_secs
    if re.search(r'PerMinute|per_minute|minute|rpm', quota_id, re.I):
        return "per_minute", retry_secs

    # No quota_id — fall back to retry_delay heuristic
    # Small retry (≤ 120s) without a daily quota_id = per-minute rate limit
    if retry_secs is not None and retry_secs <= 120:
        return "per_minute", retry_secs

    return "daily", retry_secs


def _calculate_daily_reset(
    e: Optional[Exception],
    err_type: str,
    retry_secs: Optional[int],
) -> tuple[str, str]:
    """
    Returns (reset_time_str, time_remaining_str).
    For daily limits: always use midnight US/Pacific (the real Google reset time).
    For unknown with large retry_delay: use the parsed time.
    """
    now_utc   = datetime.now(timezone.utc)
    reset_utc: Optional[datetime] = None

    # Only use retry_delay for NON-daily errors with a large value
    # Daily quota errors send small gRPC backoff (e.g. 7s) — ignore those
    if err_type == "unknown" and retry_secs is not None and retry_secs > 120:
        reset_utc = now_utc + timedelta(seconds=retry_secs)
        logger.info(f"[QuotaHelper] Using retry_delay={retry_secs}s")

    # Daily quota: always midnight Pacific Time
    if reset_utc is None:
        try:
            import pytz
            pacific   = pytz.timezone("US/Pacific")
            now_pac   = now_utc.astimezone(pacific)
            reset_pac = (now_pac + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            reset_utc = reset_pac.astimezone(timezone.utc)
            logger.info(f"[QuotaHelper] Midnight Pacific reset: {reset_utc.isoformat()}")
        except ImportError:
            reset_utc = now_utc.replace(hour=7, minute=0, second=0, microsecond=0)
            if reset_utc <= now_utc:
                reset_utc += timedelta(days=1)

    # ── Time remaining ─────────────────────────────────────────────────────
    delta      = max(reset_utc - now_utc, timedelta(0))
    total_mins = int(delta.total_seconds() // 60)
    hours_left = total_mins // 60
    mins_left  = total_mins % 60

    if total_mins == 0:
        time_remaining = "less than a minute"
    elif hours_left > 0:
        h_str = f"{hours_left} hr{'s' if hours_left != 1 else ''}"
        m_str = f" {mins_left} min" if mins_left > 0 else ""
        time_remaining = h_str + m_str
    else:
        time_remaining = f"{mins_left} min"

    # ── Format reset time: 12-hour, UTC + PKT ─────────────────────────────
    utc_str = _fmt12(reset_utc) + " UTC"

    try:
        import pytz
        karachi   = pytz.timezone("Asia/Karachi")
        reset_pkt = reset_utc.astimezone(karachi)
        pkt_str   = _fmt12(reset_pkt) + " PKT"
        reset_display = f"{utc_str}  ({pkt_str})"
    except Exception:
        reset_display = utc_str

    # Append date if reset is on a different calendar day (PKT)
    try:
        import pytz
        karachi   = pytz.timezone("Asia/Karachi")
        now_pkt   = now_utc.astimezone(karachi)
        reset_pkt = reset_utc.astimezone(karachi)
        if reset_pkt.date() != now_pkt.date():
            day_str = reset_pkt.strftime("%A, %d %B")
            reset_display += f"  —  {day_str}"
    except Exception:
        pass

    return reset_display, time_remaining


def _fmt12(dt: datetime) -> str:
    """Format datetime as 12-hour time without leading zero: '6:46 PM'."""
    try:
        return dt.strftime("%-I:%M %p")
    except ValueError:
        formatted = dt.strftime("%I:%M %p")
        return formatted.lstrip("0") or formatted
