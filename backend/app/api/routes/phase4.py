from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from app.services.memory_service import (
    get_preferences, update_preferences,
    get_recent_sessions, get_session_by_id,
    get_snippets, save_snippet, clear_memory
)

router = APIRouter()


# ── Preferences ───────────────────────────────────────────────────────────────

@router.get("/preferences")
async def read_preferences():
    return await get_preferences()


class PreferencesUpdate(BaseModel):
    updates: dict[str, Any]


@router.patch("/preferences")
async def patch_preferences(body: PreferencesUpdate):
    return await update_preferences(body.updates)


@router.put("/preferences/reset")
async def reset_preferences():
    from app.models.memory_models import UserPreferences
    from app.services.memory_service import AsyncSessionLocal
    from sqlalchemy import delete
    async with AsyncSessionLocal() as db:
        await db.execute(delete(UserPreferences))
        await db.commit()
    return await get_preferences()


# ── Session History ───────────────────────────────────────────────────────────

@router.get("/history")
async def list_history(limit: int = 20):
    sessions = await get_recent_sessions(limit=limit)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/history/{session_id}")
async def get_history_item(session_id: str):
    session = await get_session_by_id(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


# ── Memory Snippets ───────────────────────────────────────────────────────────

@router.get("/snippets")
async def list_snippets():
    snippets = await get_snippets()
    return {"snippets": snippets}


class SnippetBody(BaseModel):
    key: str
    value: str
    source: str = "explicit"
    confidence: float = 1.0


@router.post("/snippets")
async def create_snippet(body: SnippetBody):
    await save_snippet(body.key, body.value, body.source, body.confidence)
    return {"message": "Snippet saved", "key": body.key}


@router.delete("/snippets")
async def wipe_memory():
    await clear_memory()
    return {"message": "All memory snippets cleared"}


# ── Context summary (used by frontend memory panel) ───────────────────────────

@router.get("/context")
async def get_memory_context():
    """Returns a combined summary of preferences + history for display."""
    prefs = await get_preferences()
    recent = await get_recent_sessions(limit=5)
    snippets = await get_snippets()

    return {
        "preferences": prefs,
        "recent_sessions": recent,
        "snippets": snippets,
        "summary": {
            "total_sessions": len(recent),
            "last_schema": recent[0].get("schema_type") if recent else None,
            "last_file": recent[0].get("file_name") if recent else None,
            "last_run": recent[0].get("created_at") if recent else None,
        }
    }
