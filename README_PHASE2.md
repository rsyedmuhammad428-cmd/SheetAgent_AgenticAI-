# SheetAgent AI — Phase 2 Patch

## What's new in Phase 2

| Agent | What it does |
|-------|-------------|
| Formula Agent | Natural language → Excel formulas via Gemini |
| Visualization Agent | Auto-generates bar/line/pie charts inside Excel |
| Reflection Agent | Scores output quality, writes Quality Report sheet |
| Analytics Agent | Answers plain-English questions about your data |
| Diff Service | Before/after diff of every cleaning change |

## New API endpoints (`/api/p2/`)

| Endpoint | Description |
|----------|-------------|
| `POST /api/p2/formula` | Apply natural language formulas to Excel |
| `POST /api/p2/analytics` | Ask a question about the data |
| `POST /api/p2/charts` | Generate charts (auto or specified) |
| `POST /api/p2/reflect` | Run quality reflection on output |
| `GET  /api/p2/diff/{session_id}` | Get before/after diff |
| `POST /api/p2/forecast` | Basic linear regression forecast |

## How to merge into Phase 1

### Backend — copy these files into your Phase 1 project:
```
backend/app/agents/formula_agent.py       → NEW
backend/app/agents/reflection_agent.py    → NEW
backend/app/agents/visualization_agent.py → NEW
backend/app/agents/analytics_agent.py     → NEW
backend/app/agents/graph.py               → REPLACE
backend/app/models/state.py               → REPLACE
backend/app/services/diff_service.py      → NEW
backend/app/api/routes/phase2.py          → NEW
backend/app/main.py                       → REPLACE
```

### Frontend — copy these files:
```
frontend/src/components/diff/DiffViewer.tsx         → NEW
frontend/src/components/formula/FormulaPanel.tsx    → NEW
frontend/src/components/charts/AnalyticsPanel.tsx   → NEW
frontend/src/components/charts/ReflectionPanel.tsx  → NEW
frontend/src/components/layout/RightPanel.tsx       → NEW (replaces LogPanel)
frontend/src/store/agentStore.ts                    → REPLACE
frontend/src/hooks/useWebSocket.ts                  → REPLACE
```

### Update App.tsx — replace `<LogPanel />` with `<RightPanel />`
```tsx
import RightPanel from './components/layout/RightPanel'
// ...
<RightPanel />   // replaces <LogPanel />
```

## No new dependencies needed
All Phase 2 features use the same packages from Phase 1.
numpy is already in requirements.txt (used by analytics agent).

## Phase 3 preview (OCR)
- Add `easyocr` and `img2table` to requirements.txt
- Implement `backend/app/agents/ocr_agent.py`
- Wire into graph.py OCR decision node
