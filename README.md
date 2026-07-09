# 🤖 SheetAgent AI — Complete Project Documentation

> **An Agentic AI-powered Excel workbook generator that converts natural language,
> PDFs, images, and CSV files into professional spreadsheets with charts,
> dashboards, and business analytics — all through a chat interface.**

🔗 **Live Demo:** https://sheet-agent-agentic-ai-tbjd.vercel.app/

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Folder Structure — A to Z](#-folder-structure--a-to-z)
4. [Backend Technologies & Packages](#-backend-technologies--packages)
5. [Frontend Technologies & Packages](#-frontend-technologies--packages)
6. [AI & Agent System](#-ai--agent-system)
7. [Database & Storage](#-database--storage)
8. [Authentication System](#-authentication-system)
9. [API Endpoints](#-api-endpoints)
10. [Environment Variables](#-environment-variables)
11. [How Each Feature Works](#-how-each-feature-works)
12. [Data Flow](#-data-flow)

---

## 🎯 Project Overview

SheetAgent AI is a **full-stack Agentic AI application** built with:

- A **multi-agent Python backend** that understands natural language, extracts
  data from any file type, and generates production-quality Excel workbooks
- A **React/TypeScript frontend** with a ChatGPT-style interface for
  interacting with the AI agent
- **Google Gemini** as the primary AI model with **OpenRouter** as an
  automatic failover
- **Per-user authentication** with JWT tokens and a persistent chat history
  sidebar

### What it can do

| Input | Output |
|---|---|
| Natural language ("make a student marksheet") | Excel workbook with headers, totals, filters |
| CSV file upload | Cleaned, formatted Excel with charts |
| PDF file (text or scanned) | Multi-page data extracted to Excel |
| Image / PNG / JPG (table in photo) | OCR-extracted data in Excel |
| Financial data | Executive dashboard with KPI cards, profit analysis |
| Any data + "make bar chart by Subject" | Excel with aggregated bar chart on a Charts sheet |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│              https://sheet-agent-agentic-ai-tbjd.vercel.app     │
└─────────────────────┬───────────────────────────────────────────┘
                      │  HTTPS
          ┌───────────▼───────────┐
          │       Nginx           │  Reverse proxy — routes
          │    (port 80)          │  /api/* → backend:8000
          │    nginx:alpine       │  /ws/*  → backend:8000
          └──────┬────────────────┘  /* → frontend:3000
                 │
     ┌───────────┴───────────────┐
     │                           │
┌────▼──────────┐    ┌──────────▼──────────┐
│   Frontend    │    │      Backend         │
│ TanStack Start│    │  FastAPI + Uvicorn   │
│  React 19     │    │  Python 3.12         │
│  TypeScript   │    │  port 8000           │
│  Tailwind CSS │    └──────────┬───────────┘
│  port 3000    │               │
└───────────────┘    ┌──────────┴───────────┐
                     │                       │
              ┌──────▼──────┐   ┌───────────▼─────────┐
              │ PostgreSQL  │   │       Redis           │
              │ (Neon free) │   │  (session store)      │
              │   port 5432 │   │    port 6379          │
              └─────────────┘   └─────────────────────┘
                     │
              ┌──────▼──────┐
              │  Gemini API │  + OpenRouter fallback
              │  (Google)   │
              └─────────────┘
```

---

## 📁 Folder Structure — A to Z

```
SheetAgent_AgenticAI-/
│
├── docker-compose.yml          # Orchestrates all 5 services (postgres, redis,
│                               # backend, frontend, nginx)
│
├── nginx/
│   └── nginx.conf              # Reverse proxy config — routes /api/* to backend,
│                               # /* to frontend, /ws/* to WebSocket backend
│
├── backend/                    # FastAPI Python application
│   ├── Dockerfile              # Docker image for backend (Python 3.12-slim)
│   ├── requirements.txt        # All Python dependencies (pinned versions)
│   ├── .env                    # Environment variables (not in git)
│   └── app/
│       ├── main.py             # FastAPI app entry point — creates app instance,
│       │                       # registers all routers, CORS, lifespan (init_db)
│       ├── config.py           # Pydantic Settings — reads all env vars with
│       │                       # type validation and defaults
│       │
│       ├── agents/             # 🤖 THE BRAIN — all AI logic lives here
│       │   ├── chat_agent.py   # MAIN AGENT: classifies intent, decides whether
│       │   │                   # to CREATE / PROCESS / ANALYZE / QUESTION /
│       │   │                   # CLARIFY. Handles human-in-the-loop flow,
│       │   │                   # inline data parsing, enhancement choice UI
│       │   ├── intelligence_engine.py  # Understands the task via Gemini,
│       │   │                           # builds workbook design (sheets, charts,
│       │   │                           # conditional rules, heading, theme)
│       │   ├── excel_generator.py  # Converts design + data into actual .xlsx
│       │   │                       # file using openpyxl. Handles heading rows,
│       │   │                       # column formatting, totals, conditional
│       │   │                       # formatting (red/green), charts, dashboard
│       │   ├── file_extractor.py   # Extracts structured data from any file:
│       │   │                       # CSV → pandas, Excel → openpyxl,
│       │   │                       # PDF → pdfplumber (3-stage fallback),
│       │   │                       # Image → Gemini Vision (4-pass pipeline)
│       │   ├── analytics_agent.py  # Generates statistical analysis on datasets
│       │   ├── cleaning_agent.py   # Cleans raw extracted data (nulls, types)
│       │   ├── formula_agent.py    # Generates Excel formulas (SUM, IF, VLOOKUP)
│       │   ├── graph.py            # LangGraph agent workflow definition
│       │   ├── input_agent.py      # Validates and normalises user input
│       │   ├── memory_agent.py     # Manages conversation memory/context
│       │   ├── ocr_agent.py        # Handles OCR pipeline for scanned documents
│       │   ├── planner_agent.py    # Plans multi-step agent execution
│       │   ├── quota_helper.py     # Detects Gemini quota errors (daily vs RPM),
│       │   │                       # formats user-friendly error with PKT reset time
│       │   ├── rate_limiter.py     # Auto-retry wrapper for Gemini API calls
│       │   │                       # (RPM errors: wait + retry, daily: fail fast)
│       │   ├── reflection_agent.py # Self-evaluates agent output quality
│       │   ├── schema_agent.py     # Detects data schema and column types
│       │   ├── visualization_agent.py  # Decides chart type and configuration
│       │   └── extraction_agent.py    # Coordinates multi-file data extraction
│       │
│       ├── api/
│       │   └── routes/
│       │       ├── auth.py      # POST /api/auth/register, /login, /logout
│       │       │                # GET  /api/auth/me
│       │       │                # JWT auth with bcrypt password hashing
│       │       ├── chat.py      # POST /api/chat/       — main chat endpoint
│       │       │                # GET  /api/chat/history — user's chat sessions
│       │       │                # GET  /api/chat/history/{id} — session messages
│       │       │                # DELETE /api/chat/history/{id} — delete session
│       │       ├── upload.py    # POST /api/upload/     — file upload
│       │       │                # Saves file to workspace, creates session
│       │       ├── download.py  # GET /api/download/excel/{filename}
│       │       │                # Streams the generated .xlsx file
│       │       ├── ws.py        # WebSocket /ws/{session_id}
│       │       │                # Sends real-time logs + "excel_ready" events
│       │       ├── health.py    # GET /health — Docker health check
│       │       ├── workspace.py # Workspace file management
│       │       └── agent.py     # Phase-based agent execution endpoints
│       │
│       ├── models/
│       │   ├── database.py      # SQLAlchemy async engine + all ORM models:
│       │   │                    # SessionRecord, User, ChatSession,
│       │   │                    # ChatMessageRecord. init_db() creates all tables
│       │   ├── state.py         # AgentState dataclass — shared state passed
│       │   │                    # between all agents in the pipeline
│       │   ├── schemas.py       # Pydantic request/response schemas
│       │   └── memory_models.py # UserPreferences and memory-related models
│       │
│       ├── services/
│       │   ├── gemini_service.py   # Gemini API client — analyze(), analyze_json(),
│       │   │                       # vision calls. Handles streaming + JSON parse
│       │   ├── llm_failover.py     # Automatic Gemini → OpenRouter failover
│       │   │                       # on 403/429/500 errors
│       │   ├── session_store.py    # Redis-backed session store (AgentState
│       │   │                       # persistence between messages, 24h TTL)
│       │   ├── ws_manager.py       # WebSocket connection manager — broadcasts
│       │   │                       # logs and excel_ready events to clients
│       │   ├── workspace_service.py # File workspace management on disk
│       │   ├── memory_service.py   # Long-term memory storage/retrieval
│       │   └── diff_service.py     # Compares Excel versions for change tracking
│       │
│       ├── parsers/
│       │   ├── pdf_parser.py        # pdfplumber multi-page PDF extraction
│       │   ├── csv_parser.py        # CSV/TSV parsing with type inference
│       │   ├── ocr_engine.py        # EasyOCR + pytesseract integration
│       │   ├── image_preprocessor.py # PIL image cleanup before OCR
│       │   └── table_detector.py    # Detects table boundaries in images
│       │
│       └── utils/
│           ├── logger.py        # Structured logging with structlog
│           ├── rate_limiter.py  # HTTP-level rate limiting with slowapi
│           └── retry.py         # Tenacity retry decorator for external calls
│
└── frontend/                   # TanStack Start React application
    ├── Dockerfile              # Multi-stage: Node build → Nitro runtime
    ├── package.json            # All npm dependencies
    ├── vite.config.ts          # Vite + dev proxy (/api → localhost:8000)
    ├── tsconfig.json           # TypeScript config (@/ path alias)
    ├── components.json         # shadcn/ui configuration
    └── src/
        ├── routes/
        │   ├── index.tsx       # MAIN PAGE — auth gate, all state management,
        │   │                   # chat handlers, WebSocket setup, greeting logic
        │   └── __root.tsx      # Root layout — wraps all routes
        │
        ├── components/
        │   ├── sheet-agent/    # Application-specific components
        │   │   ├── AuthPage.tsx      # Login/Register tabbed card
        │   │   │                     # Pakistan-time greeting, bcrypt-safe
        │   │   ├── ChatPanel.tsx     # Message list, input box, file attach,
        │   │   │                     # stop button, clarify option buttons,
        │   │   │                     # download card, responsive layout
        │   │   ├── LeftSidebar.tsx   # Collapsible sidebar: recent chats with
        │   │   │                     # 3-dot delete menu, file list, theme toggle
        │   │   │                     # Mobile: overlay. Desktop: inline.
        │   │   ├── WelcomeScreen.tsx # Home screen with time-based greeting
        │   │   │                     # and 3 quick-start suggestion cards
        │   │   ├── SheetView.tsx     # Renders extracted/generated spreadsheet
        │   │   │                     # data as an HTML table preview
        │   │   ├── ChartView.tsx     # Renders Recharts bar/line/pie charts
        │   │   │                     # from chart data returned by agent
        │   │   └── RightSidebar.tsx  # (Reserved) artifact panel
        │   │
        │   └── ui/             # shadcn/ui component library (40+ components)
        │       ├── button.tsx, input.tsx, label.tsx   # Form controls
        │       ├── dialog.tsx, drawer.tsx, sheet.tsx  # Overlays
        │       ├── dropdown-menu.tsx, popover.tsx     # Menus
        │       ├── chart.tsx                          # Recharts wrapper
        │       ├── sonner.tsx                         # Toast notifications
        │       └── ... (35 more)
        │
        ├── lib/
        │   ├── sheet-agent.ts  # ALL backend API calls:
        │   │                   # sendMessage(), uploadFile(), downloadExcel(),
        │   │                   # fetchChatHistory(), fetchChatMessages(),
        │   │                   # deleteChatSession(), connectWebSocket()
        │   │                   # Type definitions for all data shapes
        │   ├── auth.ts         # Auth API: login(), register(), logout(), getMe()
        │   │                   # localStorage helpers: getToken(), isLoggedIn()
        │   │                   # SSR-safe (isBrowser() guards)
        │   └── utils.ts        # cn() Tailwind class merger
        │                       # getPakistanGreeting() — time-based greeting
        │                       # in Asia/Karachi timezone via Intl API
        │
        └── hooks/
            └── use-mobile.tsx  # useIsMobile() — breakpoint detection hook
```

---

## 🐍 Backend Technologies & Packages

### Core Framework

| Package | Version | Purpose |
|---|---|---|
| **FastAPI** | 0.111.0 | Web framework — REST API + WebSocket routes |
| **Uvicorn** | 0.30.1 | ASGI server (runs FastAPI) |
| **Python** | 3.12 | Runtime language |
| **Pydantic** | 2.7.4 | Data validation, request/response schemas |
| **pydantic-settings** | 2.3.4 | Environment variable management |

### AI & LLM

| Package | Version | Purpose |
|---|---|---|
| **google-generativeai** | 0.7.2 | Gemini API client (primary AI model) |
| **langchain** | 0.2.16 | LLM orchestration framework |
| **langchain-google-genai** | 1.0.10 | LangChain + Gemini integration |
| **langgraph** | 0.2.4 | Agent workflow as a stateful graph |
| **httpx** | 0.27.2 | HTTP client for OpenRouter API calls |

### Data Processing

| Package | Version | Purpose |
|---|---|---|
| **pandas** | ≥2.2.2 | CSV parsing, data manipulation, type inference |
| **numpy** | ≥1.26.0 | Numerical operations for data analysis |
| **openpyxl** | 3.1.4 | Reading + writing `.xlsx` Excel files |

### PDF & Document Parsing

| Package | Version | Purpose |
|---|---|---|
| **pdfplumber** | 0.11.4 | PDF table extraction (text-based PDFs) |
| **pdf2image** | 1.17.0 | Convert PDF pages to images (scanned PDFs) |
| **pypdf** | 4.3.1 | PDF metadata and text extraction |

### OCR (Image → Text)

| Package | Version | Purpose |
|---|---|---|
| **easyocr** | 1.7.2 | Deep-learning OCR for images |
| **img2table** | 1.2.9 | Table structure detection in images |
| **opencv-python-headless** | 4.9.0.80 | Image preprocessing for OCR |
| **Pillow** | 10.4.0 | PIL image loading and manipulation |

### Database

| Package | Version | Purpose |
|---|---|---|
| **SQLAlchemy** | 2.0.36 | ORM — defines models, runs queries |
| **asyncpg** | 0.29.0 | Async PostgreSQL driver |
| **aiosqlite** | 0.20.0 | Async SQLite driver (local dev) |
| **psycopg2-binary** | 2.9.10 | Sync PostgreSQL driver (Alembic) |
| **alembic** | 1.13.3 | Database migrations |

### Authentication & Security

| Package | Version | Purpose |
|---|---|---|
| **passlib[bcrypt]** | 1.7.4 | Password hashing with bcrypt |
| **bcrypt** | 4.0.1 | Pinned — avoids 72-byte passlib bug |
| **PyJWT** | 2.8.0 | JWT token creation and validation |
| **python-jose** | 3.3.0 | Additional JWT/JWS/JWE support |

### Session & Cache

| Package | Version | Purpose |
|---|---|---|
| **redis** | 5.1.1 | Redis client for session storage |
| **arq** | 0.26.1 | Async Redis job queue |

### Rate Limiting & Reliability

| Package | Version | Purpose |
|---|---|---|
| **slowapi** | 0.1.9 | FastAPI rate limiting middleware |
| **tenacity** | ≥8.1.0 | Retry decorator for external API calls |

### Observability

| Package | Version | Purpose |
|---|---|---|
| **sentry-sdk** | 2.14.0 | Error tracking and performance monitoring |
| **structlog** | 24.4.0 | Structured JSON logging |
| **prometheus-fastapi-instrumentator** | 7.0.0 | Metrics endpoint for monitoring |

---

## ⚛️ Frontend Technologies & Packages

### Core Framework

| Package | Version | Purpose |
|---|---|---|
| **React** | 19.2.0 | UI component library (latest with concurrent features) |
| **TypeScript** | 5.8.3 | Type-safe JavaScript |
| **TanStack Start** | 1.167.50 | Full-stack React framework with SSR/SSG |
| **TanStack Router** | 1.168.25 | Type-safe file-based routing |
| **Vite** | 8.0.16 | Build tool and dev server |
| **Nitro** | 3.0 beta | Server runtime for SSR (Node.js output) |

### Styling

| Package | Version | Purpose |
|---|---|---|
| **Tailwind CSS** | 4.2.1 | Utility-first CSS framework |
| **tailwind-merge** | 3.5.0 | Merges conflicting Tailwind classes |
| **clsx** | 2.1.1 | Conditional class names |
| **tw-animate-css** | 1.3.4 | Animation utilities |
| **class-variance-authority** | 0.7.1 | Component variant system |

### UI Component Library (shadcn/ui + Radix)

All `@radix-ui/*` packages provide **accessible, unstyled primitives**
that shadcn/ui wraps with Tailwind styles:

| Component group | Packages | Used for |
|---|---|---|
| Layout | accordion, collapsible, separator, resizable-panels | Sidebar, panels |
| Overlay | dialog, drawer, sheet, popover, hover-card | Modals, menus |
| Forms | checkbox, radio-group, select, switch, slider, input-otp | Settings |
| Navigation | navigation-menu, menubar, breadcrumb, pagination | Layout nav |
| Feedback | alert-dialog, sonner (toast), progress, skeleton | Notifications |
| Data | table, calendar, avatar, badge, carousel | Data display |
| Menus | dropdown-menu, context-menu, command | Right-click / 3-dot menus |

### Data & State

| Package | Version | Purpose |
|---|---|---|
| **TanStack Query** | 5.83.0 | Server state management and caching |
| **react-hook-form** | 7.71.2 | Form state management |
| **zod** | 3.24.2 | Schema validation for forms |
| **@hookform/resolvers** | 5.2.2 | Connects zod with react-hook-form |

### Charts & Visualization

| Package | Version | Purpose |
|---|---|---|
| **recharts** | 2.15.4 | Bar, line, pie, area charts |

### UI Utilities

| Package | Version | Purpose |
|---|---|---|
| **lucide-react** | 0.575.0 | 1000+ SVG icons |
| **sonner** | 2.0.7 | Toast notification system |
| **vaul** | 1.1.2 | Drawer/bottom-sheet component |
| **cmdk** | 1.1.1 | Command palette / search |
| **embla-carousel-react** | 8.6.0 | Touch-friendly carousel |
| **date-fns** | 4.1.0 | Date formatting and manipulation |
| **react-day-picker** | 9.14.0 | Calendar date picker |
| **input-otp** | 1.4.2 | OTP / PIN input component |

---

## 🤖 AI & Agent System

### How the Multi-Agent Pipeline Works

```
User Message
     │
     ▼
┌─────────────────┐
│   chat_agent    │  1. Parse inline data (7 strategies)
│ Intent classify │  2. Classify intent: CREATE / PROCESS /
│  (keyword-based)│     ANALYZE / QUESTION / CLARIFY
└────────┬────────┘
         │
   ┌─────┴──────────────────────────────────────┐
   │                    │                        │
   ▼                    ▼                        ▼
CREATE              PROCESS                  QUESTION
   │                    │                        │
   ▼                    ▼                        ▼
intelligence_engine  file_extractor         Gemini answer
 ├─ understand task   ├─ CSV → pandas
 ├─ design workbook   ├─ PDF → pdfplumber
 └─ chart/cond rules  ├─ Image → Vision OCR
                      └─ Excel → openpyxl
         │
         ▼
   cleaning_agent     (normalize types, remove nulls)
         │
         ▼
   excel_generator    (build .xlsx with openpyxl)
   ├─ Heading row (merged, white text on dark bg)
   ├─ Column headers + auto-filter
   ├─ Data rows with alternating fill
   ├─ Totals row (SUM/AVERAGE, skips year/ID cols)
   ├─ Conditional formatting (red/green)
   ├─ Charts sheet (aggregated bar/line/pie)
   └─ Executive Dashboard sheet (KPI cards, insights)
         │
         ▼
   WebSocket event → frontend "excel_ready"
   Download card appears in chat
```

### AI Model Strategy

```
Primary:  Google Gemini 1.5 Flash (free, 15 req/min)
             │ 403 / 429 / 500
             ▼
Fallback: OpenRouter → meta-llama/llama-3.1-8b-instruct
```

---

## 🗄 Database & Storage

### Models (PostgreSQL via SQLAlchemy)

```python
User              — id, email, full_name, hashed_pw, created_at
ChatSession       — id (=session_id), user_id, title, message_count, created_at, updated_at
ChatMessageRecord — id, session_id, role, text, action_json, created_at
SessionRecord     — id, file_name, state_json (ephemeral agent state, 24h TTL via Redis)
```

### Redis (Session Store)
- Stores `AgentState` JSON per session (24h TTL)
- AgentState holds: extracted_data, cleaned_data, workbook design, file paths
- Falls back to in-memory dict if Redis unavailable

### File Workspace (Docker volume)
```
/app/workspace/
├── incoming/     Raw uploaded files
├── processing/   Files being actively worked on
├── extracted/    Data extracted from files
├── cleaned/      Normalised/cleaned data
├── excels/       Generated .xlsx output files ← download from here
├── charts/       Chart image files
└── reports/      Summary reports
```

---

## 🔐 Authentication System

```
Register → bcrypt.hash(password[:72])    → PostgreSQL users table
Login    → bcrypt.verify(password, hash) → JWT token (72h expiry)
           ↓
           JWT stored in localStorage (SSR-safe with isBrowser() guard)
           ↓
           Sent as "Authorization: Bearer <token>" header on all requests
           ↓
           Backend decodes with PyJWT using SECRET_KEY from env
           ↓
           _current_user() dependency injected into protected routes
```

---

## 📡 API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account → JWT |
| POST | `/api/auth/login` | Sign in → JWT |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/logout` | Sign out |

### Chat
| Method | Path | Description |
|---|---|---|
| POST | `/api/chat/` | Send message → `{text, intent, action, session_id}` |
| GET | `/api/chat/history` | List user's chat sessions |
| GET | `/api/chat/history/{id}` | Get messages for one session |
| DELETE | `/api/chat/history/{id}` | Delete a session |

### Files
| Method | Path | Description |
|---|---|---|
| POST | `/api/upload/` | Upload file → `{session_id, file_path}` |
| GET | `/api/download/excel/{filename}` | Download `.xlsx` |

### System
| Method | Path | Description |
|---|---|---|
| WS | `/ws/{session_id}` | Real-time logs + `excel_ready` events |
| GET | `/health` | Docker health check |
| GET | `/docs` | FastAPI Swagger UI |

---

## ⚙️ Environment Variables

```env
# ── AI Keys ──────────────────────────────────────────────────
GEMINI_API_KEY=AIzaSy...           # Google AI Studio → free
GEMINI_MODEL=gemini-1.5-flash      # Free model (no billing needed)
OPENROUTER_API_KEY=sk-or-...       # openrouter.ai → fallback AI

# ── Database ──────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@host/db?ssl=require
# For local dev: sqlite+aiosqlite:///./sheetagent.db

# ── Redis ─────────────────────────────────────────────────────
REDIS_URL=redis://:password@host:6379

# ── Security ──────────────────────────────────────────────────
SECRET_KEY=your-random-64-char-string

# ── App Config ────────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=["https://your-app.vercel.app"]
```

---

## 🔄 How Each Feature Works

### Human-in-the-Loop (Clarification System)
When the user sends a vague request ("make a sheet"), the agent asks for
clarification instead of guessing. When data is detected, it offers
enhancement options (Basic / + Chart / + Dashboard / Full) as clickable
buttons. The pending task is stored in `_PENDING[session_id]` and resumed
when the user responds.

### Multi-page PDF Support
pdfplumber extracts tables page by page. Smart header detection compares
each page's first row against the known column headers — if ≥50% match,
it's treated as a repeated header and skipped. If it doesn't match, it's
treated as data. After table extraction, Gemini text extraction runs on
the full concatenated text to catch any highlighted/coloured rows that
pdfplumber missed.

### Large Dataset Charts
When a category column has >20 unique values, charts would be unreadable.
The aggregation engine groups data by category and computes SUM or AVERAGE
per group, writes the aggregated rows to hidden columns in the Charts sheet,
then builds the chart from those aggregated values. This means "bar chart
by Subject for 100 students" produces 5 clean bars (one per subject)
instead of 100 unreadable ones.

### Responsive Design (RWD)
- **Mobile (<1024px):** LeftSidebar is a fixed overlay that slides in from
  the left via CSS transform. A hamburger button in the header opens it.
  Tapping the dark backdrop closes it.
- **Desktop (≥1024px):** Sidebar is inline, collapses via width transition.
- **Chat bubbles:** max-w-[88%] mobile, max-w-[80%] desktop.
- **Download cards:** flex-col on mobile, flex-row on tablet+.

### Pakistan Timezone Greeting
Uses `Intl.DateTimeFormat` with `timeZone: "Asia/Karachi"` to read the
current hour in PKT (UTC+5) regardless of where the server or browser is:
- 5 AM–12 PM → Good morning
- 12 PM–5 PM → Good afternoon
- 5 PM–9 PM → Good evening
- 9 PM–5 AM → Good night

---

*Built by Muhammad Raza — BS Software Engineering, Iqra University*
*GitHub: https://github.com/rsyedmuhammad428-cmd/SheetAgent_AgenticAI-*
*Live: https://sheet-agent-agentic-ai-tbjd.vercel.app/*
