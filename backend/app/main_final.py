from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
import uuid, time

from app.config import settings
from app.utils.logger import setup_logging, get_logger
from app.utils.rate_limiter import limiter, rate_limit_handler
from app.models.database import init_db
from app.services.memory_service import init_memory_db
from app.api.routes import upload, workspace, ws
from app.api.routes.agent   import router as agent_router
from app.api.routes.phase2  import router as phase2_router
from app.api.routes.phase3  import router as phase3_router, set_sessions_store as set_p3
from app.api.routes.phase4  import router as phase4_router
from app.api.routes.health  import router as health_router
from app.api.routes.download import router as download_router   # Phase 5
from app.api.routes.chat    import router as chat_router        # Phase 5

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", version="5.0.0", environment=settings.environment)
    await init_db()
    await init_memory_db()
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    for sub in ["incoming","processing","extracted","cleaned",
                "excels","charts","reports","logs","memory","temp"]:
        (settings.workspace_path / sub).mkdir(exist_ok=True)
    from app.services.session_store import session_store
    set_p3(session_store)
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)
    logger.info("startup_complete")
    yield
    logger.info("shutdown")


app = FastAPI(
    title="SheetAgent AI",
    version="5.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time"] = f"{ms}ms"
    if request.url.path not in ("/health", "/ready"):
        logger.info("req", method=request.method, path=request.url.path,
                    status=response.status_code, ms=ms)
    return response

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error("unhandled", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500,
        content={"error": "internal_server_error", "message": "Unexpected error"})

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    pass

# ── All routers ───────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(upload.router,    prefix="/api/upload",    tags=["upload"])
app.include_router(agent_router,     prefix="/api/agent",     tags=["agent"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])
app.include_router(ws.router,        prefix="/ws",            tags=["websocket"])
app.include_router(phase2_router,    prefix="/api/p2",        tags=["phase2"])
app.include_router(phase3_router,    prefix="/api/ocr",       tags=["ocr"])
app.include_router(phase4_router,    prefix="/api/memory",    tags=["memory"])
app.include_router(download_router,  prefix="/api/download",  tags=["download"])  # Phase 5
app.include_router(chat_router,      prefix="/api/chat",      tags=["chat"])      # Phase 5
