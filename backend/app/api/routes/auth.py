"""
auth.py — FastAPI authentication routes

Endpoints:
  POST /api/auth/register   — create account
  POST /api/auth/login      — sign in
  GET  /api/auth/me         — get current user (requires token)
  POST /api/auth/logout     — sign out (client clears token)

Uses:
  - SQLite (via SQLAlchemy + aiosqlite) — same DB your project already has
  - bcrypt for password hashing (passlib)
  - PyJWT for token creation
  - All settings from app.config (adds AUTH_SECRET, TOKEN_EXPIRE_HOURS)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)

# ── Lazy imports so nothing breaks if optional deps missing ───────────────────
def _get_pwd_context():
    try:
        from passlib.context import CryptContext
        return CryptContext(schemes=["bcrypt"], deprecated="auto")
    except ImportError:
        raise HTTPException(500, "passlib not installed: pip install passlib[bcrypt]")

def _get_jwt():
    try:
        import jwt
        return jwt
    except ImportError:
        raise HTTPException(500, "PyJWT not installed: pip install PyJWT")

# ── Config ────────────────────────────────────────────────────────────────────
def _cfg():
    from app.config import settings
    secret = settings.secret_key
    expire_minutes = int(settings.access_token_expire_minutes)
    db_url = settings.database_url
    return secret, expire_minutes, db_url

# ── DB model ──────────────────────────────────────────────────────────────────
def _get_base_and_engine():
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "users"
        id         = Column(String(36), primary_key=True)
        email      = Column(String(255), unique=True, nullable=False, index=True)
        full_name  = Column(String(255), nullable=False)
        hashed_pw  = Column(String(255), nullable=False)
        created_at = Column(DateTime(timezone=True),
                            default=lambda: datetime.now(timezone.utc))

    _, _, db_url = _cfg()
    engine  = create_async_engine(db_url, echo=False)
    session = async_sessionmaker(engine, expire_on_commit=False)
    return Base, User, engine, session

_BASE, _User, _engine, _Session = None, None, None, None

async def _init_db():
    global _BASE, _User, _engine, _Session
    if _engine is None:
        _BASE, _User, _engine, _Session = _get_base_and_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(_BASE.metadata.create_all)

async def _get_db() -> AsyncSession:
    await _init_db()
    async with _Session() as s:
        yield s

# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_token(user_id: str, email: str) -> str:
    jwt      = _get_jwt()
    secret, expire_minutes, _ = _cfg()
    payload  = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def _decode_token(token: str) -> dict:
    jwt = _get_jwt()
    secret, _, _ = _cfg()
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

async def _current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db:    AsyncSession = Depends(_get_db),
):
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = _decode_token(creds.credentials)
    user_id = payload.get("sub")
    result  = await db.execute(select(_User).where(_User.id == user_id))
    user    = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    full_name: str
    email:     str        # EmailStr needs email-validator installed
    password:  str

class LoginIn(BaseModel):
    email:    str
    password: str

class UserOut(BaseModel):
    id:         str
    email:      str
    full_name:  str
    created_at: str

class AuthOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut

# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthOut)
async def register(body: RegisterIn, db: AsyncSession = Depends(_get_db)):
    await _init_db()
    pwd_ctx = _get_pwd_context()

    if not body.email or "@" not in body.email:
        raise HTTPException(400, "Invalid email address")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not body.full_name.strip():
        raise HTTPException(400, "Full name is required")

    # Check duplicate email
    result = await db.execute(select(_User).where(_User.email == body.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(409, "An account with this email already exists")

    import uuid
    # Defensive: encode + truncate to bcrypt's 72-byte limit so no raw
    # library error ever reaches the user, regardless of bcrypt version.
    password_bytes = body.password.encode("utf-8")[:72]
    try:
        hashed_pw = pwd_ctx.hash(password_bytes)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise HTTPException(400, "Error processing password. Please try a different password.")

    user = _User(
        id        = str(uuid.uuid4()),
        email     = body.email.lower().strip(),
        full_name = body.full_name.strip(),
        hashed_pw = hashed_pw,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _make_token(user.id, user.email)
    logger.info(f"[Auth] Registered: {user.email}")
    return AuthOut(
        access_token=token,
        user=UserOut(
            id=user.id, email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat(),
        ),
    )


@router.post("/login", response_model=AuthOut)
async def login(body: LoginIn, db: AsyncSession = Depends(_get_db)):
    await _init_db()
    pwd_ctx = _get_pwd_context()

    result = await db.execute(select(_User).where(_User.email == body.email.lower()))
    user   = result.scalar_one_or_none()

    password_bytes = body.password.encode("utf-8")[:72]
    try:
        password_valid = bool(user) and pwd_ctx.verify(password_bytes, user.hashed_pw)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        password_valid = False

    if not user or not password_valid:
        raise HTTPException(401, "Invalid email or password")

    token = _make_token(user.id, user.email)
    logger.info(f"[Auth] Login: {user.email}")
    return AuthOut(
        access_token=token,
        user=UserOut(
            id=user.id, email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat(),
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(user=Depends(_current_user)):
    return UserOut(
        id=user.id, email=user.email,
        full_name=user.full_name,
        created_at=user.created_at.isoformat(),
    )


@router.post("/logout")
async def logout():
    # JWT is stateless — client discards the token
    # For production, add a token blacklist here
    return {"message": "Signed out successfully"}
