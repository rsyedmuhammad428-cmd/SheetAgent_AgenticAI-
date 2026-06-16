# SheetAgent AI — Phase 6 (Intelligence Upgrade)

## What Phase 6 adds

| Component | What it does |
|-----------|-------------|
| `intelligence_engine.py` | Understands ANY task deeply using Gemini — no hardcode |
| `file_extractor.py` | Reads CSV, Excel, PDF, Images (Gemini Vision), Word docs |
| `excel_generator.py` | Professional Excel with themes, real sample data, formulas |
| `chat_agent.py` | Single response — never duplicates. Full intelligence pipeline |
| `gemini_service.py` | Robust JSON extraction — 3 attempts, handles all formats |
| `ChatPanel.tsx` | ChatGPT-style upload — attach file, type prompt, click Send |
| `useWebSocket.ts` | Deduplication guard — excel_ready fires once per filename |

## Problems fixed

### 1. Duplicate download cards
**Cause:** WebSocket broadcast `excel_ready` + API response both triggered download card.
**Fix:**
- `useWebSocket.ts`: tracks seen filenames in a Set — only fires callback once per filename
- `ChatPanel.tsx`: `sendingRef` guard prevents double-send
- `chat_agent.py`: single `handle_message` call, no background tasks

### 2. "Custom Workbook" fallback
**Cause:** Gemini JSON parsing failed silently → fell back to generic template.
**Fix:**
- `gemini_service.py`: 3 retry attempts with different prompts, 5-method JSON extraction
- `intelligence_engine.py`: validates design quality, falls back to domain-aware second attempt
- No hardcoded templates — everything driven by Gemini understanding the task

### 3. Files not being read / used
**Cause:** File content was not passed to the design step.
**Fix:**
- `file_extractor.py`: dedicated extractor for each file type
- `chat_agent.py`: extracted content passed to both `understand_task` AND `design_workbook`
- Images use Gemini Vision to extract actual data values

## Merge into Phase 5 (backend — no rebuild needed after copy)

```
# Copy these files into your project:
backend/app/agents/intelligence_engine.py   → NEW
backend/app/agents/file_extractor.py        → NEW
backend/app/agents/excel_generator.py       → NEW (replaces instruction_excel_generator.py)
backend/app/agents/chat_agent.py            → REPLACE
backend/app/services/gemini_service.py      → REPLACE
backend/app/api/routes/chat.py              → REPLACE

# Frontend (needs rebuild):
frontend/src/components/layout/ChatPanel.tsx → REPLACE
frontend/src/store/agentStore.ts             → REPLACE
frontend/src/api/client.ts                   → REPLACE
frontend/src/hooks/useWebSocket.ts           → REPLACE
```

## Update commands

```powershell
# After copying backend files (Python):
docker-compose restart backend

# After copying frontend files:
docker-compose up --build -d frontend

# Verify:
curl http://localhost/health
curl http://localhost/api/chat/health
```

## How it works now

```
User types: "Create a student marksheet with Math, Physics, English"
                           ↓
              IntelligenceEngine.understand_task()
              → Gemini: domain=education, needs subject columns, grades, pass/fail
                           ↓
              IntelligenceEngine.design_workbook()
              → Gemini: designs exact columns with formulas
                           ↓
              generate_excel()
              → Creates professional .xlsx with real sample data
                           ↓
              Single response with Download button


User uploads image + types: "Extract data and make salary report"
                           ↓
              FileExtractor.extract() 
              → Gemini Vision reads image → extracts actual data rows
                           ↓
              IntelligenceEngine.understand_task()
              → includes extracted data in task understanding
                           ↓
              IntelligenceEngine.design_workbook()
              → uses actual column names from image
                           ↓
              generate_excel() with real_data from image
              → populates sheet with extracted values
                           ↓
              Single response with Download button
```

## Note on intelligence_engine vs instruction_parser

Phase 6 replaces `instruction_parser.py` + `instruction_excel_generator.py` with:
- `intelligence_engine.py` (task understanding + workbook design)
- `excel_generator.py` (workbook generation)

The old files can stay — they're no longer called by `chat_agent.py`.
