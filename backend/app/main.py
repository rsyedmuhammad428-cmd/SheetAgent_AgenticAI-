"""
main.py — CORS Fix
The backend CORS settings are a secondary defence.
Primary fix is nginx routing (same-origin).
But we also set CORS correctly here for direct API access.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uuid
import time
import logging

from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models.database import init_db
    await init_db()

    try:
        from app.services.memory_service import init_memory_db
        await init_memory_db()
    except Exception as e:
        logger.warning(f"Memory DB skipped: {e}")

    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    for sub in ["incoming", "processing", "extracted", "cleaned",
                "excels", "charts", "reports", "logs", "memory", "temp"]:
        (settings.workspace_path / sub).mkdir(exist_ok=True)

    try:
        from app.services.session_store import session_store
        from app.api.routes.phase3 import set_sessions_store as set_p3
        set_p3(session_store)
    except Exception as e:
        logger.warning(f"Phase3 wiring skipped: {e}")

    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
        except Exception:
            pass

    logger.info(f"SheetAgent AI v5.0.0 started | env={settings.environment}")
    yield
    logger.info("SheetAgent AI shutdown")


app = FastAPI(
    title="SheetAgent AI",
    version="5.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins — nginx is the primary CORS handler.
# This allows direct API calls during development without nginx.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time", "Content-Disposition"],
)

# ── Rate limiting (optional) ──────────────────────────────────────────────────
try:
    from slowapi.errors import RateLimitExceeded
    from app.utils.rate_limiter import limiter, rate_limit_handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
except Exception as e:
    logger.warning(f"Rate limiter skipped: {e}")

# ── Request logging ───────────────────────────────────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time"] = f"{ms}ms"
    if request.url.path not in ("/health", "/ready"):
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)")
    return response

# ── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled: {request.url.path} — {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": str(exc)},
    )

# ── Prometheus (optional) ─────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception:
    pass

# ── Core routers ──────────────────────────────────────────────────────────────
from app.api.routes import upload, workspace, ws
from app.api.routes.agent    import router as agent_router
from app.api.routes.auth     import router as auth_router
from app.api.routes.health   import router as health_router
from app.api.routes.download import router as download_router
from app.api.routes.chat     import router as chat_router

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(upload.router,    prefix="/api/upload",   tags=["upload"])
app.include_router(agent_router,     prefix="/api/agent",    tags=["agent"])
app.include_router(workspace.router, prefix="/api/workspace",tags=["workspace"])
app.include_router(ws.router,        prefix="/ws",           tags=["websocket"])
app.include_router(download_router,  prefix="/api/download", tags=["download"])
app.include_router(chat_router,      prefix="/api/chat",     tags=["chat"])

# ── Phase 2-4 routers (optional) ─────────────────────────────────────────────
for name, module_path, prefix, tag in [
    ("phase2", "app.api.routes.phase2", "/api/p2",     "phase2"),
    ("phase3", "app.api.routes.phase3", "/api/ocr",    "ocr"),
    ("phase4", "app.api.routes.phase4", "/api/memory", "memory"),
]:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        app.include_router(mod.router, prefix=prefix, tags=[tag])
    except Exception as e:
        logger.warning(f"{name} routes skipped: {e}")
