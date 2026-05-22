# SheetAgent AI — Phase 5 (Production Hardening + Full Chat + Download)

## What's new in Phase 5

### Backend
| File | What it does |
|------|-------------|
| `requirements.txt` | All deps consolidated + asyncpg, redis, alembic, slowapi, structlog |
| `config.py` | Production settings, PostgreSQL URL fix, env validation |
| `utils/logger.py` | Structured JSON logging → stdout + rotating file |
| `utils/rate_limiter.py` | slowapi rate limiting with Redis backend |
| `utils/retry.py` | tenacity retry for Gemini + OCR calls |
| `services/session_store.py` | Redis session store (falls back to memory) |
| `services/gemini_service.py` | Retry-wrapped Gemini with structured logging |
| `services/instruction_parser.py` | NL → ExcelConfig via Gemini |
| `services/instruction_excel_generator.py` | ExcelConfig → styled .xlsx |
| `agents/chat_agent.py` | Full chat: slash commands, create Excel, analytics, Q&A |
| `api/routes/download.py` | Secure file download endpoint |
| `api/routes/chat.py` | POST /api/chat/ |
| `api/routes/agent.py` | Uses Redis session store |
| `api/routes/health.py` | /health + /ready with DB + Redis checks |
| `models/database.py` | PostgreSQL + SQLite auto-detection |
| `alembic/env.py` | Database migration support |
| `Dockerfile` | Multi-stage, non-root user, EasyOCR pre-download |

### Frontend
| File | What it does |
|------|-------------|
| `components/layout/ChatPanel.tsx` | Full agent chat: upload, NL instructions, download button, quick prompts |
| `hooks/useWebSocket.ts` | Handles `excel_ready` event → triggers download card in chat |
| `Dockerfile` | Multi-stage with nginx, non-root |

### Infrastructure
| File | What it does |
|------|-------------|
| `docker-compose.yml` | PostgreSQL + Redis + backend + frontend + nginx |
| `docker-compose.dev.yml` | Dev override: SQLite, no Redis needed |
| `nginx/nginx.conf` | Reverse proxy with rate limiting + WebSocket + security |
| `.env.example` | All environment variables documented |

## How to merge into Phases 1-4

### Backend — copy these files:
```
requirements.txt                                → REPLACE
.env.example                                    → REPLACE
backend/app/config.py                           → REPLACE
backend/app/main.py (use main_final.py)         → REPLACE
backend/app/utils/logger.py                     → NEW
backend/app/utils/rate_limiter.py               → NEW
backend/app/utils/retry.py                      → NEW
backend/app/services/session_store.py           → NEW
backend/app/services/gemini_service.py          → REPLACE
backend/app/services/instruction_parser.py      → NEW
backend/app/services/instruction_excel_generator.py → NEW
backend/app/agents/chat_agent.py                → NEW
backend/app/api/routes/download.py              → NEW
backend/app/api/routes/chat.py                  → NEW
backend/app/api/routes/agent.py                 → REPLACE (uses Redis)
backend/app/api/routes/health.py                → NEW
backend/app/models/database.py                  → REPLACE
backend/alembic/env.py                          → NEW
backend/alembic.ini                             → NEW
backend/Dockerfile                              → REPLACE
```

### Frontend — copy these files:
```
frontend/src/components/layout/ChatPanel.tsx    → REPLACE
frontend/src/hooks/useWebSocket.ts              → REPLACE
frontend/Dockerfile                             → REPLACE
frontend/nginx.conf                             → NEW
```

### Infrastructure:
```
docker-compose.yml        → REPLACE
docker-compose.dev.yml    → NEW
nginx/nginx.conf          → NEW
```

## Deployment

### Quick start (production):
```bash
cp .env.example .env
# Edit .env: set GEMINI_API_KEY, SECRET_KEY, POSTGRES_PASSWORD
docker-compose up --build -d
```

### Quick start (local dev — no Postgres/Redis needed):
```bash
cp .env.example .env
# Only GEMINI_API_KEY needed
docker-compose -f docker-compose.dev.yml up --build
```

### Database migrations:
```bash
cd backend
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

## New Chat features

Users can now type in plain English:
| Input | What happens |
|-------|-------------|
| `Create invoice template with tax` | Gemini designs schema → Excel generated → Download button appears |
| `Monthly sales report with bar chart` | Multi-sheet Excel with charts → Download |
| `What is the average revenue?` | Analytics agent answers from loaded data |
| `/help` | Shows all commands |
| `/plan` | Generates execution plan for uploaded file |
| `/approve` | Approves all suggestions |
| `/chart` | Generates charts |
| `/export` | Shows download button for current file |

## Download flow
1. Agent generates Excel → saved to `workspace/excels/`
2. Backend broadcasts `excel_ready` via WebSocket
3. Frontend ChatPanel receives event → renders Download button in chat
4. User clicks Download → `/api/download/excel/{filename}` → file served securely
5. Path traversal protection enforced server-side

## Monitoring endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness (always 200) |
| `GET /ready` | Readiness — checks DB + Redis + workspace |
| `GET /metrics` | Prometheus metrics (internal only via nginx) |
