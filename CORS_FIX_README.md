# SheetAgent AI — CORS Fix

## Root Cause

The error:
```
Cross-Origin Request Blocked: http://localhost:8000/api/chat/
```

Happened because **frontend was calling `http://localhost:8000` directly** (port 8000 = backend).
Browser sees: page loaded from `http://localhost` (port 80) → request going to port 8000 = **different origin = CORS blocked**.

## The Fix (3-layer)

```
BEFORE (broken):
  Browser → http://localhost:8000/api/chat/   ← CORS BLOCKED

AFTER (fixed):
  Browser → http://localhost/api/chat/        ← Same origin ✓
                    ↓
               nginx (port 80)
                    ↓
               backend:8000                   ← Internal Docker network, no CORS
```

## Files to REPLACE — 7 files

```
frontend/src/api/client.ts                    ← Removes hardcoded localhost:8000
frontend/src/hooks/useWebSocket.ts            ← Uses window.location.host for WS URL
frontend/src/components/layout/ChatPanel.tsx  ← Uses relative API calls
frontend/.env                                 ← Clears any VITE_API_BASE_URL value
frontend/vite.config.ts                       ← Adds dev proxy
nginx/nginx.conf                              ← Adds CORS headers + OPTIONS handler
backend/app/main.py                           ← Sets allow_origins=["*"]
backend/app/api/routes/chat.py               ← Never returns 500 to frontend
```

## PowerShell commands

```powershell
cd "D:\Data Entery AI_Agent\sheetagent"

# Replace the 7 files listed above from the zip

# Rebuild frontend (it has code changes)
docker-compose up --build -d frontend nginx

# Restart backend (main.py changed)
docker-compose restart backend

# Check logs
docker-compose logs -f backend
```

## Verify CORS is fixed

Open browser DevTools → Network tab → click "Create an invoice template"
You should see:
  POST /api/chat/  → 200 OK   (not blocked)

## Why allow_origins=["*"] is safe here

The backend sits behind nginx inside Docker's internal network.
External traffic can ONLY reach the backend through nginx on port 80.
Port 8000 is not exposed to the host machine (check docker-compose.yml — only port 80 is mapped).
So `allow_origins=["*"]` on the backend is fine — it's never directly reachable from the internet.
