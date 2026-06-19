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
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()
bearer = HTTPBearer(auto_error=False)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    uploaded_file_path: Optional[str] = None


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

        # If user is authenticated and this is a new session, save it to chat_sessions table
        if current_user_id and not body.session_id:
            try:
                from app.models.database import ChatSession, AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    new_session = ChatSession(
                        id=new_session_id,
                        user_id=current_user_id,
                        title=body.message[:100] if body.message else "New Chat",
                        message_count="1",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(new_session)
                    await session.commit()
                    logger.info(f"Saved chat session {new_session_id} for user {current_user_id}")
            except Exception as e:
                logger.warning(f"Failed to save chat session: {e}")

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
                .order_by(desc(ChatSession.created_at))
            )
            sessions = result.scalars().all()
            
            return [
                ChatSessionOut(
                    id=s.id,
                    title=s.title,
                    message_count=s.message_count,
                    created_at=s.created_at.isoformat(),
                    updated_at=s.updated_at.isoformat(),
                )
                for s in sessions
            ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch chat history: {e}")
        raise HTTPException(500, f"Failed to fetch history: {str(e)}")


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
