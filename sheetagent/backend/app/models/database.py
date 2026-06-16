from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, JSON, text
from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def _make_engine():
    url = settings.database_url
    kwargs: dict = {"echo": False}

    if "postgresql" in url:
        kwargs.update({
            "pool_size": 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        })
    else:
        # SQLite
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_async_engine(url, **kwargs)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"

    id          = Column(String, primary_key=True)
    file_name   = Column(String, nullable=True)
    file_type   = Column(String, nullable=True)
    schema_type = Column(String, nullable=True)
    status      = Column(String, default="pending")
    state_json  = Column(JSON, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
