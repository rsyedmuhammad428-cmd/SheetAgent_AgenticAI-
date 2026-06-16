from fastapi import APIRouter
from app.config import settings
import time

router = APIRouter()
START_TIME = time.time()


@router.get("/health")
async def health():
    return {"status": "ok", "version": "5.0.0", "environment": settings.environment}


@router.get("/ready")
async def readiness():
    checks: dict = {}
    overall = "ok"

    # DB check
    try:
        from app.models.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        overall = "degraded"

    # Redis check (optional)
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"fallback active: {str(e)[:50]}"

    # Workspace
    checks["workspace"] = "ok" if settings.workspace_path.exists() else "missing"
    checks["uptime_seconds"] = round(time.time() - START_TIME)

    return {"status": overall, "checks": checks}
