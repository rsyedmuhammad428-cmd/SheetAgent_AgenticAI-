# ════════════════════════════════════════════════════════════════
# SheetAgent AI — Windows PowerShell Setup Commands
# Run these in VS Code Terminal (PowerShell)
# ════════════════════════════════════════════════════════════════

# ── STEP 1: Prerequisites check ──────────────────────────────────
Write-Host "Checking prerequisites..." -ForegroundColor Cyan
docker --version
docker-compose --version
node --version
python --version

# ── STEP 2: Navigate to your project folder ──────────────────────
# Change this to your actual project path
cd "C:\Users\YourName\sheetagent"

# ── STEP 3: Copy env file and add your Gemini API key ────────────
Copy-Item ".env.example" ".env"
# Then open .env in VS Code and set GEMINI_API_KEY:
code .env

# ── STEP 4: Build and start all containers ───────────────────────
docker-compose up --build -d

# Watch logs (optional):
# docker-compose logs -f backend

# ── STEP 5: Check everything is running ──────────────────────────
docker-compose ps

# ── STEP 6: Open the app ─────────────────────────────────────────
Start-Process "http://localhost"

# ════════════════════════════════════════════════════════════════
# LOCAL DEV (no Docker needed for frontend)
# ════════════════════════════════════════════════════════════════

# Terminal 1 — Backend only via Docker:
docker-compose up postgres redis backend -d

# Terminal 2 — Frontend with hot reload:
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173

# ════════════════════════════════════════════════════════════════
# USEFUL COMMANDS
# ════════════════════════════════════════════════════════════════

# View backend logs live:
docker-compose logs -f backend

# Restart only backend after code change:
docker-compose restart backend

# Rebuild backend only (after requirements.txt change):
docker-compose up --build -d backend

# Stop everything:
docker-compose down

# Stop and delete all data (nuclear option):
docker-compose down -v

# Open backend container shell:
docker-compose exec backend bash

# Run DB migrations manually:
docker-compose exec backend alembic upgrade head

# Check backend health:
Invoke-WebRequest -Uri "http://localhost/health" | Select-Object -Expand Content

# Check all services ready:
Invoke-WebRequest -Uri "http://localhost/ready" | Select-Object -Expand Content

# ════════════════════════════════════════════════════════════════
# INSTALL FRONTEND PACKAGES (if running outside Docker)
# ════════════════════════════════════════════════════════════════
cd frontend
npm install

# If npm install fails due to peer deps:
npm install --legacy-peer-deps

# ════════════════════════════════════════════════════════════════
# INSTALL BACKEND PACKAGES (if running outside Docker)
# ════════════════════════════════════════════════════════════════
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# CRITICAL: install numpy first to avoid conflicts
pip install numpy==2.0.2
pip install -r requirements.txt

# Run backend locally:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ════════════════════════════════════════════════════════════════
# TROUBLESHOOTING
# ════════════════════════════════════════════════════════════════

# If backend fails to start — check logs:
docker-compose logs backend --tail=50

# If numpy/pandas error persists — force reinstall:
docker-compose exec backend pip install --force-reinstall numpy==2.0.2 pandas==2.2.3

# If port 80 is in use:
netstat -ano | findstr :80
# Change nginx port in docker-compose.yml: "8080:80"

# If Docker build is slow (EasyOCR model download):
# This is normal — EasyOCR downloads ~100MB model on first build
# Subsequent builds use cache

# Reset everything and rebuild clean:
docker-compose down -v
docker system prune -f
docker-compose up --build -d
