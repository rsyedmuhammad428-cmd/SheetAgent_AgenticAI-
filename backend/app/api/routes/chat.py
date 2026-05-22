from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.agents.chat_agent import handle_message
from app.services.session_store import session_store
from app.models.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    text: str
    intent: str
    action: dict = {}
    session_id: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def chat(body: ChatRequest):
    state = None
    if body.session_id:
        data = await session_store.get(body.session_id)
        if data:
            state = AgentState(**data)

    response = await handle_message(
        message=body.message,
        state=state,
        session_id=body.session_id or "no-session",
    )

    logger.info("chat_message", intent=response.intent, session_id=body.session_id)

    return ChatResponse(
        text=response.text,
        intent=response.intent.value,
        action=response.action,
        session_id=body.session_id,
    )
