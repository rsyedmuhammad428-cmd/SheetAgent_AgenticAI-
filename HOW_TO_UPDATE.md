# How to Update Code Without Rebuilding Docker

## The volume mount (already in docker-compose.yml)

The docker-compose.yml has this line:
  volumes:
    - ./backend/app:/app/app

This means your LOCAL backend/app/ folder is mounted INTO the container.
Any .py file you change locally is immediately available inside the container.

## Workflow for backend changes (Python files)

1. Edit any file in backend/app/
2. Run:
   docker-compose down
   docker-compose up -d

That's it. No rebuild. Takes ~10 seconds.

## Workflow for frontend changes (React/TypeScript)

Frontend IS compiled (npm run build) so it needs a rebuild when changed:
  docker-compose up --build -d frontend

But backend changes (which is most of the intelligence) don't need frontend rebuild.

## Files in this zip — what to replace

backend/app/agents/chat_agent.py              REPLACE  (intelligence fix)
backend/app/services/instruction_parser.py    REPLACE  (no more placeholder)
backend/app/services/instruction_excel_generator.py  REPLACE  (real data)
backend/app/api/routes/chat.py                REPLACE  (passes file path)
backend/app/api/routes/upload.py              REPLACE  (returns file path)
frontend/src/components/layout/ChatPanel.tsx  REPLACE  (waits for instruction)
frontend/src/api/client.ts                    REPLACE  (passes file path)
frontend/src/store/agentStore.ts              REPLACE  (adds missing fields)
frontend/src/hooks/useWebSocket.ts            REPLACE  (all events handled)
docker-compose.yml                            REPLACE  (volume mount for hot reload)

## Commands after replacing files

# Backend only changed (Python files):
docker-compose down && docker-compose up -d

# Frontend also changed:
docker-compose down
docker-compose up --build -d frontend
docker-compose up -d

## Verify it works

1. Open http://localhost
2. Upload any file (CSV, image, PDF, Word doc)
3. Notice: agent does NOT auto-process — it asks "what do you want to do?"
4. Type your instruction: "Create a professional salary dashboard from this data"
5. Agent reads the file, builds real Excel matching your request
6. Green Download button appears in chat
7. Click Download — Excel file with real data downloads immediately

## What changed in intelligence

BEFORE: Any message → "Custom Workbook" with placeholder columns
AFTER:
  - Reads actual file content (CSV, Excel, PDF, image via Gemini Vision, Word doc)
  - Understands your specific request
  - Generates domain-specific columns (invoice fields for invoices, HR fields for HR)
  - Adds real formulas (Net Salary = Basic + Allowances - Deductions)
  - Adds conditional formatting (red for overdue, green for paid)
  - Adds charts when relevant
  - Sample data matches the domain (real names, realistic numbers, proper dates)
  - Never returns "Custom Workbook" placeholder again
