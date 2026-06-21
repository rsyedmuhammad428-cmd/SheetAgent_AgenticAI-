"""
Phase 6 — Chat Route with Auth & History

Fix for duplicate responses:
- Route calls handle_message exactly ONCE
- No background tasks that also call handle_message
- Returns single ChatResponse

New secure endpoints:
- POST /api/chat/          — Send message (requires auth, links to user_id)
- GET  /api/chat/history  — Fetch user's private chat sessions (requires auth)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime, timezone
import logging
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def _iso(dt: Optional[datetime]) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _get_user_id_from_creds(creds: HTTPAuthorizationCredentials) -> Optional[str]:
    from app.api.routes.auth import _decode_token

    payload = _decode_token(creds.credentials)
    return payload.get("sub")


async def _persist_chat_history(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_text: str,
    user_action: Optional[dict[str, Any]] = None,
    assistant_action: Optional[dict[str, Any]] = None,
) -> None:
    from app.models.database import ChatMessageRecord, ChatSession, AsyncSessionLocal

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        chat_session = session_result.scalar_one_or_none()

        if chat_session is None:
            chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title=user_message[:100] if user_message else "New Chat",
                message_count="0",
                created_at=now,
                updated_at=now,
            )
            db.add(chat_session)
        elif chat_session.user_id != user_id:
            logger.warning(
                "Skipping history persist for session %s: owner mismatch", session_id
            )
            return
        elif (not chat_session.title or chat_session.title == "New Chat") and user_message:
            chat_session.title = user_message[:100]

        db.add(
            ChatMessageRecord(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="user",
                text=user_message,
                action_json=user_action or {},
                created_at=now,
            )
        )
        db.add(
            ChatMessageRecord(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                text=assistant_text,
                action_json=assistant_action or {},
                created_at=now,
            )
        )

        await db.flush()

        count_result = await db.execute(
            select(func.count())
            .select_from(ChatMessageRecord)
            .where(ChatMessageRecord.session_id == session_id)
        )
        total_messages = count_result.scalar_one()
        chat_session.message_count = str(total_messages)
        chat_session.updated_at = now
        await db.commit()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    uploaded_file_path: Optional[str] = None
    attached_file_name: Optional[str] = None


class ChatResponse(BaseModel):
    text: str
    intent: str = "question"
    action: dict = {}
    session_id: Optional[str] = None


class ChatSessionOut(BaseModel):
    id: str
    title: str
    message_count: str
    created_at: str
    updated_at: str


class StoredMessageOut(BaseModel):
    id: str
    role: str
    text: str
    action: dict[str, Any] = {}
    created_at: str


# ── Auth dependencies ─────────────────────────────────────────────────────────


@router.post("/", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """
    Send a chat message. Links to current user's session via user_id (if authenticated).
    Falls back to anonymous if not authenticated.
    """
    current_user_id = None
    
    # Try to authenticate if token provided
    if creds:
        try:
            from app.api.routes.auth import _decode_token
            payload = _decode_token(creds.credentials)
            current_user_id = payload.get("sub")
        except Exception as e:
            logger.debug(f"Auth decode failed: {e}")

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

    new_session_id = body.session_id or f"chat-{uuid.uuid4()}"
    
    try:
        from app.agents.chat_agent import handle_message
        response = await handle_message(
            message=body.message,
            state=state,
            session_id=new_session_id,
            uploaded_file_path=body.uploaded_file_path,
        )

        intent_str = response.intent.value if hasattr(response.intent, "value") else str(response.intent)

        if current_user_id:
            try:
                await _persist_chat_history(
                    user_id=current_user_id,
                    session_id=new_session_id,
                    user_message=body.message,
                    assistant_text=response.text,
                    user_action={
                        "attached_file_name": body.attached_file_name
                    } if body.attached_file_name else {},
                    assistant_action=response.action,
                )
            except Exception as e:
                logger.warning(f"Failed to persist chat history: {e}")

        return ChatResponse(
            text=response.text,
            intent=intent_str,
            action=response.action or {},
            session_id=new_session_id,
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
            session_id=new_session_id,
        )


@router.get("/history", response_model=list[ChatSessionOut])
async def get_chat_history(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(lambda: None),
):
    """
    Get current user's private chat history.
    Only returns sessions where user_id = current_user.id, sorted by newest first.
    Requires authentication.
    """
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    
    # Decode token and get user
    try:
        from app.api.routes.auth import _decode_token, _get_db
        from sqlalchemy import select
        
        payload = _decode_token(creds.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        
        # Get database session
        async for session in _get_db():
            from app.models.database import ChatSession
            
            # Query sessions for this user
            result = await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(desc(ChatSession.updated_at), desc(ChatSession.created_at))
            )
            sessions = result.scalars().all()
            
            return [
                ChatSessionOut(
                    id=s.id,
                    title=s.title,
                    message_count=s.message_count,
                    created_at=_iso(s.created_at),
                    updated_at=_iso(s.updated_at),
                )
                for s in sessions
            ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch chat history: {e}")
        raise HTTPException(500, f"Failed to fetch history: {str(e)}")


@router.get("/history/{session_id}", response_model=list[StoredMessageOut])
async def get_chat_messages(
    session_id: str,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Get all stored messages for a chat session — owner only."""
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = _get_user_id_from_creds(creds)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    try:
        from app.models.database import ChatMessageRecord, ChatSession, AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            session_result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                raise HTTPException(404, "Chat session not found")
            if session.user_id != user_id:
                raise HTTPException(403, "Not authorized to view this session")

            messages_result = await db.execute(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.session_id == session_id)
                .order_by(asc(ChatMessageRecord.created_at), asc(ChatMessageRecord.id))
            )
            messages = messages_result.scalars().all()

            return [
                StoredMessageOut(
                    id=message.id,
                    role=message.role,
                    text=message.text,
                    action=message.action_json or {},
                    created_at=_iso(message.created_at),
                )
                for message in messages
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch chat messages: {e}")
        raise HTTPException(500, f"Failed to fetch chat messages: {str(e)}")


@router.delete("/history/{session_id}")
async def delete_chat_session(
    session_id: str,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Delete a chat session and all its messages — owner only."""
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = _get_user_id_from_creds(creds)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    try:
        from app.models.database import ChatSession, ChatMessageRecord, AsyncSessionLocal
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as db:
            sess_result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            session = sess_result.scalar_one_or_none()
            if not session:
                raise HTTPException(404, "Chat session not found")
            if session.user_id != user_id:
                raise HTTPException(403, "Not authorized to delete this session")

            await db.execute(
                sa_delete(ChatMessageRecord).where(
                    ChatMessageRecord.session_id == session_id
                )
            )
            await db.execute(
                sa_delete(ChatSession).where(ChatSession.id == session_id)
            )
            await db.commit()
            logger.info(f"[ChatHistory] Deleted session {session_id}")
            return {"message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(500, f"Failed to delete session: {str(e)}")


@router.get("/health")
async def health():
    return {"status": "ok", "route": "chat", "phase": 6}
