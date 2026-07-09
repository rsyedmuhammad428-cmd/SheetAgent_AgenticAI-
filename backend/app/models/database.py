from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, JSON, Text, text, ForeignKey
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
            "pool_recycle": 300,
            "pool_timeout": 30,
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


class ChatSession(Base):
    """User chat sessions - only logged-in users can see their own"""
    __tablename__ = "chat_sessions"

    id          = Column(String, primary_key=True)
    user_id     = Column(String, nullable=False, index=True)
    title       = Column(String(255), nullable=False)
    message_count = Column(String, default="0")
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessageRecord(Base):
    """
    Individual messages within a chat session. Without this table, only
    session metadata (title/count) could be saved — the actual message
    text/role/action had nowhere to live, so loading a past chat had
    nothing to show.
    """
    __tablename__ = "chat_messages"

    id          = Column(String, primary_key=True)
    session_id  = Column(String, nullable=False, index=True)
    role        = Column(String(20), nullable=False)   # "user" | "assistant"
    text        = Column(Text, nullable=False)
    action_json = Column(JSON, nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
