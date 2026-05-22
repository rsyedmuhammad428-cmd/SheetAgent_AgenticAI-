# SheetAgent AI — Bug Fix Package

## Errors Fixed

### 1. numpy._core.multiarray ImportError (THE MAIN ERROR)
**Root cause:** numpy 1.26.4 has a `numpy.core` module but pandas 2.2.x + Python 3.12 
needs `numpy._core`. They conflict when pip resolves them together.

**Fix:** Upgraded to `numpy==2.0.2` which has the `_core` module.
Also the Dockerfile now installs numpy FIRST before everything else:
```dockerfile
RUN pip install --no-cache-dir numpy==2.0.2
RUN pip install --no-cache-dir -r requirements.txt
```

### 2. Missing __init__.py files
Every Python package directory needs an `__init__.py`. 
The Dockerfile now auto-creates them:
```dockerfile
RUN find /app/app -type d -exec touch {}/__init__.py \;
```

### 3. api/routes/__init__.py circular import
The `__init__.py` was importing all routes at module load time.
Now uses explicit imports only when needed.

### 4. LangChain/LangGraph version mismatch  
`langgraph==0.1.9` is incompatible with `langchain==0.2.5`.
**Fix:** Upgraded to `langchain==0.2.16` + `langgraph==0.2.4` + `langchain-core==0.2.40`

### 5. pydantic-settings model_config
Pydantic v2 requires `model_config` dict instead of `class Config`.
Fixed in `config.py`.

### 6. Optional deps crashing main.py
Sentry, Prometheus, Phase2-4 routes — if any dep missing, app crashed entirely.
**Fix:** All optional imports wrapped in `try/except` in `main.py`.

## Files to REPLACE in your project

```
backend/requirements.txt          ← MUST REPLACE (numpy fix)
backend/Dockerfile                 ← MUST REPLACE (numpy install order)
backend/app/main.py                ← MUST REPLACE (safe imports)
backend/app/config.py              ← MUST REPLACE (pydantic v2 fix)
backend/app/models/database.py     ← MUST REPLACE
backend/app/models/state.py        ← MUST REPLACE
backend/app/models/schemas.py      ← MUST REPLACE
backend/app/services/ws_manager.py ← MUST REPLACE
backend/app/services/workspace_service.py ← MUST REPLACE
backend/app/services/session_store.py     ← MUST REPLACE
backend/app/services/gemini_service.py    ← MUST REPLACE
backend/app/parsers/csv_parser.py  ← MUST REPLACE
backend/app/agents/graph.py        ← MUST REPLACE
backend/app/api/routes/__init__.py ← MUST REPLACE
backend/app/api/routes/upload.py   ← MUST REPLACE
backend/app/api/routes/workspace.py← MUST REPLACE
backend/app/api/routes/ws.py       ← MUST REPLACE
backend/app/api/routes/agent.py    ← MUST REPLACE
backend/app/api/routes/health.py   ← MUST REPLACE
backend/app/utils/rate_limiter.py  ← MUST REPLACE
docker-compose.yml                 ← MUST REPLACE
.env.example                       ← MUST REPLACE
```

## ADD these missing __init__.py files

```
backend/app/__init__.py                (empty file)
backend/app/api/__init__.py            (empty file)
backend/app/api/routes/__init__.py     (content: from . import upload, workspace, ws)
backend/app/agents/__init__.py         (empty file)
backend/app/services/__init__.py       (empty file)
backend/app/parsers/__init__.py        (empty file)
backend/app/models/__init__.py         (empty file)
backend/app/utils/__init__.py          (empty file)
```

## Rebuild command (run after replacing files)

```powershell
# In VS Code PowerShell terminal:
docker-compose down
docker-compose up --build -d
docker-compose logs -f backend
```

## Verify it's working

```powershell
# Should return {"status":"ok","version":"5.0.0"}
Invoke-WebRequest -Uri "http://localhost/health" | Select-Object -Expand Content

# Should return {"status":"ok","checks":{...}}
Invoke-WebRequest -Uri "http://localhost/ready" | Select-Object -Expand Content
```
