from fastapi import WebSocket
from collections import defaultdict
from typing import DefaultDict
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: DefaultDict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id].append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        try:
            self.active[session_id].remove(ws)
        except (ValueError, KeyError):
            pass

    async def broadcast(self, session_id: str, message: dict):
        dead = []
        for ws in list(self.active.get(session_id, [])):
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send_log(self, session_id: str, agent: str, message: str, level: str = "info"):
        from datetime import datetime, timezone
        await self.broadcast(session_id, {
            "type": "log",
            "session_id": session_id,
            "data": {
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "agent": agent,
                "message": message,
                "level": level,
            }
        })

    async def send_status(self, session_id: str, status: str):
        await self.broadcast(session_id, {
            "type": "status",
            "session_id": session_id,
            "data": {"status": status},
        })

    async def send_suggestion(self, session_id: str, suggestions: list):
        await self.broadcast(session_id, {
            "type": "suggestion",
            "session_id": session_id,
            "data": {"suggestions": suggestions},
        })


ws_manager = ConnectionManager()
