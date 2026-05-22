import json
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)
SESSION_TTL = 86400  # 24 hours


class SessionStore:
    def __init__(self):
        self._redis = None
        self._fallback: dict = {}
        self._use_fallback = False

    async def _get_redis(self):
        if self._use_fallback:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                r = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
                await r.ping()
                self._redis = r
                logger.info("Redis session store connected")
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory store: {e}")
                self._use_fallback = True
        return self._redis

    async def set(self, session_id: str, state_dict: dict):
        r = await self._get_redis()
        if r:
            try:
                await r.setex(f"session:{session_id}", SESSION_TTL,
                              json.dumps(state_dict, default=str))
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        self._fallback[session_id] = state_dict

    async def get(self, session_id: str) -> Optional[dict]:
        r = await self._get_redis()
        if r:
            try:
                raw = await r.get(f"session:{session_id}")
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        return self._fallback.get(session_id)

    async def delete(self, session_id: str):
        r = await self._get_redis()
        if r:
            try:
                await r.delete(f"session:{session_id}")
                return
            except Exception:
                pass
        self._fallback.pop(session_id, None)

    async def exists(self, session_id: str) -> bool:
        return (await self.get(session_id)) is not None


session_store = SessionStore()
