"""
Phase 6 — Chat Route

Fix for duplicate responses:
- Route calls handle_message exactly ONCE
- No background tasks that also call handle_message
- Returns single ChatResponse
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    uploaded_file_path: Optional[str] = None


class ChatResponse(BaseModel):
    text: str
    intent: str = "question"
    action: dict = {}
    session_id: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """
    Single endpoint. Calls handle_message ONCE.
    Never triggers background tasks that also process.
    """
    state = None
    if body.session_id:
        try:
            from app.services.session_store import session_store
            from app.models.state import AgentState
            data = await session_store.get(body.session_id)
            if data:
                state = AgentState(**data)
        except Exception as e:
            logger.warning(f"Session load: {e}")

    try:
        from app.agents.chat_agent import handle_message
        response = await handle_message(
            message=body.message,
            state=state,
            session_id=body.session_id or "no-session",
            uploaded_file_path=body.uploaded_file_path,
        )

        intent_str = response.intent.value if hasattr(response.intent, "value") else str(response.intent)

        return ChatResponse(
            text=response.text,
            intent=intent_str,
            action=response.action or {},
            session_id=body.session_id,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return ChatResponse(
            text=(
                f"Error: {str(e)}\n\n"
                "Please make sure **GEMINI_API_KEY** is set in your `.env` file.\n"
                "Then run: `docker-compose restart backend`"
            ),
            intent="error",
            action={},
            session_id=body.session_id,
        )


@router.get("/health")
async def health():
    return {"status": "ok", "route": "chat", "phase": 6}
