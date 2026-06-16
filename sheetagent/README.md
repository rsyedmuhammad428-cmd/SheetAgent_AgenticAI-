# SheetAgent AI — Intelligent Data Operating System

Phase 1: Core pipeline (CSV/Excel → Gemini analysis → styled Excel output)

## Quick Start

### 1. Get your Gemini API key
https://aistudio.google.com/app/apikey (free tier)

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run with Docker
```bash
docker-compose up --build
```

Open http://localhost:5173

### 4. Run locally (dev)

**Backend:**
```bash
cd backend
cp .env.example .env   # add your key
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Phase 1 Capabilities
- Upload CSV or Excel files
- Gemini-powered schema detection (invoice, sales, HR, etc.)
- Data cleaning suggestions (duplicates, missing values, dates, currency)
- Human-in-the-loop approval before any changes
- Styled Excel output with freeze panes, filters, conditional formatting
- Live execution log via WebSocket
- Sandboxed workspace — all files stay in ./workspace/

## Project Structure
```
sheetagent/
├── backend/          FastAPI + LangGraph + Gemini
├── frontend/         React + TypeScript + Tailwind
├── workspace/        All runtime files (sandboxed)
└── docker-compose.yml
```

## Roadmap
- Phase 2: Formula agent + reflection agent
- Phase 3: OCR pipeline (scanned PDFs, images)
- Phase 4: Visualization + analytics agents
- Phase 5: Memory system + session history
