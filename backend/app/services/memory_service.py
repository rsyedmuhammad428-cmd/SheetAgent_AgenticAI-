"""
Memory Service — Phase 4
Provides:
  - save/load user preferences
  - record session history after each run
  - store/retrieve memory snippets
  - retrieve context for new sessions ("what did I do last time?")
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

from app.models.memory_models import Base, UserPreferences, SessionHistory, MemorySnippet
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_memory_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Preferences ───────────────────────────────────────────────────────────────

async def get_preferences() -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserPreferences).where(UserPreferences.id == "default"))
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = UserPreferences(id="default")
            db.add(prefs)
            await db.commit()
            await db.refresh(prefs)
        return _prefs_to_dict(prefs)


async def update_preferences(updates: dict) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserPreferences).where(UserPreferences.id == "default"))
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = UserPreferences(id="default")
            db.add(prefs)

        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
            else:
                extras = prefs.extras or {}
                extras[key] = value
                prefs.extras = extras

        prefs.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(prefs)
        return _prefs_to_dict(prefs)


def _prefs_to_dict(prefs: UserPreferences) -> dict:
    return {
        "date_format": prefs.date_format,
        "currency": prefs.currency,
        "currency_symbol": prefs.currency_symbol,
        "number_locale": prefs.number_locale,
        "excel_theme": prefs.excel_theme,
        "header_color": prefs.header_color,
        "font_name": prefs.font_name,
        "font_size": prefs.font_size,
        "freeze_header": prefs.freeze_header,
        "auto_filter": prefs.auto_filter,
        "chart_style": prefs.chart_style,
        "chart_colorset": prefs.chart_colorset,
        "always_generate_summary": prefs.always_generate_summary,
        "always_generate_charts": prefs.always_generate_charts,
        "auto_approve_cleaning": prefs.auto_approve_cleaning,
        "preferred_schema_handling": prefs.preferred_schema_handling,
        "extras": prefs.extras or {},
    }


# ── Session History ───────────────────────────────────────────────────────────

async def save_session(session_data: dict):
    async with AsyncSessionLocal() as db:
        record = SessionHistory(
            id=session_data["session_id"],
            file_name=session_data.get("file_name"),
            file_type=session_data.get("file_type"),
            schema_type=session_data.get("schema_type"),
            row_count=session_data.get("row_count", 0),
            col_count=session_data.get("col_count", 0),
            status=session_data.get("status", "complete"),
            output_path=session_data.get("output_path"),
            plan_steps=session_data.get("plan_steps", []),
            column_names=session_data.get("column_names", []),
            quality_score=session_data.get("quality_score"),
        )
        db.add(record)
        await db.commit()
        logger.info(f"Session saved to history: {session_data['session_id']}")


async def get_recent_sessions(limit: int = 10) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionHistory)
            .order_by(SessionHistory.created_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()
        return [_session_to_dict(s) for s in sessions]


async def get_session_by_id(session_id: str) -> dict | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionHistory).where(SessionHistory.id == session_id)
        )
        s = result.scalar_one_or_none()
        return _session_to_dict(s) if s else None


def _session_to_dict(s: SessionHistory) -> dict:
    return {
        "session_id": s.id,
        "file_name": s.file_name,
        "file_type": s.file_type,
        "schema_type": s.schema_type,
        "row_count": s.row_count,
        "col_count": s.col_count,
        "status": s.status,
        "output_path": s.output_path,
        "plan_steps": s.plan_steps or [],
        "column_names": s.column_names or [],
        "quality_score": s.quality_score,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── Memory Snippets ───────────────────────────────────────────────────────────

async def save_snippet(key: str, value: str, source: str = "inferred", confidence: float = 0.8):
    async with AsyncSessionLocal() as db:
        # Update if exists
        result = await db.execute(select(MemorySnippet).where(MemorySnippet.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(MemorySnippet(key=key, value=value, source=source, confidence=confidence))
        await db.commit()


async def get_snippets(keys: list[str] | None = None) -> list[dict]:
    async with AsyncSessionLocal() as db:
        if keys:
            result = await db.execute(
                select(MemorySnippet).where(MemorySnippet.key.in_(keys))
            )
        else:
            result = await db.execute(select(MemorySnippet))
        snippets = result.scalars().all()
        return [{"key": s.key, "value": s.value, "confidence": s.confidence} for s in snippets]


async def clear_memory():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MemorySnippet))
        await db.commit()
